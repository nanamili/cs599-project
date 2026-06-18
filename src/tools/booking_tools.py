"""
预约管理工具 — Scheduler Agent 的工具箱
提供仪器查询、可用性检测、预约创建、冲突检测等功能
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from ..database.db import get_session
from ..database.models import Equipment, Booking, User


# ============================================
# 数据类
# ============================================

@dataclass
class AvailabilitySlot:
    """可用时间段"""
    start_hour: int
    end_hour: int
    is_available: bool


@dataclass
class ConflictInfo:
    """冲突信息"""
    has_conflict: bool
    conflicting_booking: Optional[Dict[str, Any]] = None
    message: str = ""


@dataclass
class AlternativeSuggestion:
    """替代方案"""
    equipment_id: int
    equipment_name: str
    date: str
    start_hour: int
    duration_hours: int
    reason: str


# ============================================
# 工具函数
# ============================================

def get_equipment_list(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    获取仪器列表

    Args:
        category: 可选过滤 - 显微镜 / 光谱仪 / 计算资源 / 衍射仪 / 其他
    """
    session = get_session()
    try:
        query = session.query(Equipment).filter(Equipment.status != "报废")
        if category:
            query = query.filter(Equipment.category == category)
        equipments = query.all()

        return [
            {
                "id": e.id,
                "name": e.name,
                "category": e.category,
                "location": e.location,
                "requires_cert": e.requires_cert,
                "cert_level_required": e.cert_level_required,
                "max_hours_per_booking": e.max_hours_per_booking,
                "hourly_cost": e.hourly_cost,
                "status": e.status,
            }
            for e in equipments
        ]
    finally:
        session.close()


def get_equipment_detail(equipment_id: int) -> Optional[Dict[str, Any]]:
    """获取仪器详细信息"""
    session = get_session()
    try:
        e = session.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not e:
            return None
        return {
            "id": e.id,
            "name": e.name,
            "category": e.category,
            "location": e.location,
            "requires_cert": e.requires_cert,
            "cert_level_required": e.cert_level_required,
            "max_hours_per_booking": e.max_hours_per_booking,
            "hourly_cost": e.hourly_cost,
            "status": e.status,
        }
    finally:
        session.close()


def check_availability(
    equipment_id: int,
    check_date: str,
    start_hour: int,
    duration_hours: int,
) -> Dict[str, Any]:
    """
    检查仪器在指定时间段的可用性

    Args:
        equipment_id: 仪器ID
        check_date: 日期 (YYYY-MM-DD)
        start_hour: 开始小时 (0-23)
        duration_hours: 持续时长

    Returns:
        {available: bool, conflicts: [...], time_slot: {...}}
    """
    session = get_session()
    try:
        # 验证仪器存在
        equipment = session.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment:
            return {"available": False, "error": f"仪器不存在: ID={equipment_id}"}

        if equipment.status != "可用":
            return {"available": False, "error": f"仪器当前状态: {equipment.status}"}

        # 检查时长限制
        if duration_hours > equipment.max_hours_per_booking:
            return {
                "available": False,
                "error": f"超过单次最长预约时长 ({equipment.max_hours_per_booking}小时)",
            }

        # 查询该日期该仪器的所有预约
        booking_date = datetime.strptime(check_date, "%Y-%m-%d").date()
        existing = (
            session.query(Booking)
            .filter(
                Booking.equipment_id == equipment_id,
                Booking.booking_date == booking_date,
                Booking.status.in_(["已确认"]),  # 只检查活跃预约
            )
            .all()
        )

        # 检测时间冲突
        conflicts = []
        request_start = start_hour
        request_end = start_hour + duration_hours

        for bk in existing:
            bk_end = bk.start_hour + bk.duration_hours
            # 时间段重叠检测
            if request_start < bk_end and request_end > bk.start_hour:
                conflicts.append({
                    "booking_id": bk.id,
                    "user": bk.user.name if bk.user else "未知",
                    "start_hour": bk.start_hour,
                    "duration_hours": bk.duration_hours,
                    "purpose": bk.purpose or "未填写",
                })

        available = len(conflicts) == 0

        return {
            "available": available,
            "equipment_name": equipment.name,
            "date": check_date,
            "start_hour": start_hour,
            "duration_hours": duration_hours,
            "end_hour": start_hour + duration_hours,
            "conflicts": conflicts,
            "conflict_count": len(conflicts),
        }
    finally:
        session.close()


def create_booking(
    equipment_id: int,
    user_id: int,
    booking_date: str,
    start_hour: int,
    duration_hours: int,
    purpose: str = "",
) -> Dict[str, Any]:
    """
    创建仪器预约（自动冲突检测）

    如果存在冲突，创建失败并返回冲突信息和建议。
    """
    session = get_session()
    try:
        # 1. 可用性检查
        availability = check_availability(
            equipment_id, booking_date, start_hour, duration_hours
        )
        if not availability.get("available"):
            # 尝试找替代方案
            alternatives = suggest_alternatives(equipment_id, booking_date, duration_hours)
            return {
                "success": False,
                "message": "预约时间段存在冲突",
                "conflict_details": availability.get("conflicts", []),
                "suggested_alternatives": alternatives,
            }

        # 2. 验证用户和仪器
        user = session.query(User).filter(User.id == user_id).first()
        equipment = session.query(Equipment).filter(Equipment.id == equipment_id).first()

        if not user:
            return {"success": False, "message": f"用户不存在: ID={user_id}"}
        if not equipment:
            return {"success": False, "message": f"仪器不存在: ID={equipment_id}"}

        # 3. SDD 规格驱动验证
        from src.spec_loader import get_spec
        spec = get_spec()
        spec_result = spec.validate_booking(equipment_id, user.cert_level, duration_hours)
        if not spec_result["valid"]:
            return {"success": False, "message": f"SDD验证失败: {'; '.join(spec_result['issues'])}"}

        # 4. 检查资质
        if equipment.requires_cert and user.cert_level < equipment.cert_level_required:
            return {
                "success": False,
                "message": (
                    f"用户 {user.name} 证书等级({user.cert_level}) "
                    f"不满足仪器要求({equipment.cert_level_required})"
                ),
            }

        # 3.5 检查用户自身时间冲突（不允许同用户重叠预约）
        booking_date_obj = datetime.strptime(booking_date, "%Y-%m-%d").date()
        user_existing = (
            session.query(Booking)
            .filter(
                Booking.user_id == user_id,
                Booking.booking_date == booking_date_obj,
                Booking.status.in_(["已确认"]),
                Booking.equipment_id != equipment_id,  # 不同仪器
            )
            .all()
        )
        req_start = start_hour
        req_end = start_hour + duration_hours
        user_conflicts = []
        for ub in user_existing:
            ub_end = ub.start_hour + ub.duration_hours
            if req_start < ub_end and req_end > ub.start_hour:
                user_conflicts.append({
                    "booking_id": ub.id,
                    "equipment_name": ub.equipment.name if ub.equipment else "未知",
                    "start_hour": ub.start_hour,
                    "duration_hours": ub.duration_hours,
                })
        if user_conflicts:
            c = user_conflicts[0]
            return {
                "success": False,
                "message": (
                    f"❌ 时间冲突！您在同一时段 ({booking_date} {c['start_hour']:02d}:00-{c['start_hour']+c['duration_hours']:02d}:00) "
                    f"已预约 {c['equipment_name']}，不能同时预约多台仪器。"
                ),
            }

        # 4. 创建预约
        booking = Booking(
            equipment_id=equipment_id,
            user_id=user_id,
            booking_date=datetime.strptime(booking_date, "%Y-%m-%d").date(),
            start_hour=start_hour,
            duration_hours=duration_hours,
            purpose=purpose,
            status="已确认",
        )
        session.add(booking)
        session.commit()

        # 估算费用
        estimated_cost = equipment.hourly_cost * duration_hours

        return {
            "success": True,
            "message": "预约成功！",
            "booking_id": booking.id,
            "equipment_name": equipment.name,
            "date": booking_date,
            "time_slot": f"{start_hour:02d}:00 - {start_hour + duration_hours:02d}:00",
            "user_name": user.name,
            "estimated_cost": estimated_cost,
        }
    finally:
        session.close()


def detect_conflict(
    equipment_id: int, booking_date: str, start_hour: int, duration_hours: int
) -> ConflictInfo:
    """检测指定时间段是否存在预约冲突"""
    result = check_availability(equipment_id, booking_date, start_hour, duration_hours)

    if result.get("available"):
        return ConflictInfo(
            has_conflict=False,
            message=f"{result.get('equipment_name', '仪器')} 在 "
                    f"{booking_date} {start_hour:02d}:00 可用",
        )
    else:
        return ConflictInfo(
            has_conflict=True,
            conflicting_booking=result.get("conflicts", [{}])[0] if result.get("conflicts") else None,
            message=f"检测到 {result.get('conflict_count', 0)} 个时间冲突",
        )


def suggest_alternatives(
    equipment_id: int,
    target_date: str,
    duration_hours: int,
) -> List[Dict[str, Any]]:
    """
    智能推荐替代方案
    - 优先推荐同仪器同一天的相邻空闲时段
    - 其次推荐同仪器前后3天的空闲时段
    - 最后推荐同类仪器
    """
    session = get_session()
    try:
        equipment = session.query(Equipment).filter(Equipment.id == equipment_id).first()
        if not equipment:
            return []

        alternatives = []
        target = datetime.strptime(target_date, "%Y-%m-%d").date()

        # 策略1: 同一天的空闲时段
        day_availability = _get_day_free_slots(session, equipment, target, duration_hours)
        for slot in day_availability[:3]:
            alternatives.append({
                "type": "同天替代",
                "equipment_id": equipment.id,
                "equipment_name": equipment.name,
                "date": str(target),
                "start_hour": slot["start"],
                "duration_hours": duration_hours,
                "reason": f"同天 {slot['start']:02d}:00 空闲",
            })

        # 策略2: 前后3天的空闲时段
        for offset in [1, -1, 2, -2, 3, -3]:
            alt_date = target + timedelta(days=offset)
            slots = _get_day_free_slots(session, equipment, alt_date, duration_hours)
            for slot in slots[:1]:
                alternatives.append({
                    "type": "邻近日期",
                    "equipment_id": equipment.id,
                    "equipment_name": equipment.name,
                    "date": str(alt_date),
                    "start_hour": slot["start"],
                    "duration_hours": duration_hours,
                    "reason": f"{alt_date}（周{_weekday_cn(alt_date)}）{slot['start']:02d}:00 空闲",
                })

        # 策略3: 同类仪器
        if len(alternatives) < 3:
            similar = (
                session.query(Equipment)
                .filter(
                    Equipment.category == equipment.category,
                    Equipment.id != equipment.id,
                    Equipment.status == "可用",
                )
                .all()
            )
            for sim in similar[:2]:
                slots = _get_day_free_slots(session, sim, target, duration_hours)
                if slots:
                    alternatives.append({
                        "type": "同类仪器",
                        "equipment_id": sim.id,
                        "equipment_name": sim.name,
                        "date": str(target),
                        "start_hour": slots[0]["start"],
                        "duration_hours": duration_hours,
                        "reason": f"同类型仪器 {sim.name}（{sim.location}）",
                    })

        return alternatives[:5]
    finally:
        session.close()


def get_user_bookings(user_id: int) -> List[Dict[str, Any]]:
    """获取用户的所有预约记录"""
    session = get_session()
    try:
        bookings = (
            session.query(Booking)
            .filter(Booking.user_id == user_id)
            .order_by(Booking.booking_date.desc())
            .limit(20)
            .all()
        )
        return [
            {
                "booking_id": b.id,
                "equipment_name": b.equipment.name if b.equipment else "未知",
                "date": str(b.booking_date),
                "start_hour": b.start_hour,
                "duration_hours": b.duration_hours,
                "purpose": b.purpose or "未填写",
                "status": b.status,
            }
            for b in bookings
        ]
    finally:
        session.close()


def cancel_booking(booking_id: int) -> Dict[str, Any]:
    """取消预约"""
    session = get_session()
    try:
        booking = session.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return {"success": False, "message": f"预约不存在: ID={booking_id}"}
        if booking.status != "已确认":
            return {"success": False, "message": f"预约状态为 '{booking.status}'，无法取消"}

        booking.status = "已取消"
        session.commit()
        return {
            "success": True,
            "message": f"预约已取消（{booking.equipment.name}, {booking.booking_date}）",
        }
    finally:
        session.close()


# ============================================
# 内部辅助函数
# ============================================

def _get_day_free_slots(
    session, equipment: Equipment, target_date: date, duration_hours: int
) -> List[Dict[str, int]]:
    """获取某台仪器在某天的所有可用时间段"""
    bookings = (
        session.query(Booking)
        .filter(
            Booking.equipment_id == equipment.id,
            Booking.booking_date == target_date,
            Booking.status.in_(["已确认"]),
        )
        .all()
    )

    # 构建占用位图（8:00 - 22:00）
    occupied = [False] * 24
    for bk in bookings:
        for h in range(bk.start_hour, min(bk.start_hour + bk.duration_hours, 24)):
            occupied[h] = True

    # 查找连续空闲时间段
    free_slots = []
    hour = 8  # 从早上8点开始
    while hour <= 22 - duration_hours:
        if all(not occupied[h] for h in range(hour, hour + duration_hours)):
            free_slots.append({"start": hour, "end": hour + duration_hours})
            hour += 1  # 逐小时检查
        else:
            hour += 1

    return free_slots


def _weekday_cn(d: date) -> str:
    """日期转中文星期"""
    days = ["一", "二", "三", "四", "五", "六", "日"]
    return days[d.weekday()]
