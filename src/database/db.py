"""
数据库连接管理
"""

import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .models import Base

# 数据库文件路径
DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DB_DIR / "lab_booking.db"


def get_engine():
    """获取数据库引擎"""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        echo=False,  # 生产环境关闭SQL日志
        connect_args={"check_same_thread": False},  # SQLite多线程支持
    )
    return engine


def init_db():
    """初始化数据库（创建所有表）"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session() -> Session:
    """获取数据库会话"""
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return SessionLocal()
