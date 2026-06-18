"""
数据库模型定义
SQLAlchemy ORM 模型：仪器、用户、预约记录
"""

from datetime import date, time
from sqlalchemy import (
    Column, Integer, String, Date, Boolean, Float,
    ForeignKey, create_engine, CheckConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    role = Column(String(20), nullable=False, default="学生")  # 学生 / 教师 / 管理员
    cert_level = Column(Integer, default=0)  # 0=无 1=初级 2=高级
    email = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)

    # 关联
    bookings = relationship("Booking", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', role='{self.role}')>"


class Equipment(Base):
    """仪器设备模型"""
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    category = Column(String(30), nullable=False)  # microscope / spectrometer / compute / other
    location = Column(String(100), nullable=False)
    requires_cert = Column(Boolean, default=False)
    cert_level_required = Column(Integer, default=0)
    max_hours_per_booking = Column(Integer, default=4)
    status = Column(String(20), default="可用")  # 可用 / 维护中 / 报废
    hourly_cost = Column(Float, default=0.0)  # 机时费（元/小时）

    # 关联
    bookings = relationship("Booking", back_populates="equipment")

    def __repr__(self):
        return f"<Equipment(id={self.id}, name='{self.name}', category='{self.category}')>"


class Booking(Base):
    """预约记录模型"""
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    booking_date = Column(Date, nullable=False)
    start_hour = Column(Integer, nullable=False)  # 0-23
    duration_hours = Column(Integer, nullable=False)  # 1-8
    purpose = Column(String(500), nullable=True)
    status = Column(
        String(20), default="已确认"
    )  # 已确认 / 已完成 / 已取消 / 爽约

    # 关联
    equipment = relationship("Equipment", back_populates="bookings")
    user = relationship("User", back_populates="bookings")

    # 约束
    __table_args__ = (
        CheckConstraint("start_hour >= 0 AND start_hour < 24", name="ck_start_hour"),
        CheckConstraint("duration_hours >= 1 AND duration_hours <= 24", name="ck_duration"),
    )

    def __repr__(self):
        return (
            f"<Booking(id={self.id}, equip={self.equipment_id}, "
            f"date={self.booking_date}, {self.start_hour}:00, "
            f"status='{self.status}')>"
        )
