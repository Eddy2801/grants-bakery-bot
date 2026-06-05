from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from bot.config import config

engine = create_async_engine(
    config.bot_db_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=config.LOG_LEVEL == "DEBUG",
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create all tables (used in development; production uses Alembic)."""
    from bot.models import User, Order, OrderItem, Subscription, SubscriptionItem  # noqa
    from bot.models import Conversation, Payment, BotProduct  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
