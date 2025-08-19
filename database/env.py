from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

from app.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    
    # 根据数据库类型配置不同的参数
    if url and "postgresql" in url:
        # PostgreSQL配置
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
    else:
        # SQLite配置
        context.configure(
            url=url,
            target_metadata=target_metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            render_as_batch=True
        )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL环境变量未设置")
        
    # 根据数据库类型选择合适的poolclass
    if db_url.startswith('postgresql'):
        # PostgreSQL推荐使用QueuePool
        pool_class = pool.QueuePool
    else:
        # 其他数据库使用NullPool
        pool_class = pool.NullPool
        
    connectable = engine_from_config(
        {"sqlalchemy.url": db_url},
        prefix="sqlalchemy.",
        poolclass=pool_class,
    )

    with connectable.connect() as connection:
        url = config.get_main_option("sqlalchemy.url")
        
        # 根据数据库类型配置不同的参数
        if url and "postgresql" in url:
            # PostgreSQL配置
            context.configure(
                connection=connection, 
                target_metadata=target_metadata
            )
        else:
            # SQLite配置
            context.configure(
                connection=connection, 
                target_metadata=target_metadata,
                render_as_batch=True
            )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()