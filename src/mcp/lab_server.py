"""
MCP Server — 实验室仪器管理工具服务
将 11 个业务工具以 MCP 协议标准化暴露，支持热插拔

启动方式:
    python -m src.mcp.lab_server              # stdio 模式 (本地)
    python -m src.mcp.lab_server --transport sse --port 8765  # SSE 模式 (远程)
"""

import sys, json, os, io
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# ⚠️ MCP 使用 stdout 传输 JSONRPC，禁止任何 print 污染 stdout
# 把初始化期间的 stdout 重定向到 stderr
_real_stdout = sys.stdout
sys.stdout = sys.stderr

from mcp.server import FastMCP

# 初始化数据库和知识库
from src.database.db import init_db, get_session
from src.database.seed import seed_all
init_db()
session = get_session()
seed_all(session)
session.close()

from src.rag.retriever import init_knowledge_base
init_knowledge_base()

# 恢复 stdout（FastMCP 需要它传输 JSONRPC）
sys.stdout = _real_stdout
print(f"[MCP Server] Initialized: 5 equipment, 22 SOP chunks", file=sys.stderr)

# ============================================
# MCP Server 实例
# ============================================
mcp = FastMCP("LabAgent MCP Server")


# ============================================
# 仪器查询工具
# ============================================

@mcp.tool()
def get_equipment_list(category: Optional[str] = None) -> str:
    """
    获取所有可用仪器列表。
    参数 category 可选过滤：显微镜 / 光谱仪 / 计算资源 / 衍射仪 / 其他
    返回 JSON 格式的仪器列表，含 ID、名称、位置、证书要求、费用等信息。
    """
    from src.tools.booking_tools import get_equipment_list as _fn
    return json.dumps(_fn(category), ensure_ascii=False, indent=2)


@mcp.tool()
def get_equipment_detail(equipment_id: int) -> str:
    """
    获取指定仪器的详细信息。
    参数 equipment_id: 仪器ID（1=透射电镜, 2=ICP-MS, 3=HPC, 4=XRD, 5=NMR）
    返回包含位置、证书等级要求、最长预约时长、机时费的完整信息。
    """
    from src.tools.booking_tools import get_equipment_detail as _fn
    result = _fn(equipment_id)
    return json.dumps(result, ensure_ascii=False, indent=2) if result else f"仪器 ID={equipment_id} 不存在"


# ============================================
# 预约管理工具
# ============================================

@mcp.tool()
def check_availability(equipment_id: int, check_date: str, start_hour: int, duration_hours: int) -> str:
    """
    检查指定仪器在目标时间段是否可用。
    参数:
      - equipment_id: 仪器 ID
      - check_date: 日期 (YYYY-MM-DD)
      - start_hour: 开始小时 (0-23)
      - duration_hours: 持续时长
    返回可用性状态及冲突详情。
    """
    from src.tools.booking_tools import check_availability as _fn
    return json.dumps(_fn(equipment_id, check_date, start_hour, duration_hours), ensure_ascii=False, indent=2)


@mcp.tool()
def create_booking(equipment_id: int, user_id: int, booking_date: str,
                   start_hour: int, duration_hours: int, purpose: str = "") -> str:
    """
    创建仪器预约，自动执行冲突检测和资质验证。
    参数: equipment_id, user_id(1=张三 2=李四 3=王五), booking_date(YYYY-MM-DD),
          start_hour(0-23), duration_hours, purpose(使用目的)
    """
    from src.tools.booking_tools import create_booking as _fn
    return json.dumps(_fn(equipment_id, user_id, booking_date, start_hour, duration_hours, purpose),
                      ensure_ascii=False, indent=2)


@mcp.tool()
def suggest_alternatives(equipment_id: int, target_date: str, duration_hours: int) -> str:
    """
    当预约冲突时推荐替代方案（同天其他时段 → 邻近日期 → 同类仪器）。
    """
    from src.tools.booking_tools import suggest_alternatives as _fn
    return json.dumps(_fn(equipment_id, target_date, duration_hours), ensure_ascii=False, indent=2)


@mcp.tool()
def get_user_bookings(user_id: int) -> str:
    """获取指定用户最近 20 条预约记录。"""
    from src.tools.booking_tools import get_user_bookings as _fn
    return json.dumps(_fn(user_id), ensure_ascii=False, indent=2)


@mcp.tool()
def cancel_booking(booking_id: int) -> str:
    """取消指定预约（仅限'已确认'状态的预约）。"""
    from src.tools.booking_tools import cancel_booking as _fn
    return json.dumps(_fn(booking_id), ensure_ascii=False, indent=2)


# ============================================
# RAG 知识检索工具
# ============================================

@mcp.tool()
def search_equipment_sop(query: str, top_k: int = 3) -> str:
    """
    在仪器 SOP 知识库中语义检索操作规范。
    适用查询: "电镜样品制备步骤"、"ICP-MS安全注意事项"、"HPC GPU作业提交"
    返回相关文档块，含来源标注和相关度评分。
    """
    from src.tools.rag_tools import search_equipment_sop as _fn
    return json.dumps(_fn(query, top_k), ensure_ascii=False, indent=2)


@mcp.tool()
def get_sop_summary(equipment_name: str) -> str:
    """
    获取指定仪器的 SOP 摘要，提取安全须知和预约规则。
    参数: 仪器名称关键词，如 "透射电镜"、"ICP-MS"、"HPC集群"
    """
    from src.tools.rag_tools import get_sop_summary as _fn
    return json.dumps(_fn(equipment_name), ensure_ascii=False, indent=2)


# ============================================
# 监控工具
# ============================================

@mcp.tool()
def check_anomalies(days: int = 7) -> str:
    """
    扫描系统异常（爽约、未持证操作、高频预约），按严重程度分级。
    参数 days: 检测最近 N 天（默认 7）
    """
    from src.tools.monitor_tools import check_anomalies as _fn
    return json.dumps(_fn(days), ensure_ascii=False, indent=2)


@mcp.tool()
def generate_usage_stats(equipment_id: Optional[int] = None, days: int = 30) -> str:
    """
    生成仪器使用统计报告：总预约数、总机时、热门仪器排名、爽约率。
    参数 equipment_id: 可选，指定仪器 ID（None=全部）
    """
    from src.tools.monitor_tools import generate_usage_stats as _fn
    stats = _fn(equipment_id, days)
    return json.dumps(stats, ensure_ascii=False, indent=2, default=str)


# ============================================
# 安全事件知识库工具
# ============================================

@mcp.tool()
def get_safety_incidents(equipment: str = "", category: str = "", severity: str = "", limit: int = 5) -> str:
    """
    检索实验室安全事故案例库。支持中文缩写如 "电镜"→"电子显微镜"、"TEM"→"透射电镜"。
    参数 equipment/category/severity 用于过滤，空=全部。limit 默认 5。
    """
    from src.tools.monitor_tools import get_safety_incidents as _fn
    results = _fn(equipment, category, severity, limit)
    # 精简输出
    short = []
    for inc in results:
        short.append({
            "id": inc["id"], "date": inc["date"], "title": inc["title"],
            "equipment": inc["equipment"], "severity": inc["severity"],
            "cause": inc["cause"], "penalty": inc["penalty"], "lesson": inc["lesson"],
        })
    return json.dumps(short, ensure_ascii=False, indent=2)


# ============================================
# MCP 资源 (Resources) — 提供上下文数据
# ============================================

@mcp.resource("equipment://list")
def get_equipment_resource() -> str:
    """以资源形式暴露仪器列表"""
    from src.tools.booking_tools import get_equipment_list as _fn
    return json.dumps(_fn(), ensure_ascii=False)


@mcp.resource("stats://overview")
def get_stats_resource() -> str:
    """以资源形式暴露系统概览"""
    from src.tools.monitor_tools import generate_usage_stats as _fn, check_anomalies as _ca
    return json.dumps({
        "equipment_count": 5,
        "active_bookings": _fn(days=7).get("total_bookings", 0),
        "pending_anomalies": len(_ca(days=7)),
        "status": "healthy",
    }, ensure_ascii=False)


# ============================================
# 入口
# ============================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LabAgent MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    print(f"[MCP] LabAgent MCP Server starting (transport={args.transport})...", file=sys.stderr)

    if args.transport == "sse":
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run(transport="stdio")
