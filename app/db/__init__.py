import os
from typing import Any, Generator, List, Optional, Self, Tuple, Union, Sequence
import asyncio
from urllib.parse import urlparse

from sqlalchemy import create_engine, text, and_, select, delete, Column, Integer, Identity
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session, as_declarative, declared_attr, scoped_session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool, AsyncAdaptedQueuePool
from sqlalchemy import inspect

from app.core.config import settings


# PostgreSQL数据库URL，必须从环境变量中获取
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL环境变量未设置")

# 解析DATABASE_URL获取数据库连接信息
def _parse_database_url(url: str):
    """
    解析数据库URL，提取连接信息
    """
    parsed = urlparse(url)
    return {
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'database': parsed.path.lstrip('/') if parsed.path else 'moviepilot',
        'username': parsed.username or 'moviepilot',
        'password': parsed.password
    }

DB_CONFIG = _parse_database_url(DATABASE_URL)
IS_POSTGRESQL = True  # 固定为PostgreSQL

def get_id_column():
    """
    根据数据库类型返回合适的ID列定义
    """
    # PostgreSQL使用SERIAL类型，让数据库自动处理序列
    return Column(Integer, Identity(start=1, cycle=True), primary_key=True, index=True)


def _get_database_engine(is_async: bool = False):
    """
    获取PostgreSQL数据库引擎，支持同步和异步
    """
    # 根据池类型设置 poolclass 和相关参数
    if is_async:
        # 异步引擎使用 AsyncAdaptedQueuePool
        pool_class = NullPool if settings.DB_POOL_TYPE == "NullPool" else AsyncAdaptedQueuePool
    else:
        # 同步引擎使用 QueuePool
        pool_class = NullPool if settings.DB_POOL_TYPE == "NullPool" else QueuePool
    
    if not is_async:
        # 同步引擎配置
        db_kwargs = {
            "url": DATABASE_URL,
            "pool_pre_ping": settings.DB_POOL_PRE_PING,
            "echo": settings.DB_ECHO,
            "poolclass": pool_class,
            "pool_recycle": settings.DB_POOL_RECYCLE
        }
        
        # 当使用 QueuePool 时，添加 QueuePool 特有的参数
        if pool_class == QueuePool:
            db_kwargs.update({
                "pool_size": settings.DB_POSTGRESQL_POOL_SIZE,
                "pool_timeout": settings.DB_POOL_TIMEOUT,
                "max_overflow": settings.DB_POSTGRESQL_MAX_OVERFLOW
            })
            
        # 创建数据库引擎
        engine = create_engine(**db_kwargs)
        print(f"PostgreSQL database connected to {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

        return engine
    else:
        # 异步引擎配置
        # 处理asyncpg URL格式
        async_db_url = DATABASE_URL
        if DATABASE_URL.startswith("postgresql://"):
            async_db_url = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        
        # 数据库参数，只能使用 NullPool
        _db_kwargs = {
            "url": async_db_url,
            "pool_pre_ping": settings.DB_POOL_PRE_PING,
            "echo": settings.DB_ECHO,
            "poolclass": NullPool,
            "pool_recycle": settings.DB_POOL_RECYCLE,
        }
        # 创建异步数据库引擎
        async_engine = create_async_engine(**_db_kwargs)
        print(f"Async PostgreSQL database connected to {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

        return async_engine


# 同步数据库引擎
Engine = _get_database_engine(is_async=False)

# 异步数据库引擎
AsyncEngine = _get_database_engine(is_async=True)

# 同步会话工厂
SessionFactory = sessionmaker(bind=Engine)

# 异步会话工厂
AsyncSessionFactory = async_sessionmaker(bind=AsyncEngine, class_=AsyncSession)

# 同步多线程全局使用的数据库会话
ScopedSession = scoped_session(SessionFactory)


def get_db() -> Generator:
    """
    获取数据库会话，用于WEB请求
    :return: Session
    """
    db = None
    try:
        db = SessionFactory()
        yield db
    finally:
        if db:
            db.close()


async def get_async_db() -> AsyncSession:
    """
    获取异步数据库会话，用于异步WEB请求
    :return: AsyncSession
    """
    db = AsyncSessionFactory()
    try:
        yield db
    finally:
        await db.close()


def close_database():
    """
    关闭所有数据库连接并清理资源
    """
    try:
        # 释放同步连接池
        Engine.dispose()
        # 释放异步连接池
        AsyncEngine.dispose()
    except Exception as err:
        print(f"Error while disposing database connections: {err}")


def _get_args_db(args: tuple, kwargs: dict) -> Optional[Session]:
    """
    从参数中获取数据库Session对象
    """
    db = None
    if args:
        for arg in args:
            if isinstance(arg, Session):
                db = arg
                break
    if kwargs:
        for key, value in kwargs.items():
            if isinstance(value, Session):
                db = value
                break
    return db


def _get_args_async_db(args: tuple, kwargs: dict) -> Optional[AsyncSession]:
    """
    从参数中获取异步数据库AsyncSession对象
    """
    db = None
    if args:
        for arg in args:
            if isinstance(arg, AsyncSession):
                db = arg
                break
    if kwargs:
        for key, value in kwargs.items():
            if isinstance(value, AsyncSession):
                db = value
                break
    return db


def _update_args_db(args: tuple, kwargs: dict, db: Session) -> Tuple[tuple, dict]:
    """
    更新参数中的数据库Session对象，关键字传参时更新db的值，否则更新第1或第2个参数
    """
    if kwargs and 'db' in kwargs:
        kwargs['db'] = db
    elif args:
        if args[0] is None:
            args = (db, *args[1:])
        else:
            args = (args[0], db, *args[2:])
    return args, kwargs


def _update_args_async_db(args: tuple, kwargs: dict, db: AsyncSession) -> Tuple[tuple, dict]:
    """
    更新参数中的异步数据库AsyncSession对象，关键字传参时更新db的值，否则更新第1或第2个参数
    """
    if kwargs and 'db' in kwargs:
        kwargs['db'] = db
    elif args:
        if args[0] is None:
            args = (db, *args[1:])
        else:
            args = (args[0], db, *args[2:])
    return args, kwargs


def db_update(func):
    """
    数据库更新类操作装饰器，第一个参数必须是数据库会话或存在db参数
    """

    def wrapper(*args, **kwargs):
        # 是否关闭数据库会话
        _close_db = False
        # 从参数中获取数据库会话
        db = _get_args_db(args, kwargs)
        if not db:
            # 如果没有获取到数据库会话，创建一个
            db = ScopedSession()
            # 标记需要关闭数据库会话
            _close_db = True
            # 更新参数中的数据库会话
            args, kwargs = _update_args_db(args, kwargs, db)
        try:
            # 执行函数
            result = func(*args, **kwargs)
            # 提交事务
            db.commit()
        except Exception as err:
            # 回滚事务
            db.rollback()
            raise err
        finally:
            # 关闭数据库会话
            if _close_db:
                db.close()
        return result

    return wrapper


def async_db_update(func):
    """
    异步数据库更新类操作装饰器，第一个参数必须是异步数据库会话或存在db参数
    """

    async def wrapper(*args, **kwargs):
        # 是否关闭数据库会话
        _close_db = False
        # 从参数中获取异步数据库会话
        db = _get_args_async_db(args, kwargs)
        if not db:
            # 如果没有获取到异步数据库会话，创建一个
            db = AsyncSessionFactory()
            # 标记需要关闭数据库会话
            _close_db = True
            # 更新参数中的异步数据库会话
            args, kwargs = _update_args_async_db(args, kwargs, db)
        try:
            # 执行函数
            result = await func(*args, **kwargs)
            # 提交事务
            await db.commit()
        except Exception as err:
            # 回滚事务
            await db.rollback()
            raise err
        finally:
            # 关闭数据库会话
            if _close_db:
                await db.close()
        return result

    return wrapper


def db_query(func):
    """
    数据库查询操作装饰器，第一个参数必须是数据库会话或存在db参数
    注意：db.query列表数据时，需要转换为list返回
    """

    def wrapper(*args, **kwargs):
        # 是否关闭数据库会话
        _close_db = False
        # 从参数中获取数据库会话
        db = _get_args_db(args, kwargs)
        if not db:
            # 如果没有获取到数据库会话，创建一个
            db = ScopedSession()
            # 标记需要关闭数据库会话
            _close_db = True
            # 更新参数中的数据库会话
            args, kwargs = _update_args_db(args, kwargs, db)
        try:
            # 执行函数
            result = func(*args, **kwargs)
        except Exception as err:
            raise err
        finally:
            # 关闭数据库会话
            if _close_db:
                db.close()
        return result

    return wrapper


def async_db_query(func):
    """
    异步数据库查询操作装饰器，第一个参数必须是异步数据库会话或存在db参数
    注意：db.query列表数据时，需要转换为list返回
    """

    async def wrapper(*args, **kwargs):
        # 是否关闭数据库会话
        _close_db = False
        # 从参数中获取异步数据库会话
        db = _get_args_async_db(args, kwargs)
        if not db:
            # 如果没有获取到异步数据库会话，创建一个
            db = AsyncSessionFactory()
            # 标记需要关闭数据库会话
            _close_db = True
            # 更新参数中的异步数据库会话
            args, kwargs = _update_args_async_db(args, kwargs, db)
        try:
            # 执行函数
            result = await func(*args, **kwargs)
        except Exception as err:
            raise err
        finally:
            # 关闭数据库会话
            if _close_db:
                await db.close()
        return result

    return wrapper


@as_declarative()
class Base:
    id: Any
    __name__: str

    @db_update
    def create(self, db: Session):
        db.add(self)

    @async_db_update
    async def async_create(self, db: AsyncSession):
        db.add(self)
        await db.flush()
        return self

    @classmethod
    @db_query
    def get(cls, db: Session, rid: int) -> Self:
        return db.query(cls).filter(and_(cls.id == rid)).first()

    @classmethod
    @async_db_query
    async def async_get(cls, db: AsyncSession, rid: int) -> Self:
        result = await db.execute(select(cls).where(and_(cls.id == rid)))
        return result.scalars().first()

    @db_update
    def update(self, db: Session, payload: dict):
        payload = {k: v for k, v in payload.items() if v is not None}
        for key, value in payload.items():
            setattr(self, key, value)
        if inspect(self).detached:
            db.add(self)

    @async_db_update
    async def async_update(self, db: AsyncSession, payload: dict):
        payload = {k: v for k, v in payload.items() if v is not None}
        for key, value in payload.items():
            setattr(self, key, value)
        if inspect(self).detached:
            db.add(self)

    @classmethod
    @db_update
    def delete(cls, db: Session, rid):
        db.query(cls).filter(and_(cls.id == rid)).delete()

    @classmethod
    @async_db_update
    async def async_delete(cls, db: AsyncSession, rid):
        result = await db.execute(select(cls).where(and_(cls.id == rid)))
        user = result.scalars().first()
        if user:
            await db.delete(user)

    @classmethod
    @db_update
    def truncate(cls, db: Session):
        db.query(cls).delete()

    @classmethod
    @async_db_update
    async def async_truncate(cls, db: AsyncSession):
        await db.execute(delete(cls))

    @classmethod
    @db_query
    def list(cls, db: Session) -> List[Self]:
        return db.query(cls).all()

    @classmethod
    @async_db_query
    async def async_list(cls, db: AsyncSession) -> Sequence[Self]:
        result = await db.execute(select(cls))
        return result.scalars().all()

    def to_dict(self):
        return {c.name: getattr(self, c.name, None) for c in self.__table__.columns}  # noqa

    @declared_attr
    def __tablename__(self) -> str:
        return self.__name__.lower()


class DbOper:
    """
    数据库操作基类
    """

    def __init__(self, db: Union[Session, AsyncSession] = None):
        self._db = db