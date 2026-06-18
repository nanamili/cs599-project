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
    # LangChain 空字符串会被忽略，必须注入环境变量
    if api_key and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = api_key
    return ChatOpenAI(
        model=model, api_key=api_key or "dummy", base_url=base_url, temperature=temperature,
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
    """MCP 加载：本地可用，云环境有 event loop 冲突自动跳过"""
    global _mcp_tools_loaded, _mcp_scheduler_tools, _mcp_qa_tools, _mcp_monitor_tools
    if _mcp_tools_loaded: return
    _mcp_tools_loaded = True
    # 云环境检测：asyncio 有运行中的 loop → MCP 工具调用会崩，直接走内置
    import asyncio as _asyncio
    try:
        loop = _asyncio.get_running_loop()
        if loop.is_running():
            raise RuntimeError("Running event loop detected")
    except RuntimeError:
        _mcp_scheduler_tools = None; _mcp_qa_tools = None; _mcp_monitor_tools = None
        return
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
                print(f"[MCP] Running via MCP: {len(all_mcp)} tools", file=sys.stderr)
                return
    except Exception as e:
        print(f"[MCP] Fallback to built-in: {e}", file=sys.stderr)
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
    import re
    # 传全部对话历史（子Agent需要上下文）
    for m in msgs:
        if isinstance(m, (HumanMessage, AIMessage)):
            input_msgs.append(m)

    # 防列表死循环：纯数字回复 + AI刚列过仪器 → 替换prompt推进
    last_human = [m for m in msgs if isinstance(m, HumanMessage)]
    last_ai = [m for m in msgs if isinstance(m, AIMessage)]
    prev_listed = last_ai and any(w in (last_ai[-1].content or "") for w in ["回复编号","仪器列表"])
    if prev_listed and last_human and re.match(r'^\s*[1-5①②③④⑤]\s*$', last_human[-1].content.strip()):
        eq_names = ["透射电镜","ICP-MS","HPC集群","XRD","NMR"]
        try:
            idx = int(last_human[-1].content.strip().replace("①","1").replace("②","2").replace("③","3").replace("④","4").replace("⑤","5")) - 1
            input_msgs[0] = SystemMessage(content=f"用户选择了{idx+1}号：{eq_names[idx]}。只回复：'✅ 已选 {eq_names[idx]}（费用X元/h，最长Xh）。请告诉我日期和时间？' 禁止列清单！")
        except: pass

    # 防第三步回退：AI问了时间+用户提供了时间 → 代码层调 check_availability
    prev_asked_time = last_ai and ("日期和时间" in (last_ai[-1].content or "") or "几点" in (last_ai[-1].content or ""))
    if not prev_listed and prev_asked_time and last_human and len(last_human[-1].content.strip()) > 2:
        from datetime import date as _dt, timedelta as _td
        from src.tools.booking_tools import check_availability as _ca
        user_text = last_human[-1].content.strip(); today = _dt.today()
        week_map = {"周一":0,"周二":1,"周三":2,"周四":3,"周五":4,"周六":5,"周日":6}
        wm = re.search(r'(下?周[一二三四五六日])', user_text)
        if wm:
            target_wd = week_map.get(wm.group(1).replace("下",""), 0)
            days_ahead = (target_wd - today.weekday()) % 7
            if days_ahead == 0: days_ahead = 7
            if "下" in wm.group(1) and days_ahead <= 3: days_ahead += 7
            target_date = today + _td(days=days_ahead)
        elif "明天" in user_text: target_date = today + _td(days=1)
        elif "后天" in user_text: target_date = today + _td(days=2)
        elif "今天" in user_text: target_date = today
        else:
            dm = re.search(r'(\d{4}-\d{2}-\d{2})', user_text)
            target_date = _dt.fromisoformat(dm.group(1)) if dm else today
        # 判断上下午
        is_pm = "下午" in user_text or "晚上" in user_text or "傍晚" in user_text
        hour_map = {"零":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,"十一":11,"十二":12,"十三":13,"十四":14,"十五":15,"十六":16,"十七":17,"十八":18,"十九":19,"二十":20,"二十一":21,"二十二":22,"二十三":23}
        times = re.findall(r'([零一二三四五六七八九十]+)点', user_text)
        if len(times) >= 2:
            sh = hour_map.get(times[0], 9); eh = hour_map.get(times[1], 12)
            if is_pm: sh += 12; eh += 12
        else:
            shm = re.search(r'(\d{1,2})\s*[:：点]', user_text)
            sh = int(shm.group(1)) if shm else 9
            if is_pm and sh < 12: sh += 12
            ehm = re.search(r'到\s*(\d{1,2})', user_text); eh = int(ehm.group(1)) if ehm else sh + 3
            if is_pm and eh < 12: eh += 12
        dur = eh - sh
        # 从对话历史提取已选仪器
        equip_name = None
        for m in reversed(msgs):
            if isinstance(m, AIMessage) and m.content and "已选" in m.content:
                for en in ["透射电镜","ICP-MS","HPC集群","XRD","NMR","JEM","Agilent","StarCluster","Bruker"]:
                    if en in m.content: equip_name = en; break
                if equip_name: break
        if equip_name:
            from src.database.db import get_session as _gs2
            from src.database.models import Equipment as _Eq2
            s2 = _gs2(); eq2 = s2.query(_Eq2).filter(_Eq2.name.contains(equip_name[:6])).first(); s2.close()
            if eq2:
                av = _ca(eq2.id, str(target_date), sh, dur)
                if av.get("available"):
                    # 从用户上下文解析 uid
                    uid = 1
                    uid_m2 = re.search(r'ID[：:]\s*(\d+)', user_ctx) if user_ctx else None
                    if uid_m2: uid = int(uid_m2.group(1))
                    # 检查用户自身时间冲突
                    from src.database.models import Booking as _Bk
                    s3 = _gs2(); user_bks = s3.query(_Bk).filter(
                        _Bk.user_id == uid, _Bk.booking_date == target_date,
                        _Bk.status == "已确认", _Bk.equipment_id != eq2.id).all(); s3.close()
                    user_conflict = False
                    for ub in user_bks:
                        ub_e = ub.start_hour + ub.duration_hours
                        if sh < ub_e and eh > ub.start_hour:
                            user_conflict = True; break
                    if user_conflict:
                        out = f"❌ {target_date} {sh:02d}:00-{eh:02d}:00 不可用：您在该时段已有其他预约，不能同时预约多台仪器"
                    else:
                        cost = eq2.hourly_cost * dur
                        out = f"✅ {eq2.name} {target_date} {sh:02d}:00-{eh:02d}:00 可用。费用：{eq2.hourly_cost}元/h × {dur}h = {cost}元。确认预约吗？"
                else:
                    out = f"❌ {target_date} {sh:02d}:00-{eh:02d}:00 不可用：{av.get('error','时段冲突')}"
                    from src.tools.booking_tools import suggest_alternatives as _sa
                    alts = _sa(eq2.id, str(target_date), dur)
                    if alts: out += "\n\n替代方案：\n" + "\n".join(f"· {a.get('equipment_name','')} {a.get('date','')} {a.get('start_hour',''):02d}:00 ({a.get('type','')})" for a in alts[:3])
                return {"scheduler_result": out}

    # 防确认死循环：确认词检测 → 直接代码层调 create_booking，不走 LLM
    confirm_words = ["是","对","嗯","好","行","可","确认","yes","ok","确定","可以","要得"]
    last_human = [m for m in msgs if isinstance(m, HumanMessage)]
    is_confirm = last_human and any(w in last_human[-1].content.strip() for w in confirm_words)
    prev_asked = any(isinstance(m, AIMessage) and m.content and "确认" in m.content for m in msgs[-4:])

    if is_confirm and prev_asked:
        # 从 AI 确认消息中提取参数（确认消息最准确，含日期+时间+仪器）
        import re
        confirm_msg = last_ai[-1].content if last_ai else ""
        all_text = " ".join([m.content for m in msgs if hasattr(m, 'content') and m.content])
        # 日期：从 AI 确认消息提取
        date_m = re.search(r'(\d{4}-\d{2}-\d{2})', confirm_msg)
        # 时段：从确认消息提取 "10:00-12:00"
        slot_m = re.search(r'(\d{1,2}):00\s*[-–—]\s*(\d{1,2}):00', confirm_msg)
        if slot_m:
            sh = int(slot_m.group(1)); eh = int(slot_m.group(2))
            dur = eh - sh
        else:
            times = re.findall(r'(\d{1,2}):00', confirm_msg)
            hours_list = [int(t) for t in times]
            sh = min(hours_list) if hours_list else 9
            dur = (max(hours_list) - min(hours_list) + 1) if hours_list else 2
        # 仪器
        equip_m = re.search(r'(JEM-2100F|Agilent 7900|StarCluster|Bruker D8|Bruker 600MHz)', confirm_msg)
        if not equip_m:
            equip_m = re.search(r'(JEM-2100F|Agilent 7900|StarCluster|Bruker D8|Bruker 600MHz)', all_text)
        # 用户ID
        uid_m = re.search(r'ID[：:]\s*(\d+)', all_text)
        if date_m and equip_m:
            from src.database.db import get_session as _gs
            from src.database.models import Equipment as _Eq
            s = _gs()
            eq = s.query(_Eq).filter(_Eq.name.contains(equip_m.group(1)[:8])).first()
            s.close()
            if eq:
                uid = int(uid_m.group(1)) if uid_m else 1
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
    """调用 QA 子 Agent"""
    msgs = state["messages"]; input_msgs = [SystemMessage(content=QA_SYSTEM)]
    for m in msgs:
        if isinstance(m, (HumanMessage, AIMessage)):
            input_msgs.append(m)
    agent = _get_subagent("qa")
    result = agent.invoke({"messages": input_msgs, "react_steps": 0})
    out = "";
    for m in reversed(result["messages"]):
        if isinstance(m, AIMessage) and m.content and not (hasattr(m, 'tool_calls') and m.tool_calls):
            out = m.content; break
        if not out and isinstance(m, AIMessage) and m.content: out = m.content; break
    return {"qa_result": out or "仪器顾问未返回结果"}

def _dispatch_monitor(state: AgentState) -> dict:
    """调用 Monitor 子 Agent"""
    msgs = state["messages"]; input_msgs = [SystemMessage(content=MONITOR_SYSTEM)]
    for m in msgs:
        if isinstance(m, (HumanMessage, AIMessage)):
            input_msgs.append(m)
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
