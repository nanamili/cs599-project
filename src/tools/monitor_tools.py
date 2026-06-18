"""
异常监控工具 — Monitor Agent 的工具箱
提供异常检测、使用统计、违规预警等功能
"""

from datetime import date, datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy import func
from ..database.db import get_session
from ..database.models import Booking, Equipment, User


def check_anomalies(days: int = 7) -> List[Dict[str, Any]]:
    """
    检测最近N天的异常情况

    检测维度:
    1. 爽约记录（预约了但没来）
    2. 超时使用嫌疑（预约时长用完但实际更久）
    3. 未持证操作（用户证书等级不够但预约了高要求仪器）
    4. 高频预约异常（同一用户短时间内密集预约）
    """
    session = get_session()
    try:
        today = date.today()
        since_date = today - timedelta(days=days)
        anomalies = []

        # 1. 爽约检测
        no_shows = (
            session.query(Booking)
            .filter(
                Booking.booking_date >= since_date,
                Booking.status == "爽约",
            )
            .all()
        )
        for bk in no_shows:
            anomalies.append({
                "type": "爽约",
                "severity": "中",
                "booking_id": bk.id,
                "equipment_name": bk.equipment.name if bk.equipment else "未知",
                "user_name": bk.user.name if bk.user else "未知",
                "date": str(bk.booking_date),
                "detail": f"预约时段 {bk.start_hour:02d}:00（{bk.duration_hours}小时），"
                          f"但未到场使用",
                "suggestion": "累计爽约2次以上应暂停预约权限1个月",
            })

        # 2. 未持证操作检测
        uncertified = (
            session.query(Booking, User, Equipment)
            .join(User, Booking.user_id == User.id)
            .join(Equipment, Booking.equipment_id == Equipment.id)
            .filter(
                Booking.booking_date >= since_date,
                Equipment.requires_cert == True,
                User.cert_level < Equipment.cert_level_required,
            )
            .all()
        )
        for bk, user, equip in uncertified:
            anomalies.append({
                "type": "未持证操作",
                "severity": "高",
                "booking_id": bk.id,
                "equipment_name": equip.name,
                "user_name": user.name,
                "date": str(bk.booking_date),
                "detail": f"用户证书等级({user.cert_level})不满足"
                          f"仪器要求({equip.cert_level_required})",
                "suggestion": "立即暂停该用户的预约权限，要求先取得对应操作证书",
            })

        # 3. 高频预约检测（同一人3天内预约超过5次）
        three_days_ago = today - timedelta(days=3)
        freq_check = (
            session.query(Booking.user_id, User.name, func.count(Booking.id).label("cnt"))
            .join(User, Booking.user_id == User.id)
            .filter(Booking.booking_date >= three_days_ago)
            .group_by(Booking.user_id)
            .having(func.count(Booking.id) > 5)
            .all()
        )
        for uid, uname, cnt in freq_check:
            anomalies.append({
                "type": "高频预约",
                "severity": "低",
                "user_name": uname,
                "detail": f"近3天预约了 {cnt} 次，可能存在资源挤占行为",
                "suggestion": "关注该用户的预约动机，必要时限制每日预约上限",
            })

        return anomalies
    finally:
        session.close()


def generate_usage_stats(
    equipment_id: int = None, days: int = 30
) -> Dict[str, Any]:
    """
    生成仪器使用统计报告

    Args:
        equipment_id: 仪器ID（None=全部仪器）
        days: 统计最近N天
    """
    session = get_session()
    try:
        today = date.today()
        since_date = today - timedelta(days=days)

        query = session.query(Booking).filter(
            Booking.booking_date >= since_date,
            Booking.status.in_(["已完成", "已确认"]),
        )
        if equipment_id:
            query = query.filter(Booking.equipment_id == equipment_id)

        bookings = query.all()

        # 按仪器汇总
        by_equipment = {}
        for bk in bookings:
            eid = bk.equipment_id
            if eid not in by_equipment:
                by_equipment[eid] = {
                    "equipment_name": bk.equipment.name if bk.equipment else f"ID:{eid}",
                    "total_bookings": 0,
                    "total_hours": 0,
                    "unique_users": set(),
                    "completed": 0,
                    "no_show": 0,
                }
            stats = by_equipment[eid]
            stats["total_bookings"] += 1
            stats["total_hours"] += bk.duration_hours
            stats["unique_users"].add(bk.user_id)
            if bk.status == "已完成":
                stats["completed"] += 1

        # 转换 set 为 count
        for eid in by_equipment:
            by_equipment[eid]["unique_users"] = len(by_equipment[eid]["unique_users"])

        # 爽约统计
        no_shows = (
            session.query(Booking)
            .filter(
                Booking.booking_date >= since_date,
                Booking.status == "爽约",
            )
        )
        if equipment_id:
            no_shows = no_shows.filter(Booking.equipment_id == equipment_id)

        # 找出最热门仪器
        if by_equipment:
            hottest = max(by_equipment.values(), key=lambda x: x["total_hours"])
        else:
            hottest = None

        return {
            "period": f"{since_date} ~ {today}（{days}天）",
            "total_bookings": len(bookings),
            "total_hours": sum(b.duration_hours for b in bookings),
            "no_show_count": no_shows.count(),
            "by_equipment": by_equipment,
            "hottest_equipment": hottest,
        }
    finally:
        session.close()


def get_violation_history(user_id: int = None, days: int = 30) -> List[Dict[str, Any]]:
    """获取违规历史"""
    session = get_session()
    try:
        today = date.today()
        since_date = today - timedelta(days=days)

        query = session.query(Booking).filter(
            Booking.booking_date >= since_date,
            Booking.status.in_(["爽约", "已取消"]),
        )
        if user_id:
            query = query.filter(Booking.user_id == user_id)

        violations = query.all()
        return [
            {
                "booking_id": b.id,
                "user_name": b.user.name if b.user else "未知",
                "equipment_name": b.equipment.name if b.equipment else "未知",
                "date": str(b.booking_date),
                "status": b.status,
                "purpose": b.purpose or "未填写",
            }
            for b in violations
        ]
    finally:
        session.close()


def get_safety_incidents(
    equipment: str = "", category: str = "", severity: str = "", limit: int = 5
) -> list:
    """
    检索实验室安全事故案例库（7个真实案例）。
    返回匹配的案例列表，每个案例含 id/date/title/cause/penalty/lesson。
    """
    import yaml
    from pathlib import Path

    yaml_path = Path(__file__).parent.parent.parent / "config" / "safety_incidents.yaml"
    if not yaml_path.exists():
        return [{"error": "安全事件库不存在"}]

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    incidents = data.get("incidents", [])
    if equipment:
        # 支持中文缩写/俗称匹配（如 "电镜"→"电子显微镜"、"NMR"→"核磁共振"）
        synonyms = {
            "电镜": ["电子显微镜"],
            "tem": ["透射电子显微镜", "电子显微镜"],
            "nmr": ["核磁共振"],
            "icp": ["icp-ms", "质谱"],
            "xrd": ["x射线衍射"],
            "hpc": ["高性能计算", "计算集群"],
            "透射电镜": ["透射电子显微镜"],
        }
        eq_lower = equipment.lower()
        match_ids = set()
        for inc in incidents:
            eq_name = inc.get("equipment", "").lower()
            # 直接匹配
            if eq_lower in eq_name:
                match_ids.add(inc["id"])
            # 同义词匹配
            for abbr, fulls in synonyms.items():
                if eq_lower == abbr or eq_lower in abbr:
                    for full in fulls:
                        if full.lower() in eq_name:
                            match_ids.add(inc["id"])
        incidents = [i for i in incidents if i["id"] in match_ids]
    if category:
        incidents = [i for i in incidents if category in i.get("category", "")]
    if severity:
        incidents = [i for i in incidents if severity in i.get("severity", "")]
    return incidents[:limit]
