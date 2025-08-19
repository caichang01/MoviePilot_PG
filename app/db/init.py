from alembic.command import upgrade
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from urllib.parse import urlparse

from app.core.config import settings
from app.db import Base, Engine, DB_CONFIG
from app.log import logger

# 全局Session工厂
SessionLocal = None

def init_db():
    """
    初始化数据库连接
    """
    global SessionLocal
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL环境变量未设置")

    # 使用已存在的全局引擎
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=Engine)

    Base.metadata.create_all(bind=Engine)

def update_db():
    """
    执行数据库迁移
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL环境变量未设置")
        return
        
    # 解析数据库URL以获取连接信息
    parsed_url = urlparse(db_url)
    host = parsed_url.hostname or settings.DB_POSTGRESQL_HOST
    port = parsed_url.port or settings.DB_POSTGRESQL_PORT
    database = parsed_url.path.lstrip('/') if parsed_url.path else settings.DB_POSTGRESQL_DATABASE
        
    script_location = settings.ROOT_PATH / 'database'
    try:
        alembic_cfg = Config()
        alembic_cfg.set_main_option('script_location', str(script_location))
        # 仅支持PostgreSQL，使用从DATABASE_URL解析出的配置
        if DB_CONFIG.get('password'):
            db_url = f"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        else:
            db_url = f"postgresql://{DB_CONFIG['username']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            
        alembic_cfg.set_main_option('sqlalchemy.url', db_url)
        upgrade(alembic_cfg, 'head')
    except Exception as e:
        logger.error(f'数据库更新失败：{str(e)}')