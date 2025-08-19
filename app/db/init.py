from alembic.command import upgrade
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

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
        
    try:
        # 使用从DATABASE_URL解析出的配置
        db_url = f"postgresql://{DB_CONFIG['username']}"
        if DB_CONFIG.get('password'):
            db_url += f":{DB_CONFIG['password']}"
        db_url += f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            
        alembic_cfg = Config()
        alembic_cfg.set_main_option('sqlalchemy.url', db_url)
        alembic_cfg.set_main_option('script_location', str(DB_CONFIG['script_location']))
        upgrade(alembic_cfg, 'head')
    except Exception as e:
        logger.error(f'数据库更新失败：{str(e)}')