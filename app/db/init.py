from alembic.command import upgrade
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

from app.core.config import settings
from app.db import Base
from app.log import logger

# 全局数据库引擎和Session工厂
Engine = None
SessionLocal = None

def init_db():
    """
    初始化数据库连接
    """
    global Engine, SessionLocal
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL环境变量未设置")

    Engine = create_engine(
        db_url,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        echo=settings.DB_ECHO
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=Engine)
    
    # 创建所有表
    Base.metadata.create_all(bind=Engine)

def update_db():
    """
    执行数据库迁移
    """
    try:
        alembic_cfg = Config()
        alembic_cfg.set_main_option('script_location', str(settings.ROOT_PATH / 'database'))
        upgrade(alembic_cfg, 'head')
    except Exception as e:
        logger.error(f'数据库更新失败：{str(e)}')
