"""
Streamlit Agent 调用接口（独立文件，避免 Python 模块缓存）
每次调用前强制 reload graph 模块，确保使用最新代码。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


def send_message(msg: str, thread_id: str, agent, user_name: str = "张三", user_id: int = 1, user_cert: int = 1, user_role: str = "学生") -> dict:
    """发送消息给 Agent，带用户上下文"""
    # 强制重新加载
    import importlib
    for mod_name in ["src.agents.graph", "src.agents.prompts"]:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
    import src.agents.graph as gmod

    from src.agents.graph import run_with_stream, create_agent
    if agent is None:
        agent = create_agent()

    from datetime import date
    today = date.today()
    user_ctx = (
        f"当前用户: {user_name}, ID: {user_id}, 角色: {user_role}, 证书等级: L{user_cert}。"
        f"当前日期: {today} ({['周一','周二','周三','周四','周五','周六','周日'][today.weekday()]})，"
        f"所有日期计算以此为基准。"
    )

    text = ""
    trace = []
    for chunk in run_with_stream(msg, thread_id, agent=agent, user_context=user_ctx):
        if chunk["type"] == "token":
            text += chunk["data"]
        elif chunk["type"] == "final":
            if not text: text = chunk["data"]
            trace = chunk.get("trace", [])
    return {"response": text, "trace": trace}
