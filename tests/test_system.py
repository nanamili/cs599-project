"""
系统集成测试
验证数据库初始化、RAG知识库、Agent工具调用
用法: python tests/test_system.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


def test_database_init():
    """测试数据库初始化"""
    print("=" * 50)
    print("测试1: 数据库初始化")
    print("=" * 50)

    from src.database.db import init_db, get_session
    from src.database.seed import seed_all
    from src.database.models import Equipment, User, Booking

    init_db()
    session = get_session()
    seed_all(session)

    equip_count = session.query(Equipment).count()
    user_count = session.query(User).count()
    booking_count = session.query(Booking).count()

    print(f"  仪器数: {equip_count} (期望: 5)")
    print(f"  用户数: {user_count} (期望: 5)")
    print(f"  预约数: {booking_count} (期望: 9)")

    session.close()

    assert equip_count == 5, f"仪器数不正确: {equip_count}"
    assert user_count == 5, f"用户数不正确: {user_count}"
    assert booking_count == 9, f"预约数不正确: {booking_count}"
    print("  ✅ 通过\n")


def test_booking_tools():
    """测试预约工具"""
    print("=" * 50)
    print("测试2: 预约工具函数")
    print("=" * 50)

    from src.tools.booking_tools import (
        get_equipment_list, get_equipment_detail,
        check_availability, detect_conflict,
        suggest_alternatives, get_user_bookings,
    )

    # 2.1 获取仪器列表
    eq_list = get_equipment_list()
    print(f"  仪器列表: {len(eq_list)} 台")
    assert len(eq_list) == 5

    # 2.2 按类别过滤
    microscopes = get_equipment_list(category="显微镜")
    print(f"  显微镜: {len(microscopes)} 台")
    assert len(microscopes) == 1

    # 2.3 获取仪器详情
    detail = get_equipment_detail(1)
    print(f"  电镜详情: {detail['name']}")
    assert "透射" in detail["name"]

    # 2.4 检查可用性（种子数据：下周一赵教授已预约9-13点）
    from datetime import date, timedelta
    today = date.today()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    next_monday = str(monday + timedelta(days=7))

    avail = check_availability(1, next_monday, 9, 4)
    print(f"  可用性检查 ({next_monday} 9-13): 可用={avail['available']}, 冲突={avail['conflict_count']}个")
    assert avail["available"] is False  # 赵教授已预约
    assert avail["conflict_count"] >= 1

    # 2.5 冲突检测
    conflict = detect_conflict(1, next_monday, 9, 4)
    print(f"  冲突检测: {conflict.has_conflict}")
    assert conflict.has_conflict is True

    # 2.6 替代方案推荐
    alternatives = suggest_alternatives(1, next_monday, 4)
    print(f"  替代方案: {len(alternatives)} 个")
    assert len(alternatives) > 0

    # 2.7 用户预约
    bookings = get_user_bookings(1)
    print(f"  张三的预约: {len(bookings)} 条")
    assert len(bookings) >= 1

    print("  ✅ 全部通过\n")


def test_rag_tools():
    """测试RAG工具"""
    print("=" * 50)
    print("测试3: RAG知识库工具")
    print("=" * 50)

    from src.rag.retriever import init_knowledge_base
    from src.tools.rag_tools import search_equipment_sop, get_sop_summary

    # 初始化
    store = init_knowledge_base()
    print(f"  知识库块数: {store.collection.count()}")

    # 3.1 语义检索
    results = search_equipment_sop("电镜样品怎么制备？", top_k=3)
    print(f"  '电镜样品制备' 检索结果: {len(results)} 条")
    assert len(results) > 0
    assert any("样品" in r["content"] for r in results)

    # 3.2 SOP摘要
    summary = get_sop_summary("透射电镜")
    print(f"  电镜SOP摘要: 安全项={len(summary.get('safety_notices', []))}, 规则项={len(summary.get('booking_rules', []))}")
    assert summary["has_full_sop"]

    print("  ✅ 全部通过\n")


def test_monitor_tools():
    """测试监控工具"""
    print("=" * 50)
    print("测试4: 异常监控工具")
    print("=" * 50)

    from src.tools.monitor_tools import (
        check_anomalies, generate_usage_stats, get_violation_history
    )

    # 4.1 异常检测
    anomalies = check_anomalies(days=30)
    print(f"  异常检测（30天）: {len(anomalies)} 条")
    for a in anomalies:
        print(f"    [{a['severity']}] {a['type']}: {a.get('detail', '')[:80]}")
    assert len(anomalies) > 0  # 种子数据中包含违规记录

    # 4.2 使用统计
    stats = generate_usage_stats(days=30)
    print(f"  使用统计: {stats['total_bookings']} 条预约, {stats['total_hours']} 机时")
    assert stats["total_bookings"] > 0

    # 4.3 违规历史
    violations = get_violation_history(days=30)
    print(f"  违规记录: {len(violations)} 条")

    print("  ✅ 全部通过\n")


def test_agent_requires_api():
    """测试 Agent（需要 API Key）"""
    print("=" * 50)
    print("测试5: Agent 基本功能（需要 DEEPSEEK_API_KEY）")
    print("=" * 50)

    import os
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("  ⚠️ 未设置 DEEPSEEK_API_KEY，跳过 Agent 测试")
        return

    from src.agents.graph import create_agent

    agent = create_agent()
    print("  Agent 图创建成功")

    # 测试简单请求
    config = {"configurable": {"thread_id": "test_session"}}
    try:
        result = agent.invoke(
            {"messages": ["有哪些仪器可用？"]},
            config=config,
        )
        messages = result.get("messages", [])
        response_found = any(
            hasattr(m, "content") and m.content and len(m.content) > 20
            for m in messages
        )
        print(f"  响应消息数: {len(messages)}")
        print(f"  有有效响应: {response_found}")
        assert response_found, "Agent 未返回有效响应"
    except Exception as e:
        print(f"  ❌ Agent 调用失败: {e}")
        raise

    print("  ✅ 通过\n")


def main():
    print("\n🧪 LabAgent 系统集成测试\n")

    all_passed = True

    try:
        test_database_init()
    except Exception as e:
        print(f"❌ 测试1失败: {e}\n")
        all_passed = False

    try:
        test_booking_tools()
    except Exception as e:
        print(f"❌ 测试2失败: {e}\n")
        all_passed = False

    try:
        test_rag_tools()
    except Exception as e:
        print(f"❌ 测试3失败: {e}\n")
        all_passed = False

    try:
        test_monitor_tools()
    except Exception as e:
        print(f"❌ 测试4失败: {e}\n")
        all_passed = False

    try:
        test_agent_requires_api()
    except Exception as e:
        print(f"❌ 测试5失败: {e}\n")
        all_passed = False

    print("=" * 50)
    if all_passed:
        print("🎉 所有测试通过！")
    else:
        print("⚠️ 部分测试失败，请检查上方输出")
    print("=" * 50)


if __name__ == "__main__":
    main()
