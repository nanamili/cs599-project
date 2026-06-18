"""
MCP Client — 连接 LabAgent MCP Server，动态发现并调用工具

架构:
    Agent (LangGraph) → MCP Client (stdio) → MCP Server → 业务逻辑

价值:
    - 工具与 Agent 解耦：新增工具无需修改 Agent 代码
    - 标准化协议：任何 MCP-compatible 工具都可接入
    - 运行时发现：Agent 启动时自动 list_tools() 获取可用工具列表
"""

import sys, json, asyncio
from pathlib import Path
from typing import List, Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from langchain_core.tools import tool as langchain_tool

PROJECT_ROOT = Path(__file__).parent.parent.parent


class MCPToolBridge:
    """
    MCP 工具桥接器
    - 启动 MCP Server 子进程
    - 发现并缓存工具列表
    - 将 MCP 工具转换为 LangChain 兼容的工具函数
    """

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self._exit_stack = AsyncExitStack()
        self._tools: List[dict] = []
        self._langchain_tools: List = []
        self._connected = False

    async def connect(self):
        """建立与 MCP Server 的连接"""
        if self._connected:
            return

        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "src.mcp.lab_server"],
            env=None,
        )

        # 启动 MCP Server 子进程
        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read_stream, write_stream = stdio_transport

        # 创建会话
        self.session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        # 初始化握手
        await self.session.initialize()

        # 发现工具
        result = await self.session.list_tools()
        self._tools = [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema or {},
            }
            for t in result.tools
        ]

        self._connected = True
        print(f"[MCP Client] Connected to server, discovered {len(self._tools)} tools", file=sys.stderr)
        for t in self._tools:
            print(f"  - {t['name']}: {t['description'][:60]}...", file=sys.stderr)

    async def disconnect(self):
        """断开连接"""
        if self._exit_stack:
            await self._exit_stack.aclose()
        self._connected = False
        self._tools = []

    async def call_tool(self, name: str, arguments: dict) -> str:
        """调用 MCP Server 上的工具"""
        if not self._connected:
            await self.connect()

        result = await self.session.call_tool(name, arguments=arguments)
        # 提取文本内容
        if result.content:
            return result.content[0].text
        return json.dumps({"error": "No content returned from tool"})

    def get_tools_as_langchain(self) -> List:
        """
        将 MCP 工具动态转换为 LangChain @tool 函数
        这样 Agent 就能像使用本地工具一样使用 MCP 工具
        """
        if self._langchain_tools:
            return self._langchain_tools

        for mt in self._tools:
            name = mt["name"]
            desc = mt["description"]
            schema = mt["input_schema"]

            # 动态创建 LangChain tool
            # 使用闭包捕获 name
            def make_tool_func(tool_name):
                def tool_func(**kwargs) -> str:
                    """MCP tool wrapper - 处理 event loop 冲突"""
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop and loop.is_running():
                        # 已有运行中的 event loop，用线程池执行
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(lambda: asyncio.run(self.call_tool(tool_name, kwargs)))
                            return future.result(timeout=60)
                    else:
                        return asyncio.run(self.call_tool(tool_name, kwargs))

                return tool_func

            fn = make_tool_func(name)

            # 构建 args_schema（从 JSON Schema 转 Pydantic）
            from pydantic import create_model, Field

            props = schema.get("properties", {})
            required = schema.get("required", [])

            fields = {}
            for prop_name, prop_info in props.items():
                prop_type = prop_info.get("type", "string")
                prop_desc = prop_info.get("description", "")
                is_required = prop_name in required

                py_type = {"string": str, "integer": int, "number": float, "boolean": bool}.get(prop_type, str)

                if is_required:
                    fields[prop_name] = (py_type, Field(description=prop_desc))
                else:
                    fields[prop_name] = (Optional[py_type], Field(default=None, description=prop_desc))

            # 如果没有属性，使用空模型
            if not fields:
                from pydantic import BaseModel
                ArgsModel = BaseModel
            else:
                ArgsModel = create_model(f"{name}_args", **fields)

            # 创建 LangChain tool
            # 创建 LangChain tool（兼容不同版本）
            try:
                lc_tool = langchain_tool(name=name, description=desc, args_schema=ArgsModel if fields else None)(fn)
            except TypeError:
                try:
                    lc_tool = langchain_tool(fn, name=name, description=desc)
                except TypeError:
                    lc_tool = langchain_tool(fn)
                    lc_tool.name = name
                    lc_tool.description = desc
            self._langchain_tools.append(lc_tool)

        return self._langchain_tools

    @property
    def tool_names(self) -> List[str]:
        return [t["name"] for t in self._tools]

    @property
    def is_connected(self) -> bool:
        return self._connected


# ============================================
# 全局单例
# ============================================
_mcp_bridge: Optional[MCPToolBridge] = None


def get_mcp_bridge() -> MCPToolBridge:
    """获取 MCP 桥接器单例"""
    global _mcp_bridge
    if _mcp_bridge is None:
        _mcp_bridge = MCPToolBridge()
    return _mcp_bridge


async def init_mcp_connection() -> MCPToolBridge:
    """初始化 MCP 连接（异步）"""
    bridge = get_mcp_bridge()
    if not bridge.is_connected:
        await bridge.connect()
    return bridge


def init_mcp_sync() -> Optional[MCPToolBridge]:
    """同步初始化 MCP 连接"""
    try:
        bridge = get_mcp_bridge()
        if not bridge.is_connected:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(bridge.connect())
            loop.close()
        return bridge
    except Exception as e:
        print(f"[MCP Client] Failed to connect: {e}", file=sys.stderr)
        return None
