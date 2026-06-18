"""
LangGraph 多智能体协作图 v3 — 多 Agent 独立子图架构
架构:
    START → supervisor (意图分类 + 按需派发)
                │
        ┌───────┼──────────┐
        ↓       ↓           ↓
    scheduler  qa        monitor   ← 独立子图，按意图路由，各自 ReAct
        │       │           │
        └───────┼──────────┘
                ↓
            finalize (整合)
                ↓
               END
"""

import json, os, sys
from typing import TypedDict, List, Literal, Annotated, Optional, Any
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import (
    HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from src.agents.prompts import (
    SUPERVISOR_SYSTEM, SCHEDULER_SYSTEM, QA_SYSTEM, MONITOR_SYSTEM, INTENT_CLASSIFIER
)
from src.tools.booking_tools import (
    get_equipment_list, get_equipment_detail,
    check_availability, create_booking,
    detect_conflict, suggest_alternatives,
    get_user_bookings, cancel_booking,
)
from src.tools.rag_tools import search_equipment_sop, get_sop_summary
from src.tools.monitor_tools import (
    check_anomalies, generate_usage_stats, get_violation_history,
    get_safety_incidents,
)

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ============================================
# 🔧 Tool 定义
# ============================================

@tool
def tool_get_equipment_list(category: Optional[str] = None) -> str:
    """获取所有可用仪器的列表。可按类别过滤：显微镜/光谱仪/计算资源/衍射仪/其他"""
    return json.dumps(get_equipment_list(category), ensure_ascii=False, indent=2)

@tool
def tool_get_equipment_detail(equipment_id: int) -> str:
    """获取指定仪器的完整信息：位置、证书要求、最长预约时长、每小时费用、当前状态"""
    result = get_equipment_detail(equipment_id)
    return json.dumps(result, ensure_ascii=False, indent=2) if result else f"仪器ID={equipment_id}不存在"

@tool
def tool_check_availability(equipment_id: int, check_date: str, start_hour: int, duration_hours: int) -> str:
    """检查仪器在指定时间段是否可用。参数：equipment_id, check_date(YYYY-MM-DD), start_hour(0-23), duration_hours"""
    return json.dumps(check_availability(equipment_id, check_date, start_hour, duration_hours), ensure_ascii=False, indent=2)

@tool
def tool_create_booking(equipment_id: int, user_id: int, booking_date: str,
                        start_hour: int, duration_hours: int, purpose: str = "") -> str:
    """创建仪器预约。自动执行冲突检测和资质验证。参数：equipment_id, user_id, booking_date(YYYY-MM-DD), start_hour(0-23), duration_hours, purpose"""
    return json.dumps(create_booking(equipment_id, user_id, booking_date, start_hour, duration_hours, purpose), ensure_ascii=False, indent=2)

@tool
def tool_suggest_alternatives(equipment_id: int, target_date: str, duration_hours: int) -> str:
    """当预约冲突时自动推荐替代方案。按优先级：①同天其他空闲时段 → ②前后3天 → ③同类仪器"""
    return json.dumps(suggest_alternatives(equipment_id, target_date, duration_hours), ensure_ascii=False, indent=2)

@tool
def tool_search_sop(query: str) -> str:
    """在仪器SOP知识库中语义检索操作规范。适用查询示例：'电镜样品制备步骤'、'ICP-MS安全注意事项'"""
    results = search_equipment_sop(query, top_k=3)
    return json.dumps(results, ensure_ascii=False, indent=2)

@tool
def tool_get_sop_summary(equipment_name: str) -> str:
    """获取指定仪器的SOP摘要，提取安全须知和预约规则。"""
    return json.dumps(get_sop_summary(equipment_name), ensure_ascii=False, indent=2)

@tool
def tool_check_anomalies(days: int = 7) -> str:
    """检测系统异常：爽约记录、未持证操作、高频预约。按严重程度分为 高/中/低 三级"""
    anomalies = check_anomalies(days)
    return json.dumps(anomalies, ensure_ascii=False, indent=2)

@tool
def tool_generate_usage_stats(equipment_id: Optional[int] = None, days: int = 30) -> str:
    """生成仪器使用统计报告：总预约数、总机时、热门仪器、爽约率"""
    stats = generate_usage_stats(equipment_id, days)
    stats_safe = json.loads(json.dumps(stats, ensure_ascii=False, default=str))
    return json.dumps(stats_safe, ensure_ascii=False, indent=2)

@tool
def tool_get_safety_incidents(equipment: str = "", category: str = "", severity: str = "", limit: int = 3) -> str:
    """检索实验室安全事故案例库。当检测到用户违规时调用此工具，引用真实事故案例作为警示。"""
    incidents = get_safety_incidents(equipment, category, severity, limit)
    return json.dumps(incidents, ensure_ascii=False, indent=2)

@tool
def tool_get_user_bookings(user_id: int) -> str:
    """查看指定用户的所有预约记录（最近20条）"""
    return json.dumps(get_user_bookings(user_id), ensure_ascii=False, indent=2)

@tool
def tool_cancel_booking(booking_id: int) -> str:
    """取消指定预约（仅限'已确认'状态的预约）"""
    return json.dumps(cancel_booking(booking_id), ensure_ascii=False, indent=2)


# ============================================
# 🛠️ 工具集分组（每个 Agent 独立）
# ============================================
SCHEDULER_TOOLS = [
    tool_get_equipment_list, tool_get_equipment_detail,
    tool_check_availability, tool_create_booking,
    tool_suggest_alternatives, tool_get_user_bookings, tool_cancel_booking,
]
QA_TOOLS = [tool_search_sop, tool_get_sop_summary, tool_get_equipment_detail]
MONITOR_TOOLS = [tool_check_anomalies, tool_generate_usage_stats, tool_get_safety_incidents]
ALL_TOOLS = SCHEDULER_TOOLS + QA_TOOLS + MONITOR_TOOLS


# ============================================
# 🏗️ State 定义
# ============================================

def _dedup_trace(existing: List[dict], incoming: List[dict]) -> List[dict]:
    seen = set(); result = []
    for t in existing + incoming:
        key = (t.get("agent",""), t.get("action",""), str(t.get("detail",""))[:80])
        if key not in seen: seen.add(key); result.append(t)
    return result[-60:]

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]
    intent: str
    active_agents: List[str]       # 需要调用的 Agent 列表
    user_context: str
    agent_trace: Annotated[List[dict], _dedup_trace]
    # 各 Agent 独立结果
    scheduler_result: str
    qa_result: str
    monitor_result: str
    final_response: str

MAX_REACT_STEPS = 8


def _get_llm(temperature: float = 0.2):
    api_key = ""; base_url = ""; model = ""
    try:
        import streamlit as _st
        api_key = _st.secrets.get("DEEPSEEK_API_KEY", "")
        base_url = _st.secrets.get("DEEPSEEK_BASE_URL", "")
        model = _st.secrets.get("DEEPSEEK_MODEL", "")
    except: pass
    if not api_key:
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not base_url:
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    if not model:
        model = os.getenv("DEEPSEEK_MODEL", "qwen3-max")
    if not api_key:
        raise RuntimeError("未找到 API Key！请在 Streamlit Cloud Secrets 中设置 DEEPSEEK_API_KEY")
    return ChatOpenAI(
        model=model, api_key=api_key, base_url=base_url, temperature=temperature,
    )


# ============================================
# 🔀 Supervisor 节点 — 意图分类 + 按需派发
# ============================================

def supervisor_node(state: AgentState) -> dict:
    """Supervisor：分析用户意图，决定需要调用哪些子 Agent"""
    last_msg = state["messages"][-1]
    user_text = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

    # 构建对话上下文
    recent = ""
    for m in state.get("messages", [])[-6:]:
        role = "用户" if isinstance(m, HumanMessage) else "助手" if isinstance(m, AIMessage) else ""
        if role and hasattr(m, 'content') and m.content:
            recent += f"{role}: {m.content[:200]}\n"

    llm = _get_llm(temperature=0)
    classification = llm.invoke([
        SystemMessage(content=INTENT_CLASSIFIER),
        HumanMessage(content=f"对话历史:\n{recent}\n\n最新消息: {user_text}"),
    ])

    try:
        content = classification.content.strip()
        if "```json" in content: content = content.split("```json")[1].split("```")[0]
        elif "```" in content: content = content.split("```")[1].split("```")[0]
        intent_data = json.loads(content)
        primary = intent_data.get("primary", "scheduler")
    except Exception:
        primary = "scheduler"
        for kw, it in [("预约","scheduler"),("怎么","qa"),("如何","qa"),("SOP","qa"),
                       ("安全","qa"),("异常","monitor"),("违规","monitor"),("统计","monitor"),
                       ("检查","monitor"),("取消","scheduler")]:
            if kw in user_text: primary = it; break

    # 决定需要哪些 Agent（目前单意图用一个，复杂意图可扩展为多个）
    agents = [primary]

    trace = [{"agent": "🏠 Supervisor", "action": "意图分类 + 派发",
              "detail": f"调用: {agents}"}]

    user_ctx = state.get("user_context", "")
    # 保留原有消息，追加 Supervisor 上下文
    existing = state.get("messages", [])
    return {
        "intent": primary,
        "active_agents": agents,
        "agent_trace": state.get("agent_trace", []) + trace,
        "messages": existing + [SystemMessage(content=f"[Supervisor: route to {primary}] {user_ctx}")],
    }


def route_to_agents(state: AgentState) -> List[str]:
    """根据 active_agents 返回需要执行的子 Agent 节点名"""
    agents = state.get("active_agents", ["scheduler"])
    return agents


# ============================================
# 📅 Scheduler Agent 子图（独立 ReAct）
# ============================================

class SubAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]
    react_steps: int
    result: str

def _make_subagent_node(system_prompt: str, tools: list, agent_name: str):
    """工厂函数：创建子 Agent 的 think 节点"""
    def think_node(state: SubAgentState) -> dict:
        llm = _get_llm(temperature=0.3)
        llm_bound = llm.bind_tools(tools)
        msgs = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in msgs):
            msgs = [SystemMessage(content=system_prompt)] + msgs
        try:
            resp = llm_bound.invoke(msgs)
        except Exception as e:
            return {"messages": [AIMessage(content=f"处理出错: {e}")], "react_steps": state.get("react_steps",0)+1}
        return {"messages": [resp], "react_steps": state.get("react_steps", 0) + 1}

    def should_continue(state: SubAgentState) -> Literal["tools", "done"]:
        steps = state.get("react_steps", 0)
        if steps >= MAX_REACT_STEPS: return "done"
        last = state["messages"][-1] if state["messages"] else None
        if last and hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "done"

    return think_node, should_continue


def build_subagent(system_prompt: str, tools: list, name: str) -> StateGraph:
    """构建一个子 Agent 的 LangGraph（独立 ReAct 循环）"""
    g = StateGraph(SubAgentState)
    think_node, should_continue = _make_subagent_node(system_prompt, tools, name)
    g.add_node("think", think_node)
    g.add_node("tools", ToolNode(tools))
    g.set_entry_point("think")
    g.add_conditional_edges("think", should_continue, {"tools": "tools", "done": END})
    g.add_edge("tools", "think")
    return g.compile()


# MCP 工具动态加载
_mcp_tools_loaded = False
_mcp_scheduler_tools = None
_mcp_qa_tools = None
_mcp_monitor_tools = None

def _init_mcp_tools():
    """尝试通过 MCP 协议加载工具，成功则覆盖内置工具"""
    global _mcp_tools_loaded, _mcp_scheduler_tools, _mcp_qa_tools, _mcp_monitor_tools
    if _mcp_tools_loaded: return
    _mcp_tools_loaded = True
    try:
        from src.mcp.mcp_client import init_mcp_sync, get_mcp_bridge
        bridge = init_mcp_sync()
        if bridge and bridge.is_connected:
            all_mcp = bridge.get_tools_as_langchain()
            if all_mcp:
                s_names = {t.name.replace('tool_','') for t in SCHEDULER_TOOLS}
                q_names = {t.name.replace('tool_','') for t in QA_TOOLS}
                m_names = {t.name.replace('tool_','') for t in MONITOR_TOOLS}
                _mcp_scheduler_tools = [t for t in all_mcp if t.name in s_names]
                _mcp_qa_tools = [t for t in all_mcp if t.name in q_names]
                _mcp_monitor_tools = [t for t in all_mcp if t.name in m_names]
                print(f"[MCP] Agent 运行时已接入 MCP: {len(all_mcp)} tools (S:{len(_mcp_scheduler_tools)} Q:{len(_mcp_qa_tools)} M:{len(_mcp_monitor_tools)})", file=sys.stderr)
                return
    except Exception as e:
        print(f"[MCP] 回退到内置 Function Calling: {e}", file=sys.stderr)
    _mcp_scheduler_tools = None; _mcp_qa_tools = None; _mcp_monitor_tools = None

def _get_agent_tools(agent_type: str):
    """获取指定 Agent 的工具（MCP 优先，内置回退）"""
    _init_mcp_tools()
    if agent_type == "scheduler":
        return _mcp_scheduler_tools if _mcp_scheduler_tools else SCHEDULER_TOOLS
    elif agent_type == "qa":
        return _mcp_qa_tools if _mcp_qa_tools else QA_TOOLS
    else:
        return _mcp_monitor_tools if _mcp_monitor_tools else MONITOR_TOOLS

# 预编译三个子 Agent（每次动态构建以支持 MCP 热切换）
def _get_subagent(agent_type: str):
    prompts = {"scheduler": SCHEDULER_SYSTEM, "qa": QA_SYSTEM, "monitor": MONITOR_SYSTEM}
    return build_subagent(prompts[agent_type], _get_agent_tools(agent_type), agent_type)


# ============================================
# 🔀 主 Graph
# ============================================

def _dispatch_scheduler(state: AgentState) -> dict:
    """调用 Scheduler 子 Agent（MCP 工具优先 + 防确认死循环）"""
    msgs = state["messages"]; user_ctx = state.get("user_context", "")
    prompt = SCHEDULER_SYSTEM
    if user_ctx: prompt += f"\n\n{user_ctx}"
    input_msgs = [SystemMessage(content=prompt)]
    for m in msgs:
        if isinstance(m, HumanMessage):
            input_msgs.append(m); break
    if not any(isinstance(m, HumanMessage) for m in input_msgs):
        input_msgs.append(HumanMessage(content="你好"))

    # 防死循环：确认词检测 → 直接代码层调 create_booking，不走 LLM
    confirm_words = ["是","对","嗯","好","行","可","确认","yes","ok","确定","可以","要得"]
    last_human = [m for m in msgs if isinstance(m, HumanMessage)]
    is_confirm = last_human and any(w in last_human[-1].content.strip() for w in confirm_words)
    prev_asked = any(isinstance(m, AIMessage) and m.content and "确认" in m.content for m in msgs[-4:])

    if is_confirm and prev_asked:
        # 直接解析参数调 create_booking，绕过 LLM
        import re
        # 只从最新一条用户消息中提取参数
        latest_human_text = last_human[-1].content if last_human else ""
        all_text = " ".join([m.content for m in msgs if hasattr(m, 'content') and m.content])
        # 解析日期（优先最新消息）
        date_m = re.search(r'(\d{4}-\d{2}-\d{2})', latest_human_text) or re.search(r'(\d{4}-\d{2}-\d{2})', all_text)
        # 解析时段（取每段的开始时间，排除结束时间）
        slots = re.findall(r'(\d{1,2}):00\s*[-–—]\s*\d{1,2}:00', latest_human_text)
        if not slots:
            slots = re.findall(r'(\d{1,2}):00\s*[-–—]\s*\d{1,2}:00', all_text)
        hours_list = [int(re.match(r'(\d+)', s).group(1)) for s in slots] if slots else []
        if not hours_list:
            times = re.findall(r'(\d{1,2}):00', latest_human_text) or re.findall(r'(\d{1,2}):00', all_text)
            hours_list = [int(t) for t in times]
        # 解析仪器（优先最新消息）
        equip_m = re.search(r'(JEM-2100F|Agilent 7900|StarCluster|Bruker D8|Bruker 600MHz)', latest_human_text)
        if not equip_m:
            equip_m = re.search(r'(JEM-2100F|Agilent 7900|StarCluster|Bruker D8|Bruker 600MHz)', all_text)
        # 解析用户ID
        uid_m = re.search(r'ID[：:]\s*(\d+)', all_text)
        if date_m and hours_list and equip_m:
            from src.database.db import get_session as _gs
            from src.database.models import Equipment as _Eq
            s = _gs()
            eq = s.query(_Eq).filter(_Eq.name.contains(equip_m.group(1)[:8])).first()
            s.close()
            if eq:
                uid = int(uid_m.group(1)) if uid_m else 1
                # 合并连续时段
                sh = min(hours_list)
                dur = max(hours_list) - min(hours_list) + 1
                from src.tools.booking_tools import create_booking as _cb
                r = _cb(eq.id, uid, date_m.group(1), sh, dur, "")
                if r.get("success"):
                    out = f"✅ 预约成功！\n\n仪器：{r.get('equipment_name','')}\n日期：{r.get('date','')}\n时段：{r.get('time_slot','')}\n费用：¥{r.get('estimated_cost',0):.0f}\n用户：{r.get('user_name','')}"
                else:
                    out = f"❌ 预约失败：{r.get('message','')}"
                    if r.get("suggested_alternatives"):
                        alts = r["suggested_alternatives"][:3]
                        out += "\n\n💡 替代方案：\n" + "\n".join(f"· {a.get('equipment_name','')} {a.get('date','')} {a.get('start_hour',''):02d}:00 ({a.get('type','')})" for a in alts)
                return {"scheduler_result": out}

    agent = _get_subagent("scheduler")
    result = agent.invoke({"messages": input_msgs, "react_steps": 0})
    out = ""
    for m in reversed(result["messages"]):
        if isinstance(m, AIMessage) and m.content and not (hasattr(m, 'tool_calls') and m.tool_calls):
            out = m.content; break
        if not out and isinstance(m, AIMessage) and m.content: out = m.content; break
    return {"scheduler_result": out or "排期专家未返回结果"}

def _dispatch_qa(state: AgentState) -> dict:
    """调用 QA 子 Agent（MCP 工具优先）"""
    msgs = state["messages"]; input_msgs = [SystemMessage(content=QA_SYSTEM)]
    for m in msgs:
        if isinstance(m, HumanMessage): input_msgs.append(m); break
    if not any(isinstance(m, HumanMessage) for m in input_msgs):
        input_msgs.append(HumanMessage(content="你好"))
    agent = _get_subagent("qa")
    result = agent.invoke({"messages": input_msgs, "react_steps": 0})
    out = "";
    for m in reversed(result["messages"]):
        if isinstance(m, AIMessage) and m.content and not (hasattr(m, 'tool_calls') and m.tool_calls):
            out = m.content; break
        if not out and isinstance(m, AIMessage) and m.content: out = m.content; break
    return {"qa_result": out or "仪器顾问未返回结果"}

def _dispatch_monitor(state: AgentState) -> dict:
    """调用 Monitor 子 Agent（MCP 工具优先）"""
    msgs = state["messages"]; input_msgs = [SystemMessage(content=MONITOR_SYSTEM)]
    for m in msgs:
        if isinstance(m, HumanMessage): input_msgs.append(m); break
    if not any(isinstance(m, HumanMessage) for m in input_msgs):
        input_msgs.append(HumanMessage(content="你好"))
    agent = _get_subagent("monitor")
    result = agent.invoke({"messages": input_msgs, "react_steps": 0})
    out = "";
    for m in reversed(result["messages"]):
        if isinstance(m, AIMessage) and m.content and not (hasattr(m, 'tool_calls') and m.tool_calls):
            out = m.content; break
        if not out and isinstance(m, AIMessage) and m.content: out = m.content; break
    return {"monitor_result": out or "监控哨兵未返回结果"}


def finalize_node(state: AgentState) -> dict:
    """整合所有 Agent 的结果"""
    intent = state.get("intent", "scheduler")
    result_map = {"scheduler": state.get("scheduler_result", ""),
                  "qa": state.get("qa_result", ""),
                  "monitor": state.get("monitor_result", "")}
    primary_result = result_map.get(intent, "")
    if not primary_result:
        primary_result = next((v for v in result_map.values() if v), "未能生成回复")

    return {
        "final_response": primary_result,
        "messages": [AIMessage(content=primary_result)],
        "agent_trace": state.get("agent_trace", []) + [{
            "agent": "🏠 Supervisor", "action": "✅ 多Agent整合完成",
            "detail": f"调度:{'Y' if result_map['scheduler'] else 'N'} 顾问:{'Y' if result_map['qa'] else 'N'} 监控:{'Y' if result_map['monitor'] else 'N'}"
        }],
    }


def build_graph() -> StateGraph:
    """构建多智能体协作主图"""
    w = StateGraph(AgentState)

    w.add_node("supervisor", supervisor_node)
    w.add_node("scheduler_agent", _dispatch_scheduler)
    w.add_node("qa_agent", _dispatch_qa)
    w.add_node("monitor_agent", _dispatch_monitor)
    w.add_node("finalize", finalize_node)

    w.set_entry_point("supervisor")

    # Supervisor → 各子 Agent（按意图路由）
    w.add_conditional_edges("supervisor", route_to_agents,
        {"scheduler": "scheduler_agent", "qa": "qa_agent", "monitor": "monitor_agent"})

    # 子 Agent → finalize
    w.add_edge("scheduler_agent", "finalize")
    w.add_edge("qa_agent", "finalize")
    w.add_edge("monitor_agent", "finalize")

    w.add_edge("finalize", END)
    return w


def create_agent():
    return build_graph().compile(checkpointer=MemorySaver())


# ============================================
# 🌊 流式 API
# ============================================

def run_with_stream(user_message: str, thread_id: str = "default", agent=None, user_context: str = ""):
    from src.rag.retriever import init_knowledge_base
    from src.database.db import init_db, get_session
    from src.database.seed import seed_all

    init_db(); s = get_session(); seed_all(s); s.close()
    init_knowledge_base()

    if agent is None: agent = create_agent()
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {"messages": [HumanMessage(content=user_message)]}
    if user_context: initial_state["user_context"] = user_context

    accumulated_trace = []; raw_output = ""

    for event in agent.stream(initial_state, config=config, stream_mode="updates"):
        for node_name, state_update in event.items():
            if "agent_trace" in state_update:
                accumulated_trace.extend(state_update["agent_trace"])
                yield {"type": "trace", "data": state_update["agent_trace"], "node": node_name}
            if node_name == "finalize" and "final_response" in state_update:
                raw_output = state_update["final_response"]

    if not raw_output: raw_output = "Agent 未返回有效结果。"

    full_text = raw_output
    for i, char in enumerate(full_text):
        yield {"type": "token", "data": char}
    yield {"type": "final", "data": full_text, "trace": accumulated_trace}


def run_agent(user_message: str, thread_id: str = "default", agent=None) -> dict:
    ft = ""; trace = []
    for chunk in run_with_stream(user_message, thread_id, agent=agent):
        if chunk["type"] == "token": ft += chunk["data"]
        elif chunk["type"] == "final":
            if not ft: ft = chunk["data"]
            trace = chunk.get("trace", [])
    return {"response": ft, "trace": trace}
