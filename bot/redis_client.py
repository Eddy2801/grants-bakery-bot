import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

from bot.config import config

logger = logging.getLogger(__name__)

_pool: Optional[aioredis.ConnectionPool] = None


def get_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            config.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return aioredis.Redis(connection_pool=_pool)


async def redis_get(key: str) -> Optional[Any]:
    r = get_redis()
    val = await r.get(key)
    if val is None:
        return None
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return val


async def redis_set(key: str, value: Any, ttl: Optional[int] = None):
    r = get_redis()
    serialized = json.dumps(value, default=str)
    if ttl:
        await r.setex(key, ttl, serialized)
    else:
        await r.set(key, serialized)


async def redis_delete(key: str):
    r = get_redis()
    await r.delete(key)


async def redis_expire(key: str, ttl: int):
    r = get_redis()
    await r.expire(key, ttl)


# ── Session helpers ───────────────────────────────────────────

def _session_key(telegram_id: int) -> str:
    return f"session:{telegram_id}"


def _cart_key(telegram_id: int) -> str:
    return f"cart:{telegram_id}"


def _conv_key(telegram_id: int) -> str:
    return f"conv:{telegram_id}"


async def get_session(telegram_id: int) -> dict:
    return await redis_get(_session_key(telegram_id)) or {}


async def set_session(telegram_id: int, data: dict):
    await redis_set(_session_key(telegram_id), data, ttl=config.SESSION_TTL_SECONDS)


async def update_session(telegram_id: int, **kwargs):
    session = await get_session(telegram_id)
    session.update(kwargs)
    await set_session(telegram_id, session)


async def get_cart(telegram_id: int) -> dict:
    """Cart: {product_id: {qty, name_ru, price_with_vat}}"""
    return await redis_get(_cart_key(telegram_id)) or {}


async def set_cart(telegram_id: int, cart: dict):
    await redis_set(_cart_key(telegram_id), cart, ttl=config.CART_TTL_SECONDS)


async def clear_cart(telegram_id: int):
    await redis_delete(_cart_key(telegram_id))


async def get_conversation(telegram_id: int) -> list[dict]:
    """Last N LLM messages for context."""
    return await redis_get(_conv_key(telegram_id)) or []


async def append_message(telegram_id: int, role: str, content: str, max_messages: int = 10):
    messages = await get_conversation(telegram_id)
    messages.append({"role": role, "content": content})
    if len(messages) > max_messages:
        messages = messages[-max_messages:]
    await redis_set(_conv_key(telegram_id), messages, ttl=config.SESSION_TTL_SECONDS)


async def clear_conversation(telegram_id: int):
    await redis_delete(_conv_key(telegram_id))
