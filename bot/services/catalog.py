"""
Catalog service — reads products from ERP DB with Redis caching.
Cache TTL: 5 minutes (products rarely change).
"""
import json
import logging
from typing import Optional

from bot.erp_db import erp_get_products, erp_get_product
from bot.redis_client import get_redis
from bot.utils.formatting import fmt_product_name

logger = logging.getLogger(__name__)

_CACHE_KEY = "erp:products"
_CACHE_TTL = 300  # 5 minutes


async def get_all_products(lang: str = "ru") -> list[dict]:
    """Return active products, using Redis cache."""
    r = get_redis()
    cached = await r.get(_CACHE_KEY)
    if cached:
        products = json.loads(cached)
    else:
        products = await erp_get_products()
        await r.setex(_CACHE_KEY, _CACHE_TTL, json.dumps(products, default=str))

    # Add display_name for current language
    for p in products:
        p["display_name"] = fmt_product_name(p, lang)
        p["price_cents"] = round(float(p["price_with_vat"]) * 100)

    return products


async def get_product(product_id: int, lang: str = "ru") -> Optional[dict]:
    """Return a single product by ERP id."""
    products = await get_all_products(lang)
    for p in products:
        if p["id"] == product_id:
            return p
    # Not in cache — fetch directly
    p = await erp_get_product(product_id)
    if p:
        p["display_name"] = fmt_product_name(p, lang)
        p["price_cents"] = round(float(p["price_with_vat"]) * 100)
    return p


async def format_catalog_text(products: list[dict], lang: str = "ru") -> str:
    lines = []
    for p in products:
        price = fmt_product_name(p, lang)
        lines.append(f"• {p['display_name']} — €{float(p['price_with_vat']):.2f}")
    return "\n".join(lines)


async def invalidate_cache():
    r = get_redis()
    await r.delete(_CACHE_KEY)
