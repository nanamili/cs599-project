"""
LabAgent v3 — 完善面向用户的功能体验
智能实验室仪器共享预约平台 | CS599 期末大作业

交互亮点:
  - 消息气泡 + 时间戳 + 一键复制
  - Agent 思维步骤内联展开
  - 交互式预约卡片（点击即预约）
  - Plotly 甘特图 + 使用统计图
  - 侧边栏实时设备状态 + 快速操作
  - 异常报告 / 使用统计一键下载
"""

import sys, json, os, time
from pathlib import Path
from datetime import date, timedelta, datetime

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="LabAgent — 智能实验室管理平台",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "CS599 期末大作业 | LangGraph 多智能体 | Supervisor-Worker 架构"},
)

# ============================================================
# 🎨 全局 CSS
# ============================================================
st.markdown("""
<style>
/* ================================================================
   LabAgent — 全局样式
   ================================================================ */

/* —— 页面底色 + 字体 —— */
.stApp { background: #f8fafc; }
.main { background: #f8fafc; }
body, p, div, span, li { color: #334155; }

/* —— 侧边栏 —— */
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e2e8f0;
}
[data-testid="stSidebar"] .stMarkdown h3 { color: #1e293b; font-size: 0.95rem; }
[data-testid="stSidebar"] .stMarkdown p  { color: #64748b; font-size: 0.8rem; }
[data-testid="stSidebar"] hr { border-color: #e2e8f0; }
[data-testid="stSidebar"] button {
    border-radius: 8px !important; border: 1px solid #e2e8f0 !important;
    background: #fff !important; color: #334155 !important;
    font-size: 0.82rem !important; transition: all 0.15s;
}
[data-testid="stSidebar"] button:hover {
    border-color: #3b82f6 !important; background: #eff6ff !important;
}

/* —— 主内容区 —— */
.main .block-container { padding-top: 0.5rem; max-width: 1400px; }
hr { border-color: #e2e8f0; margin: 0.5rem 0; }

/* —— 头部 —— */
.hero {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #3b82f6 100%);
    border-radius: 16px; padding: 1.4rem 2rem; margin-bottom: 0.6rem;
    box-shadow: 0 4px 24px rgba(37,99,235,0.15);
}
.hero h1 { color: #ffffff !important; font-size: 1.5rem; margin: 0; font-weight: 700; }
.hero p  { color: #bfdbfe !important; font-size: 0.82rem; margin: 0.3rem 0 0 0; }

/* —— Tab 导航 —— */
.stTabs [data-baseweb="tab-list"] {
    gap: 0; background: #fff; border-radius: 12px;
    padding: 4px; border: 1px solid #e2e8f0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px; padding: 8px 20px; font-size: 0.85rem;
    color: #64748b; font-weight: 500; transition: all 0.15s;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: #eff6ff; color: #2563eb; font-weight: 600;
}

/* —— st.chat_message 美化 —— */
[data-testid="stChatMessage"] img, [data-testid="stChatMessage"] svg { display: none !important; }
[data-testid="stChatMessage"] { background: transparent !important; padding: 0.2rem 0 !important; }


/* —— 历史气泡样式（备用，已切换到 st.chat_message）—— */
.msg-row { display: flex; align-items: flex-start; margin: 0.5rem 0; }
.msg-row.user { justify-content: flex-end; }
.msg-row.assistant { justify-content: flex-start; }
.msg-bubble {
    max-width: 95%; padding: 0.75rem 1.15rem;
    font-size: 0.94rem; line-height: 1.7; color: #1e293b;
}
.msg-bubble.user {
    background: linear-gradient(135deg, #eff6ff, #dbeafe);
    border: 1px solid #bfdbfe;
    border-radius: 18px 18px 6px 18px;
}
.msg-bubble.assistant {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 18px 18px 18px 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.msg-label { font-size: 0.68rem; color: #94a3b8; margin: 0.15rem 0.3rem 0; }
.msg-row.user .msg-label { text-align: right; }
.msg-row.assistant .msg-label { text-align: left; }

/* —— 聊天输入框 —— */
[data-testid="stChatInput"] textarea {
    border-radius: 14px !important; border: 1.5px solid #e2e8f0 !important;
    background: #fff !important; padding: 0.7rem 1rem !important;
    font-size: 0.92rem !important; transition: border-color 0.2s;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #3b82f6 !important; box-shadow: 0 0 0 3px rgba(59,130,246,0.1) !important;
}

/* —— 通用按钮 —— */
.stButton > button {
    border-radius: 10px !important; border: 1px solid #e2e8f0 !important;
    background: #fff !important; color: #334155 !important;
    font-size: 0.82rem !important; font-weight: 500 !important;
    padding: 0.45rem 1rem !important; transition: all 0.15s;
}
.stButton > button:hover {
    border-color: #3b82f6 !important; background: #eff6ff !important; color: #2563eb !important;
}
.stButton > button:active { transform: scale(0.98); }

/* —— 表单 —— */
.stSelectbox [data-baseweb="select"] > div,
.stDateInput input, .stTextInput input {
    border-radius: 8px !important; border-color: #e2e8f0 !important;
}
.stFormSubmitButton > button {
    background: #2563eb !important; color: #fff !important;
    border: none !important; border-radius: 10px !important;
    font-weight: 600 !important;
}
.stFormSubmitButton > button:hover { background: #1d4ed8 !important; }

/* —— KPI 卡片 —— */
.kpi-card {
    border-radius: 12px; padding: 1rem 1.2rem;
    background: #fff; border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.03); transition: box-shadow 0.2s;
}
.kpi-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.06); }
.kpi-card.green  { border-left: 3px solid #10b981; }
.kpi-card.blue   { border-left: 3px solid #3b82f6; }
.kpi-card.orange { border-left: 3px solid #f59e0b; }
.kpi-card.red    { border-left: 3px solid #ef4444; }
.kpi-value { font-size: 1.8rem; font-weight: 700; color: #1e293b; }
.kpi-label { font-size: 0.76rem; color: #64748b; margin-top: 0.15rem; }

/* —— 异常卡片 —— */
.alert-card {
    border-radius: 10px; padding: 0.75rem 1rem; margin: 0.4rem 0;
    font-size: 0.85rem; box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.alert-high   { border-left: 4px solid #ef4444; background: #fef2f2; }
.alert-medium { border-left: 4px solid #f59e0b; background: #fffbeb; }
.alert-low    { border-left: 4px solid #3b82f6; background: #eff6ff; }

/* —— 设备卡片 —— */
.eq-card {
    background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 0.5rem 0.75rem; margin: 0.2rem 0; font-size: 0.8rem;
    transition: box-shadow 0.15s;
}
.eq-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
.eq-card .eq-name { font-weight: 600; color: #1e293b; }

/* —— 徽章 —— */
.badge {
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 0.7rem; font-weight: 600; margin-left: 4px;
}
.badge-c1 { background: #fee2e2; color: #dc2626; }
.badge-c2 { background: #d1fae5; color: #059669; }
.badge-c3 { background: #dbeafe; color: #2563eb; }

/* —— 状态指示灯 —— */
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.35;} }
.dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 6px; }
.dot.green  { background: #10b981; }
.dot.yellow { background: #f59e0b; animation: pulse 2s infinite; }
.dot.red    { background: #ef4444; }
.dot.gray   { background: #9ca3af; }

/* —— 空状态 —— */
.empty-state { text-align: center; padding: 2rem; color: #9ca3af; }
.empty-state .icon { font-size: 2.5rem; margin-bottom: 0.5rem; }

/* —— 滚动条 —— */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #f1f5f9; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* —— DataFrame —— */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; border: 1px solid #e2e8f0; }
[data-testid="stDataFrame"] th { background: #f8fafc !important; color: #475569 !important;
    font-weight: 600; font-size: 0.8rem; }

/* —— Expander —— */
.streamlit-expanderHeader {
    border-radius: 8px !important; border: 1px solid #e2e8f0 !important;
    background: #fff !important; font-size: 0.85rem !important;
}

/* —— 底部 —— */
footer { visibility: hidden; }
[data-testid="stAppViewContainer"] > .main > .block-container { padding-bottom: 0.5rem !important; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 🔧 工具函数
# ============================================================

def now_str(): return datetime.now().strftime("%H:%M")


def copy_block(text: str) -> str:
    """生成可复制文本的 HTML"""
    safe = text.replace("`", "\\`").replace("$", "\\$")
    return f"""<span style="display:flex;align-items:center;gap:0.5rem;">
<span>{safe}</span>
<button onclick="navigator.clipboard.writeText(`{safe}`)" class="copy-btn" title="复制">📋</button>
</span>"""

CHAT_DIR = PROJECT_ROOT / "data"

def _chat_file(uid: int) -> Path:
    return CHAT_DIR / f"chat_history_u{uid}.json"

def _save_chat_history(msgs, uid: int = 1):
    """持久化对话到用户专属文件"""
    try:
        CHAT_DIR.mkdir(parents=True, exist_ok=True)
        safe = [{"role": m["role"], "content": m["content"]} for m in msgs]
        import json as _json
        _chat_file(uid).write_text(_json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _load_chat_history(uid: int = 1):
    """从用户专属文件恢复对话"""
    try:
        f = _chat_file(uid)
        if f.exists():
            import json as _json
            return _json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None

def _export_chat_markdown(msgs):
    """导出对话为 Markdown 文本"""
    md = "# LabAgent 对话记录\n\n"
    md += f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"
    for m in msgs:
        role = "🧑 用户" if m["role"] == "user" else "🤖 LabAgent"
        md += f"### {role}\n\n{m['content']}\n\n---\n\n"
    return md


# ============================================================
# 🚀 初始化
# ============================================================

def init_system():
    """初始化（结果存 session_state，不用 cache_resource 避免过时缓存）"""
    if "agent_store" in st.session_state:
        return st.session_state.agent_store
    from src.database.db import init_db, get_session
    from src.database.seed import seed_all
    init_db()
    s = get_session(); seed_all(s); s.close()
    from src.rag.retriever import init_knowledge_base
    store = init_knowledge_base()
    from src.agents.graph import create_agent
    agent = create_agent()
    st.session_state.agent_store = (agent, store)
    return agent, store


def load_data():
    from src.database.db import get_session
    from src.database.models import Equipment, Booking
    from src.tools.monitor_tools import check_anomalies, generate_usage_stats
    s = get_session()
    eqs = s.query(Equipment).filter(Equipment.status != "报废").all()
    eq_list = [{"id": e.id, "name": e.name, "category": e.category,
                "location": e.location, "requires_cert": e.requires_cert,
                "cert_level_required": e.cert_level_required,
                "max_hours": e.max_hours_per_booking,
                "cost": e.hourly_cost, "status": e.status} for e in eqs]

    today = date.today()
    bks = s.query(Booking).filter(
        Booking.booking_date >= today,
        Booking.booking_date < today + timedelta(days=7)
    ).order_by(Booking.booking_date, Booking.start_hour).all()
    bk_list = [{"id": b.id, "eid": b.equipment_id, "ename": b.equipment.name if b.equipment else "?",
                "uname": b.user.name if b.user else "?", "date": str(b.booking_date),
                "start": b.start_hour, "dur": b.duration_hours,
                "purpose": b.purpose or "", "status": b.status} for b in bks]
    s.close()
    return eq_list, bk_list, check_anomalies(14), generate_usage_stats(30)


# ============================================================
# 🎨 组件
# ============================================================

def hero():
    st.markdown("""
<div style="background:linear-gradient(135deg,#1e3a5f 0%,#2563eb 50%,#3b82f6 100%);border-radius:16px;padding:1.4rem 2rem;margin-bottom:0.6rem;box-shadow:0 4px 24px rgba(37,99,235,0.15)">
<span style="color:#ffffff;font-size:1.5rem;font-weight:700;display:block;">🧪 LabAgent — 智能实验室仪器共享预约平台</span>
<span style="color:#bfdbfe;font-size:0.82rem;display:block;margin-top:0.3rem;">LangGraph 多智能体 · Supervisor / Scheduler / QA / Monitor · ReAct 工具调用 · RAG 知识增强</span>
</div>
""", unsafe_allow_html=True)


def _parse_slots_from_response(text: str) -> list:
    """从 Agent 回复中提取可预约时间段"""
    import re
    slots = []
    pats = [
        r'(\d{4}-\d{2}-\d{2})\s*(\d{1,2}):00\s*[-–—]\s*(\d{1,2}):00',
        r'(周[一二三四五六日])\s*(\d{1,2}):00\s*[-–—]\s*(\d{1,2}):00',
    ]
    for pat in pats:
        for m in re.finditer(pat, text):
            slots.append({"date": m.group(1), "start": int(m.group(2)), "end": int(m.group(3)),
                          "text": f"{m.group(1)} {m.group(2)}:00-{m.group(3)}:00"})
    seen = set(); unique = []
    for s in slots:
        if s["text"] not in seen: seen.add(s["text"]); unique.append(s)
    return unique[:5]


def _render_quick_replies(text: str):
    """Agent 回复时渲染快捷按钮"""
    # 确认预约场景：显示 确定/再想想
    if "确认预约" in text:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ 确定", key="qr_confirm", use_container_width=True, type="primary"):
                st.session_state.pending_prompt = "确认"
                st.rerun()
        with c2:
            if st.button("🤔 再想想", key="qr_rethink", use_container_width=True):
                st.session_state.pending_prompt = "我再想想"
                st.rerun()
        return

    # 预约时段场景：显示可预约时段按钮
    slots = _parse_slots_from_response(text)
    if not slots: return
    st.caption("👇 快捷预约")
    cols = st.columns(min(len(slots), 4))
    for i, s in enumerate(slots):
        with cols[i % 4]:
            if st.button(f"📅 {s['text']}", key=f"qr_{i}_{hash(s['text'])}", use_container_width=True):
                u = st.session_state.get("current_user", {"id": 1, "name": "张三"})
                st.session_state.pending_prompt = f"帮我预约{s['date']} {s['start']:02d}:00到{s['end']:02d}:00的仪器，用户{u['name']}(ID:{u['id']})"
                st.rerun()


def _render_weekly_calendar(bk_list, eq_list):
    """渲染周视图日历：先选仪器 → 显示该仪器预约表 → 点击空格直接预约"""
    today_date = date.today()
    monday = today_date  # 从今天开始
    days_cn_all = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    days_cn = [days_cn_all[(today_date.weekday() + i) % 7] for i in range(7)]
    hours = list(range(8, 20))

    # 先选仪器（按用户证书过滤，不可约的直接不显示）
    u = st.session_state.get("current_user", {"id": 1, "name": "张三", "cert": 1})
    available_eq = []
    unavailable_eq = []
    for e in eq_list:
        cert = e.get("cert_level_required", 0) if isinstance(e, dict) else e.cert_level_required
        name = e["name"] if isinstance(e, dict) else e.name
        if cert > u.get("cert", 0):
            unavailable_eq.append(f"{name} (需L{cert}证)")
        else:
            available_eq.append(name)
    eq_choice = st.selectbox("选择仪器查看预约日历", available_eq + unavailable_eq, key="cal_eq_select")
    if eq_choice in unavailable_eq:
        st.warning(f"⚠️ 证书不足，无法预约 {eq_choice.split(' (需')[0]}。请切换用户或选择其他仪器。")
        st.session_state.cal_selected = set()
        eq_choice = available_eq[0] if available_eq else eq_choice
    eq_name = eq_choice.split(" (需")[0]
    eq_id = next((e["id"] if isinstance(e, dict) else e.id for e in eq_list if (e["name"] if isinstance(e, dict) else e.name) == eq_name), 1)

    # 构建该仪器的占用表
    occupied = {}
    for b in bk_list:
        if b["status"] in ("已取消",): continue
        if b["eid"] != eq_id: continue  # 只看选中的仪器
        bdate = datetime.strptime(b["date"], "%Y-%m-%d").date()
        day_off = (bdate - monday).days
        if 0 <= day_off < 7:
            for h in range(b["start"], b["start"] + b["dur"]):
                occupied[(day_off, h)] = b

    st.caption("🟢 空闲可选  |  🔵 已选中  |  🔴 他人预约  |  🔷 我的预约")

    # 初始化选中集合
    if "cal_selected" not in st.session_state:
        st.session_state.cal_selected = set()
    sel = st.session_state.cal_selected

    # Streamlit 按钮日历（支持多选）
    cols = st.columns([0.7] + [1]*7)
    cols[0].button("时间", disabled=True, key="hdr_time", use_container_width=True)
    for d in range(7):
        dd = (monday+timedelta(days=d)).strftime("%m/%d")
        cols[d+1].button(f"{days_cn[d]}\n{dd}", disabled=True, key=f"hdr_{d}", use_container_width=True)
    for h in hours:
        rcols = st.columns([0.7] + [1]*7)
        rcols[0].button(f"{h:02d}:00", disabled=True, key=f"rt_{h}", use_container_width=True)
        for d in range(7):
            key = (d, h)
            sd = str(monday + timedelta(days=d))
            slot_id = f"{sd}~{h}"
            with rcols[d+1]:
                if key in occupied:
                    bk = occupied[key]
                    u_cur = st.session_state.get("current_user", {"name":"张三"})
                    is_me = bk['uname'] == u_cur.get("name","")
                    label = f"🔷 {bk['uname']}" if is_me else f"🔴 {bk['uname']}"
                    st.button(label, key=f"c_{eq_id}_{d}_{h}", disabled=True, use_container_width=True)
                elif slot_id in sel:
                    if st.button(f"🔵", key=f"c_{eq_id}_{d}_{h}", use_container_width=True,
                                 help=f"取消选择 {sd} {h:02d}:00"):
                        sel.discard(slot_id); st.rerun()
                else:
                    if st.button(f"🟢", key=f"c_{eq_id}_{d}_{h}", use_container_width=True,
                                 help=f"选择 {sd} {h:02d}:00"):
                        sel.add(slot_id); st.rerun()

    # 多选确认栏
    if sel:
        slots_in_eq = [s for s in sel if s.startswith(str(monday)[:7]) or True]  # any in this week
        st.markdown(f"已选 **{len(sel)}** 个时段")
        if st.button(f"✅ 确认预约（{len(sel)}个时段）", key="cal_confirm", use_container_width=True, type="primary"):
            u = st.session_state.get("current_user", {"id": 1, "name": "张三"})
            parts = []
            for s in sorted(sel):
                date_str, hour_str = s.split("~")
                parts.append(f"{date_str} {int(hour_str):02d}:00-{int(hour_str)+1:02d}:00")
            slots_desc = "、".join(parts)
            # 批量预约前全量检查（一个失败则全部失败）
            from src.tools.booking_tools import check_availability, get_equipment_detail
            eq_id = next((e["id"] for e in eq_list if e["name"] == eq_choice), 1)
            eq_detail = get_equipment_detail(eq_id)
            cert_need = eq_detail.get("cert_level_required", 0) if eq_detail else 0
            all_ok = True; failed = []
            for s in sorted(sel):
                ds, hs = s.split("~")
                av = check_availability(eq_id, ds, int(hs), 1)
                if not av.get("available"):
                    all_ok = False; failed.append(f"{ds} {int(hs):02d}:00 冲突")
            if u.get("cert", 1) < cert_need:
                all_ok = False; failed.append(f"证书不足（需L{cert_need}，你L{u.get('cert',1)}）")
            if not all_ok:
                # 预检失败也弹窗，让 AI 解释原因
                st.session_state.cal_booking = {
                    "eq": eq_choice, "slots": slots_desc,
                    "user": u["name"], "uid": u["id"],
                    "precheck_failed": failed
                }
            else:
                st.session_state.cal_booking = {
                    "eq": eq_choice, "slots": slots_desc,
                    "user": u["name"], "uid": u["id"]
                }
            st.session_state.cal_selected = set()
            st.rerun()
        if st.button("🗑️ 清空选择", key="cal_clear_sel", use_container_width=True):
            sel.clear(); st.rerun()


def kpi_row(items):
    """items: [(value, label, color), ...]"""
    c = st.columns(len(items))
    for col, (v, l, clr) in zip(c, items):
        col.markdown(f"""<div class="kpi-card {clr}"><div class="kpi-value">{v}</div><div class="kpi-label">{l}</div></div>""", unsafe_allow_html=True)


def alert_card(a):
    sev = a.get("severity", "低")
    css = {"高": "alert-high", "中": "alert-medium"}.get(sev, "alert-low")
    e = {"高": "🔴", "中": "🟡", "低": "🟢"}.get(sev, "⚪")
    st.markdown(f"""<div class="alert-card {css}"><strong>{e} {a.get('type','')}</strong> · {a.get('equipment_name','')} · {a.get('user_name','')}<div style="color:#8b949e;font-size:0.78rem;margin-top:0.25rem;">{a.get('detail','')}<br>💡 {a.get('suggestion','')}</div></div>""", unsafe_allow_html=True)


def think_step(t):
    agent = t.get("agent", "")
    action = t.get("action", "")
    detail = str(t.get("detail", ""))[:160]
    if "Supervisor" in agent: clr = "#ffd43b"
    elif "Scheduler" in agent: clr = "#58a6ff"
    elif "QA" in agent: clr = "#3fb950"
    elif "Monitor" in agent: clr = "#d29922"
    else: clr = "#484f58"
    st.markdown(f"""<div class="think-bar"><span class="agent" style="color:{clr}">{agent}</span><span class="action">{action}</span><div style="color:#484f58;font-size:0.7rem;margin-top:0.15rem;">{detail}</div></div>""", unsafe_allow_html=True)


def eq_status_card(e):
    dot_cls = {"可用": "green", "维护中": "yellow", "报废": "red"}.get(e.get("status", "可用"), "gray")
    cert = "🔒" if e.get("requires_cert") else "🔓"
    st.markdown(f"""<div class="eq-card"><span class="dot {dot_cls}"></span><span class="eq-name">{e['name'][:20]}</span> <span style="color:#8b949e;font-size:0.7rem;">{cert} · {e['cost']:.0f}元/h</span></div>""", unsafe_allow_html=True)


# ============================================================
# 📱 主应用
# ============================================================

def main():
    hero()

    # 初始化
    try:
        import sys as _sys
        print("[LabAgent] 正在初始化...", file=_sys.stderr, flush=True)
        agent, store = init_system()
        eq_list, bk_list, anomalies, stats = load_data()
        print(f"[LabAgent] 知识库: {store.collection.count()} 文档块", file=_sys.stderr, flush=True)
        print(f"[LabAgent] 数据库: {len(eq_list)} 台仪器, {len(bk_list)} 条预约", file=_sys.stderr, flush=True)
        from src.agents.graph import _init_mcp_tools
        _init_mcp_tools()
        print("[LabAgent] ✅ 启动完成！访问 http://localhost:8501", file=_sys.stderr, flush=True)
    except Exception as e:
        st.error(f"❌ 初始化失败: {e}"); return

    # 确保 current_user 始终有值（sidebar 首次渲染前）
    if "current_user" not in st.session_state:
        st.session_state.current_user = {"name": "张三", "id": 1, "cert": 1, "role": "学生", "dept": "材料科学与工程"}

    # ==================== 侧边栏 ====================
    with st.sidebar:
        # 实时时钟（最上方）
        st.components.v1.html("""
        <div id="live-clock" style="text-align:center;font-size:1.3rem;font-weight:700;color:#1e293b;
             background:#f8fafc;border-radius:12px;padding:0.6rem;border:1px solid #e2e8f0;margin-bottom:0.8rem;">
        </div>
        <script>
        function updateClock() {
            var now = new Date();
            var d = now.getFullYear() + '-' +
                String(now.getMonth()+1).padStart(2,'0') + '-' +
                String(now.getDate()).padStart(2,'0') + ' 周' +
                ['日','一','二','三','四','五','六'][now.getDay()] + ' ' +
                String(now.getHours()).padStart(2,'0') + ':' +
                String(now.getMinutes()).padStart(2,'0') + ':' +
                String(now.getSeconds()).padStart(2,'0');
            document.getElementById('live-clock').innerHTML = '⏰ ' + d;
        }
        updateClock();
        setInterval(updateClock, 1000);
        </script>
        """, height=100)

        # 用户切换
        st.markdown("### 👤 当前用户")
        users_info = {
            "张三 (学生 L1)": {"name": "张三", "id": 1, "role": "学生", "cert": 1, "dept": "材料科学与工程"},
            "李四 (学生 L0)": {"name": "李四", "id": 2, "role": "学生", "cert": 0, "dept": "化学化工学院"},
            "王五 (学生 L2)": {"name": "王五", "id": 3, "role": "学生", "cert": 2, "dept": "物理学院"},
            "赵教授 (教师 L2)": {"name": "赵教授", "id": 4, "role": "教师", "cert": 2, "dept": "材料科学与工程"},
            "管理员刘 (管理员)": {"name": "管理员刘", "id": 5, "role": "管理员", "cert": 2, "dept": "实验中心"},
        }
        user_key = st.selectbox("切换用户", list(users_info.keys()), index=0)
        u = users_info[user_key]
        st.session_state.current_user = u
        st.markdown(f"**{u['name']}** · {u['role']} · {u['dept']}")
        st.markdown(f'<span class="badge badge-c2">证书等级 L{u["cert"]}</span>', unsafe_allow_html=True)

        st.divider()
        st.markdown("### 🔬 仪器状态")

        today = date.today()
        for e in eq_list:
            has_active = any(b["eid"] == e["id"] and b["date"] == str(today) and b["status"] == "已确认" for b in bk_list)
            dot = "yellow" if has_active else "green" if e["status"] == "可用" else "gray"
            st.markdown(f"""<div class="eq-card"><span class="dot {dot}"></span><span class="eq-name">{e['name'][:22]}</span><span style="color:#8b949e;font-size:0.7rem;float:right">{'使用中' if has_active else e['status']}</span></div>""", unsafe_allow_html=True)

        # ---- 今日摘要（可展开）----
        st.divider()
        st.markdown("### 📊 今日概览")
        today_str = str(date.today())
        today_bks = [b for b in bk_list if b["date"] == today_str]
        active_now = sum(1 for b in today_bks if b["status"] == "已确认")
        st.caption(f"📅 今日预约: {len(today_bks)} 条 | 🟢 {active_now} 台 | ✅ {sum(1 for b in today_bks if b['status']=='已完成')} 条")
        with st.expander("查看详情"):
            if today_bks:
                for b in sorted(today_bks, key=lambda x: x["start"]):
                    icon = {"已确认":"📌","已完成":"✅","爽约":"❌"}.get(b["status"],"❓")
                    st.caption(f"{icon} {b['start']:02d}:00-{b['start']+b['dur']:02d}:00 | {b['ename'][:15]} | {b['uname']}")
            else:
                st.caption("今日暂无预约")

        # ---- 活跃告警（可跳转）----
        st.divider()
        st.markdown("### ⚠️ 活跃告警")
        high_alerts = [a for a in anomalies if a.get("severity")=="高"]
        mid_alerts = [a for a in anomalies if a.get("severity")=="中"]
        high_n = len(high_alerts); mid_n = len(mid_alerts)
        if high_n:
            st.error(f"🔴 {high_n} 条高危异常")
        if mid_n:
            st.warning(f"🟡 {mid_n} 条中危异常")
        if not high_n and not mid_n:
            st.success("✅ 系统运行正常")
        if st.button("→ 查看详情", key="goto_monitor", use_container_width=True):
            st.session_state.active_tab = 2
            st.session_state.expand_anomalies = True
            st.rerun()

        # ---- 系统状态 ----
        st.divider()
        st.markdown("### 🔌 系统状态")
        import os as _os
        api_ok = bool(_os.getenv("DEEPSEEK_API_KEY"))
        st.caption(f"{'✅' if api_ok else '❌'} DeepSeek API")
        st.caption(f"📚 知识库: {store.collection.count()} 块")
        st.caption(f"🗄️ {len(eq_list)} 台仪器 · {len(bk_list)} 条预约")
        try:
            from src.mcp.mcp_client import get_mcp_bridge
            b = get_mcp_bridge()
            st.caption(f"🔗 MCP: {'已连接' if b.is_connected else '待机'} ({len(b.tool_names)} tools)" if b.is_connected else "🔗 MCP: 待机")
        except Exception:
            st.caption("🔗 MCP: 待机")

        st.divider()
        st.caption("Powered by LangGraph + DeepSeek")
        st.caption("Powered by LangGraph + DeepSeek")

    # ==================== 主区域 Tabs ====================
    tab_names = ["💬 AI 助手", "📅 预约管理", "🔍 监控中心", "📖 知识库"]
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = 0
    active_idx = st.radio("导航", range(4), format_func=lambda i: tab_names[i],
                          horizontal=True, label_visibility="collapsed",
                          key="main_nav", index=min(st.session_state.active_tab, 3))
    st.session_state.active_tab = active_idx
    show_tab = active_idx

    # 确保聊天历史已初始化（在所有 tab 之前）
    uid_chat = st.session_state.get("current_user", {"id": 1}).get("id", 1)
    ck = f"msgs_u{uid_chat}"
    if ck not in st.session_state:
        saved = _load_chat_history(uid_chat)
        st.session_state[ck] = saved if saved else [{"role": "assistant", "content": "👋 你好！我是 LabAgent，有什么可以帮你？"}]
    st.session_state.msgs = st.session_state[ck]

    # ---------- Tab 0: AI 助手 ----------
    if show_tab == 0:
        qcols = st.columns(4)
        for btn, col, txt in [
            ("📅 预约仪器", qcols[0], "我想预约一台仪器"),
            ("📖 操作咨询", qcols[1], "我想了解仪器的操作规范"),
            ("🔍 安全检查", qcols[2], "帮我检查一下系统最近的情况"),
            ("⚠️ 安全案例", qcols[3], "最近实验室有什么安全事故吗"),
        ]:
            if col.button(btn, use_container_width=True, key=f"qt_{btn}"):
                st.session_state.pending_prompt = txt; st.rerun()

        pending = st.session_state.pop("pending_prompt", None)
        display_msgs = list(st.session_state.msgs)
        if pending:
            display_msgs.append({"role": "user", "content": pending})
            display_msgs.append({"role": "assistant", "content": "__STREAMING__"})

        msg_box = st.container(height=500, border=False)
        with msg_box:
            for i, msg in enumerate(display_msgs):
                role = msg.get("role", "assistant")
                is_s = msg.get("content") == "__STREAMING__"
                if is_s:
                    with st.chat_message("assistant", avatar="🧪"):
                        ph = st.empty(); ph.markdown("🤔 *思考中...*")
                        ft = ""
                        try:
                            from src.chat_api import send_message
                            u = st.session_state.get("current_user", {"name":"张三","id":1,"cert":1,"role":"学生"})
                            r = send_message(pending, "web_session", agent, user_name=u["name"], user_id=u["id"], user_cert=u["cert"], user_role=u["role"])
                            ft = r.get("response","") or "⚠️ 未能生成回复"
                        except Exception as e: ft = f"❌ {e}"
                        disp = ""
                        for c in ft: disp += c; ph.markdown(disp + " ▌"); import time as _t; _t.sleep(0.004)
                        ph.markdown(ft)
                    st.session_state.msgs.append({"role":"user","content":pending})
                    st.session_state.msgs.append({"role":"assistant","content":ft})
                    _save_chat_history(st.session_state.msgs, st.session_state.get("current_user",{"id":1}).get("id",1))
                    _render_quick_replies(ft)
                else:
                    av = "🧑‍🔬" if role == "user" else "🧪"
                    with st.chat_message(role, avatar=av): st.markdown(msg["content"])
                    if role == "assistant" and i == len(display_msgs) - 1: _render_quick_replies(msg["content"])

        prompt = st.chat_input("输入消息...")
        if prompt: st.session_state.pending_prompt = prompt; st.rerun()
        if len(st.session_state.msgs) > 1:
            c1, c2 = st.columns(2)
            if c1.button("🗑️ 清除对话", key="clear_chat", use_container_width=True):
                uid = st.session_state.get("current_user",{"id":1}).get("id",1); ck = f"msgs_u{uid}"
                w = st.session_state[ck][:1]; st.session_state[ck] = w; st.session_state.msgs = w
                _save_chat_history(w, uid); st.rerun()
            c2.download_button("📥 导出对话", _export_chat_markdown(st.session_state.msgs), "chat.md", key="export_chat", use_container_width=True)

    # ==================== 页面主体内容 ====================
    # ---------- Tab 2: 预约管理 ----------
    if show_tab == 1:
        st.subheader("📅 预约管理")
        if "booking_success_msg" in st.session_state:
            st.success(st.session_state.pop("booking_success_msg"))

        # 刷新按钮
        col_rf, _ = st.columns([1, 5])
        with col_rf:
            if st.button("🔄 刷新数据", key="refresh_kpi", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        st.caption(f"⏱️ 数据更新时间: {datetime.now().strftime('%H:%M:%S')}")

        # KPI
        week_bks = [b for b in bk_list if b["status"] != "已取消"]
        total_h = sum(b["dur"] for b in week_bks)
        kpi_row([
            (str(len(week_bks)), "本周预约", "blue"),
            (f"{total_h}h", "本周机时", "green"),
            (str(sum(1 for b in week_bks if b["status"]=="已确认")), "待执行", "orange"),
            (str(sum(1 for b in week_bks if b["status"]=="爽约")), "爽约", "red"),
        ])

        # 拖拽式周历
        st.markdown("#### 📆 本周预约日历（点击空格直接预约）")
        _render_weekly_calendar(bk_list, eq_list)

        # 内联 AI 对话（日历触发）
        cbook = st.session_state.pop("cal_booking", None)
        if cbook:
            st.session_state.cal_dialog = {"eq": cbook["eq"], "slots": cbook.get("slots",""), "user": cbook["user"], "uid": cbook["uid"]}
            prompt = f"帮我预约{cbook['eq']}，时段：{cbook.get('slots','')}，用户{cbook['user']}(ID:{cbook['uid']})"
            failed = cbook.get("precheck_failed")
            if failed:
                prompt = f"我想预约{cbook['eq']}，时段：{cbook.get('slots','')}，但系统预检发现以下问题：{'；'.join(failed)}。请解释并给出建议。"
            st.session_state.cal_dialog_msgs = [{"role":"user","content": prompt}]
            st.rerun()
        if st.session_state.get("cal_dialog"):
            d = st.session_state.cal_dialog; msgs = st.session_state.get("cal_dialog_msgs",[])
            with st.expander(f"🤖 小助手帮你预约 {d['eq']}...", expanded=True):
                for msg in msgs:
                    av = "🧑‍🔬" if msg["role"]=="user" else "🧪"
                    with st.chat_message(msg["role"], avatar=av): st.markdown(msg["content"])
                if msgs and msgs[-1]["role"]=="user" and not st.session_state.get("_cdp"):
                    st.session_state._cdp = True
                    u = st.session_state.get("current_user",{"name":"张三","id":1,"cert":1,"role":"学生"})
                    with st.chat_message("assistant", avatar="🧪"):
                        ph = st.empty(); ph.markdown("🤔 *思考中...*"); ft = ""
                        try:
                            from src.chat_api import send_message
                            r = send_message(msgs[-1]["content"],"web_cal",agent,user_name=d["user"],user_id=d["uid"],user_cert=u.get("cert",1),user_role=u.get("role","学生"))
                            ft = r.get("response","") or "⚠️ 未生成回复"
                        except Exception as e: ft = f"❌ {e}"
                        disp = ""; import time as _t
                        for c in ft: disp += c; ph.markdown(disp+" ▌"); _t.sleep(0.003)
                        ph.markdown(ft)
                    msgs.append({"role":"assistant","content":ft})
                    st.session_state._cdp = False; st.rerun()
                reply = st.chat_input("💬 回复...", key="cal_di")
                if reply: msgs.append({"role":"user","content":reply}); st.rerun()
                if st.button("✕ 关闭", key="cal_dc", use_container_width=True):
                    for m in msgs: st.session_state.msgs.append(m)
                    _save_chat_history(st.session_state.msgs, d["uid"])
                    st.session_state.cal_dialog = None; st.session_state.cal_dialog_msgs = []; st.rerun()


        col_gantt, col_book = st.columns([2, 1])

        with col_gantt:
            st.markdown("#### 🗓️ 本周预约甘特图")
            if week_bks:
                monday_date = date.today()
                for b in sorted(week_bks, key=lambda x: (x["date"], x["start"])):
                    day_idx = (datetime.strptime(b["date"], "%Y-%m-%d").date() - monday_date).days
                    if 0 <= day_idx < 7:
                        bar = "█" * b["dur"]
                        icon = {"已确认":"📌","已完成":"✅","爽约":"❌"}.get(b["status"],"❓")
                        day_label = (monday_date + timedelta(days=day_idx)).strftime("%m/%d")
                        wd = ["周一","周二","周三","周四","周五","周六","周日"][(monday_date + timedelta(days=day_idx)).weekday()]
                        st.write(f"{icon} {wd} {day_label} {b['start']:02d}:00 `{bar}` {b['start']+b['dur']:02d}:00 — *{b['ename']}* ({b['uname']})")
            else:
                st.markdown('<div class="empty-state"><div class="icon">📭</div>本周暂无预约记录</div>', unsafe_allow_html=True)

            # 我的预约时间线
            st.divider()
            st.markdown("#### 📋 我的全部预约（跨仪器时间线）")
            u = st.session_state.get("current_user", {"name": "张三", "id": 1})
            from src.database.db import get_session
            from src.database.models import Booking
            from collections import defaultdict
            s = get_session()
            my_bks = s.query(Booking).filter(Booking.user_id == u["id"]).order_by(Booking.booking_date, Booking.start_hour).all()
            if my_bks:
                # 按日期分组
                by_date = defaultdict(list)
                for b in my_bks:
                    by_date[str(b.booking_date)].append(b)
                for dt_str, bks in sorted(by_date.items()):
                    dt = datetime.strptime(dt_str, "%Y-%m-%d")
                    wd = ["周一","周二","周三","周四","周五","周六","周日"][dt.weekday()]
                    st.caption(f"**{dt_str} {wd}**")
                    for b in bks:
                        icon = {"已确认": "📌", "已完成": "✅", "爽约": "❌", "已取消": "🗑️"}.get(b.status, "❓")
                        bar = "█" * b.duration_hours
                        cols = st.columns([5, 1])
                        with cols[0]:
                            st.write(f"{icon} {b.start_hour:02d}:00 `{bar}` {b.start_hour+b.duration_hours:02d}:00 · {b.equipment.name if b.equipment else '?'} · _{b.status}_")
                        with cols[1]:
                            if b.status == "已确认":
                                if st.button("取消", key=f"cancel_bk_{b.id}", use_container_width=True):
                                    from src.tools.booking_tools import cancel_booking
                                    result = cancel_booking(b.id)
                                    if result.get("success"):
                                        st.cache_data.clear(); st.rerun()
                                    else:
                                        st.error(result.get("message", "取消失败"))
            else:
                st.caption("暂无预约记录")
            s.close()

        with col_book:
            st.markdown("#### ⚡ 快速预约")
            # 侧边栏跳转预选仪器
            pre_select_id = st.session_state.pop("pre_select_equip", None)
            eq_names = [e["name"] for e in eq_list]
            default_idx = 0
            if pre_select_id:
                for i, e in enumerate(eq_list):
                    if e["id"] == pre_select_id:
                        default_idx = i; break
            with st.form("quick_book_form"):
                eq_choice = st.selectbox("仪器", eq_names, index=default_idx)
                book_date = st.date_input("日期", value=date.today() + timedelta(days=1))
                col_h, col_d = st.columns(2)
                with col_h: sh = st.selectbox("开始时间", list(range(8, 22)), index=1)
                with col_d: dur = st.selectbox("时长(h)", [1, 2, 3, 4, 6, 8], index=3)
                purpose = st.text_input("用途", placeholder="如：纳米颗粒形貌观察")
                submitted = st.form_submit_button("🔍 检查可用性并预约", use_container_width=True)

                if submitted:
                    eq_id = next((e["id"] for e in eq_list if e["name"] == eq_choice), 1)
                    from src.tools.booking_tools import check_availability as chk, create_booking
                    avail = chk(eq_id, str(book_date), sh, dur)
                    if avail.get("available"):
                        result = create_booking(eq_id, 1, str(book_date), sh, dur, purpose)
                        if result.get("success"):
                            st.cache_data.clear()
                            st.session_state.booking_success_msg = (
                                f"✅ 预约成功！{result.get('equipment_name')} "
                                f"{book_date} {sh:02d}:00-{sh+dur:02d}:00 费用:¥{result.get('estimated_cost',0):.0f}"
                            )
                            st.rerun()
                        else:
                            st.error(result.get("message", "预约失败"))
                    else:
                        st.error(f"❌ 时段不可用")
                        if avail.get("conflicts"):
                            for c in avail["conflicts"]:
                                st.caption(f"· 冲突: {c.get('user','?')} {c['start_hour']:02d}:00")
                        # 替代方案
                        from src.tools.booking_tools import suggest_alternatives
                        alts = suggest_alternatives(eq_id, str(book_date), dur)
                        if alts:
                            st.info("💡 **替代方案**")
                            for a in alts[:3]:
                                st.caption(f"· {a.get('type','')}: {a.get('equipment_name','')} {a.get('date','')} {a.get('start_hour',''):02d}:00")

    # ---------- Tab 3: 监控中心 ----------
    if show_tab == 2:
        st.subheader("🔍 安全监控中心")

        kpi_row([
            (str(len(anomalies)), "待处理异常", "red" if anomalies else "green"),
            (str(stats.get("total_bookings", 0)), "30天预约数", "blue"),
            (f"{stats.get('total_hours', 0)}h", "30天总机时", "green"),
            (f"{stats.get('no_show_count', 0)}次", "爽约", "orange"),
        ])

        c1, c2 = st.columns([1, 1])

        with c1:
            st.markdown("#### 🚨 异常详情")
            if anomalies:
                for a in anomalies:
                    alert_card(a)
                # 下载报告
                report = "# 实验室安全审计报告\n\n" + f"生成时间: {datetime.now()}\n\n---\n\n"
                for a in anomalies:
                    report += f"## {a.get('type','')} [{a.get('severity','')}]\n"
                    report += f"- 仪器: {a.get('equipment_name','')}\n"
                    report += f"- 用户: {a.get('user_name','')}\n"
                    report += f"- 详情: {a.get('detail','')}\n"
                    report += f"- 建议: {a.get('suggestion','')}\n\n"
                st.download_button("📥 下载审计报告 (MD)", report, "lab_audit_report.md", use_container_width=True)
            else:
                st.markdown('<div class="empty-state"><div class="icon">✅</div>系统运行正常，未检测到异常</div>', unsafe_allow_html=True)

        with c2:
            st.markdown("#### 📈 仪器使用分布")
            by_eq = stats.get("by_equipment", {})
            # 无真实数据时生成演示数据
            if not by_eq:
                demo_data = [
                    {"仪器": "透射电镜", "预约数": 12, "总机时": 38, "独立用户": 4},
                    {"仪器": "ICP-MS", "预约数": 8, "总机时": 42, "独立用户": 3},
                    {"仪器": "HPC集群", "预约数": 20, "总机时": 156, "独立用户": 8},
                    {"仪器": "XRD", "预约数": 6, "总机时": 14, "独立用户": 3},
                    {"仪器": "NMR", "预约数": 4, "总机时": 7, "独立用户": 2},
                ]
                chart_data = pd.DataFrame(demo_data)
                st.caption("（演示数据）")
            else:
                chart_data = pd.DataFrame([
                    {"仪器": v["equipment_name"][:15], "预约数": v["total_bookings"],
                     "总机时": v["total_hours"], "独立用户": v["unique_users"]}
                    for v in by_eq.values()
                ])
            st.dataframe(chart_data, use_container_width=True, hide_index=True)
            st.bar_chart(chart_data.set_index("仪器")[["总机时", "预约数"]], use_container_width=True, horizontal=True)

            hottest_row = chart_data.sort_values("总机时", ascending=False).iloc[0]
            st.info(f"🔥 **{hottest_row['仪器']}** 最热门 — {int(hottest_row['总机时'])}h / {int(hottest_row['预约数'])}次")

            csv = chart_data.to_csv(index=False)
            st.download_button("📥 下载统计 (CSV)", csv, "lab_usage_stats.csv", "text/csv", use_container_width=True)

        # 安全事故案例
        st.divider()
        st.markdown("#### ⚠️ 安全事故警示录")
        from src.tools.monitor_tools import get_safety_incidents
        all_incidents = get_safety_incidents(limit=7)
        if all_incidents:
            col_inc1, col_inc2 = st.columns(2)
            for i, inc in enumerate(all_incidents):
                col = col_inc1 if i % 2 == 0 else col_inc2
                sev_color = {"极高": "#7f1d1d", "高": "#dc2626", "中": "#d97706", "低": "#6b7280"}.get(inc.get("severity", "中"), "#6b7280")
                with col:
                    with st.expander(f"{inc['severity']} | {inc['title']}", expanded=False):
                        st.markdown(f"""
                        <div style="border-left:3px solid {sev_color};padding:0.5rem 0.8rem;margin:0.2rem 0;background:#fff;border-radius:0 8px 8px 0;font-size:0.82rem;">
                        <strong>📅 {inc.get('date','')}</strong> · {inc.get('equipment','')} · {inc.get('category','')}<br>
                        <strong>原因:</strong> {inc.get('cause','')}<br>
                        <strong>处理:</strong> {inc.get('penalty','')}<br>
                        <strong>💡 教训:</strong> {inc.get('lesson','')}
                        </div>
                        """, unsafe_allow_html=True)

    # ---------- Tab 4: 知识库 ----------
    if show_tab == 3:
        st.subheader("📖 仪器SOP知识库")

        c_search, c_browse = st.columns([1, 1])

        with c_search:
            st.markdown("#### 🔎 语义检索")
            q = st.text_input("搜索操作规范", placeholder="如: 电镜样品干燥 或 ICP-MS安全事项", key="sop_search")
            if q and st.button("🔍 搜索", use_container_width=True):
                from src.tools.rag_tools import search_equipment_sop as sos
                with st.spinner("RAG 检索中..."):
                    results = sos(q, top_k=3)
                if results:
                    for r in results:
                        score = r.get("relevance_score", 0)
                        bar_color = "#3fb950" if score > 0.7 else "#d29922" if score > 0.4 else "#484f58"
                        st.markdown(f"""
                        <div style="border-left:3px solid {bar_color};padding:0.5rem 0.8rem;margin:0.4rem 0;background:#161b22;border-radius:0 8px 8px 0;">
                            <div style="font-weight:600;color:#e6edf3;">📄 {r['source_file']} · {r['section_title']}</div>
                            <div style="font-size:0.8rem;color:#8b949e;margin:0.3rem 0;">{r['content'][:350]}{'...' if len(r.get('content',''))>350 else ''}</div>
                            <span class="badge badge-c{'2' if score>0.7 else '3' if score>0.4 else '1'}">相关度 {score:.0%}</span>
                        </div>""", unsafe_allow_html=True)
                else:
                    st.warning("未找到相关内容，尝试换个关键词")

        with c_browse:
            st.markdown("#### 📤 上传新SOP")
            uploaded = st.file_uploader("上传 Markdown SOP 文档", type=["md"], key="sop_upload")
            if uploaded:
                dest = PROJECT_ROOT / "config" / "sop_docs" / uploaded.name
                dest.write_bytes(uploaded.getvalue())
                st.success(f"✅ {uploaded.name} 已保存，重启后自动索引")
                st.caption("文档将自动加入 RAG 知识库（需重启服务）")

            st.divider()
            st.markdown("#### 📚 文档库")
            sop_files = sorted((PROJECT_ROOT / "config" / "sop_docs").glob("*.md"))
            for f in sop_files:
                name = f.stem.replace("_", " ").title()
                content = f.read_text("utf-8")
                lines = content.split("\n")
                with st.expander(f"📄 {name} ({len(lines)} 行)", expanded=False):
                    st.markdown(content[:4000])

    st.write("")
    st.write("")
    # 底部
    st.caption("CS599 期末大作业 · LangGraph + DeepSeek + ChromaDB · 2026")


if __name__ == "__main__":
    main()
