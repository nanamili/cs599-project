"""
种子数据 — 预置仪器、用户和部分预约记录
用于 Agent 演示的模拟数据
"""

from datetime import date, timedelta
from sqlalchemy.orm import Session

from .models import User, Equipment, Booking


def seed_all(session: Session):
    """填充所有种子数据（幂等：已存在则跳过）"""
    _seed_users(session)
    _seed_equipment(session)
    _seed_bookings(session)
    session.commit()


def _seed_users(session: Session):
    if session.query(User).count() > 0:
        return

    users = [
        User(id=1, name="张三", role="学生", cert_level=1,
             email="zhangsan@university.edu.cn", department="材料科学与工程"),
        User(id=2, name="李四", role="学生", cert_level=0,
             email="lisi@university.edu.cn", department="化学化工学院"),
        User(id=3, name="王五", role="学生", cert_level=2,
             email="wangwu@university.edu.cn", department="物理学院"),
        User(id=4, name="赵教授", role="教师", cert_level=2,
             email="zhaopro@university.edu.cn", department="材料科学与工程"),
        User(id=5, name="管理员刘", role="管理员", cert_level=2,
             email="admin_liu@university.edu.cn", department="实验中心"),
    ]
    session.add_all(users)
    print("[OK] Seed: 5 users created")


def _seed_equipment(session: Session):
    if session.query(Equipment).count() > 0:
        return

    equipment_list = [
        Equipment(
            id=1, name="JEM-2100F 透射电子显微镜", category="显微镜",
            location="材料楼 B101", requires_cert=True, cert_level_required=2,
            max_hours_per_booking=4, hourly_cost=200.0,
        ),
        Equipment(
            id=2, name="Agilent 7900 ICP-MS", category="光谱仪",
            location="分析测试中心 C205", requires_cert=True, cert_level_required=1,
            max_hours_per_booking=8, hourly_cost=150.0,
        ),
        Equipment(
            id=3, name="StarCluster-HPC GPU节点", category="计算资源",
            location="信息楼 3F 数据中心", requires_cert=False, cert_level_required=0,
            max_hours_per_booking=24, hourly_cost=10.0,
        ),
        Equipment(
            id=4, name="Bruker D8 Advance X射线衍射仪", category="衍射仪",
            location="材料楼 B105", requires_cert=True, cert_level_required=1,
            max_hours_per_booking=4, hourly_cost=100.0,
        ),
        Equipment(
            id=5, name="Bruker 600MHz 核磁共振波谱仪", category="光谱仪",
            location="分析测试中心 C210", requires_cert=True, cert_level_required=2,
            max_hours_per_booking=2, hourly_cost=300.0,
        ),
    ]
    session.add_all(equipment_list)
    print("[OK] Seed: 5 equipment created")


def _seed_bookings(session: Session):
    if session.query(Booking).count() > 0:
        return

    today = date.today()
    d0 = today  # 今天

    bookings = [
        # ===== 今天的预约 =====
        Booking(equipment_id=1, user_id=4, booking_date=d0, start_hour=9, duration_hours=4,
                purpose="高熵合金微观结构分析", status="已确认"),
        Booking(equipment_id=2, user_id=1, booking_date=d0, start_hour=14, duration_hours=3,
                purpose="水样重金属检测", status="已确认"),
        Booking(equipment_id=3, user_id=5, booking_date=d0, start_hour=10, duration_hours=6,
                purpose="分子动力学模拟", status="已确认"),

        # ===== D+1 =====
        Booking(equipment_id=1, user_id=3, booking_date=d0+timedelta(days=1), start_hour=9, duration_hours=4,
                purpose="纳米线样品观察", status="已确认"),
        Booking(equipment_id=4, user_id=1, booking_date=d0+timedelta(days=1), start_hour=10, duration_hours=2,
                purpose="薄膜XRD物相分析", status="已确认"),
        Booking(equipment_id=2, user_id=4, booking_date=d0+timedelta(days=1), start_hour=14, duration_hours=4,
                purpose="土壤元素分析", status="已确认"),

        # ===== D+2 =====
        Booking(equipment_id=5, user_id=4, booking_date=d0+timedelta(days=2), start_hour=14, duration_hours=2,
                purpose="天然产物结构鉴定", status="已确认"),
        Booking(equipment_id=3, user_id=2, booking_date=d0+timedelta(days=2), start_hour=8, duration_hours=8,
                purpose="深度学习训练", status="已确认"),
        Booking(equipment_id=1, user_id=1, booking_date=d0+timedelta(days=2), start_hour=9, duration_hours=3,
                purpose="纳米颗粒形貌观察", status="已确认"),

        # ===== D+3 =====
        Booking(equipment_id=2, user_id=3, booking_date=d0+timedelta(days=3), start_hour=9, duration_hours=4,
                purpose="水质分析", status="已确认"),
        Booking(equipment_id=4, user_id=4, booking_date=d0+timedelta(days=3), start_hour=15, duration_hours=2,
                purpose="粉末衍射", status="已确认"),

        # ===== D+4 =====
        Booking(equipment_id=1, user_id=2, booking_date=d0+timedelta(days=4), start_hour=9, duration_hours=4,
                purpose="高温合金位错分析", status="已确认"),
        Booking(equipment_id=5, user_id=3, booking_date=d0+timedelta(days=4), start_hour=14, duration_hours=2,
                purpose="有机化合物鉴定", status="已确认"),
        Booking(equipment_id=3, user_id=1, booking_date=d0+timedelta(days=4), start_hour=10, duration_hours=4,
                purpose="CFD仿真计算", status="已确认"),

        # ===== 违规记录 =====
        Booking(equipment_id=1, user_id=2, booking_date=d0-timedelta(days=1), start_hour=9, duration_hours=4,
                purpose="样品测试（未到场）", status="爽约"),
        Booking(equipment_id=2, user_id=2, booking_date=d0-timedelta(days=2), start_hour=14, duration_hours=3,
                purpose="超时使用检测", status="已完成"),

        # ===== 历史已完成 =====
        Booking(equipment_id=1, user_id=1, booking_date=d0-timedelta(days=2), start_hour=9, duration_hours=4,
                purpose="纳米颗粒形貌观察", status="已完成"),
        Booking(equipment_id=1, user_id=4, booking_date=d0-timedelta(days=1), start_hour=14, duration_hours=4,
                purpose="高温合金位错分析", status="已完成"),
        Booking(equipment_id=2, user_id=2, booking_date=d0-timedelta(days=3), start_hour=8, duration_hours=4,
                purpose="水样重金属检测", status="已完成"),
    ]
    session.add_all(bookings)
    print(f"[OK] Seed: {len(bookings)} bookings created (with violations)")


if __name__ == "__main__":
    from .db import init_db, get_session
    init_db()
    session = get_session()
    seed_all(session)
    print("[OK] Database init complete")
    session.close()
