"""
LabAgent CLI 入口
支持命令行直接与 Agent 对话

用法:
    python -m src.main                  # 交互模式
    python -m src.main --help           # 查看帮助
    python -m src.main --init-only      # 仅初始化数据库和知识库
"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


def init_all():
    """初始化所有组件"""
    print("=" * 60)
    print("🧪 LabAgent — 智能实验室仪器共享预约平台")
    print("=" * 60)

    # 1. 数据库
    print("\n[1/3] 初始化数据库...")
    from src.database.db import init_db, get_session
    from src.database.seed import seed_all
    init_db()
    session = get_session()
    seed_all(session)
    session.close()

    # 2. 知识库
    print("\n[2/3] 初始化SOP知识库...")
    from src.rag.retriever import init_knowledge_base
    store = init_knowledge_base()

    # 3. Agent
    print("\n[3/3] 初始化多智能体系统...")
    from src.agents.graph import create_agent
    agent = create_agent()

    print("\n" + "=" * 60)
    print("✅ 所有组件初始化完成！输入你的请求开始对话。")
    print("   输入 'quit' 或 'exit' 退出")
    print("=" * 60 + "\n")
    return agent


def interactive_mode(agent):
    """交互模式"""
    thread_id = "cli_session"

    while True:
        try:
            user_input = input("\n🧑 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 再见！")
            break

        print("\n🤖 Agent 思考中...")
        try:
            config = {"configurable": {"thread_id": thread_id}}
            result = agent.invoke(
                {"messages": [user_input]},
                config=config,
            )

            # 提取最终回复
            response = ""
            for msg in reversed(result.get("messages", [])):
                if hasattr(msg, "content") and msg.content:
                    response = msg.content
                    break

            if response:
                print(f"\n🤖 LabAgent:\n{response}")
            else:
                print("\n🤖 LabAgent: 抱歉，未能生成回复。")

        except Exception as e:
            print(f"\n❌ 错误: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="LabAgent - 智能实验室仪器共享预约平台 CLI"
    )
    parser.add_argument(
        "--init-only", action="store_true",
        help="仅初始化数据库和知识库，不进入交互模式"
    )
    parser.add_argument(
        "--message", "-m", type=str,
        help="发送单条消息给Agent（非交互模式）"
    )
    parser.add_argument(
        "--web", action="store_true",
        help="启动 Streamlit Web 界面"
    )
    args = parser.parse_args()

    if args.web:
        import subprocess
        web_path = PROJECT_ROOT / "src" / "web" / "app.py"
        subprocess.run(["streamlit", "run", str(web_path)])
        return

    agent = init_all()

    if args.init_only:
        print("初始化完成，退出。")
        return

    if args.message:
        config = {"configurable": {"thread_id": "cli_single"}}
        result = agent.invoke(
            {"messages": [args.message]},
            config=config,
        )
        for msg in reversed(result.get("messages", [])):
            if hasattr(msg, "content") and msg.content:
                print(msg.content)
                break
        return

    # 默认：交互模式
    interactive_mode(agent)


if __name__ == "__main__":
    main()
