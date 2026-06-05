"""User service — get or create user from Telegram update."""
import logging
from typing import Optional

from sqlalchemy import select, update
from telegram import User as TGUser

from bot.database import AsyncSessionLocal
from bot.models import User
from bot.utils.lang_detect import detect_lang

logger = logging.getLogger(__name__)


async def get_or_create_user(tg_user: TGUser, first_message: str = "") -> User:
    """Get existing user or create new from Telegram user object."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == tg_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            return user

        # Auto-detect language
        lang = detect_lang(first_message) if first_message else (tg_user.language_code or "ru")
        if lang not in ("lv", "ru", "en"):
            lang = "ru"

        user = User(
            telegram_id=tg_user.id,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            username=tg_user.username,
            lang=lang,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info("New user: telegram_id=%d lang=%s", tg_user.id, lang)
        return user


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def update_user_lang(telegram_id: int, lang: str):
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User).where(User.telegram_id == telegram_id).values(lang=lang)
        )
        await session.commit()


async def update_user_phone(telegram_id: int, phone: str):
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User).where(User.telegram_id == telegram_id).values(phone=phone)
        )
        await session.commit()


async def save_recurring_token(telegram_id: int, klix_purchase_id: str):
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(klix_recurring_purchase_id=klix_purchase_id)
        )
        await session.commit()
