"""
Cart service — manages the in-progress shopping cart in Redis.
Cart structure: {str(product_id): {qty, display_name, price_cents, price_with_vat}}
"""
import logging
from typing import Optional

from bot.redis_client import get_cart, set_cart, clear_cart as redis_clear_cart
from bot.services.catalog import get_product

logger = logging.getLogger(__name__)


async def add_to_cart(telegram_id: int, product_id: int, qty: int, lang: str = "ru") -> dict:
    """Add qty of product to cart. Returns updated cart."""
    cart = await get_cart(telegram_id)
    key = str(product_id)
    if key in cart:
        cart[key]["qty"] += qty
    else:
        product = await get_product(product_id, lang)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        cart[key] = {
            "qty": qty,
            "display_name": product["display_name"],
            "price_cents": product["price_cents"],
            "erp_product_id": product_id,
        }
    await set_cart(telegram_id, cart)
    return cart


async def remove_from_cart(telegram_id: int, product_id: int) -> dict:
    cart = await get_cart(telegram_id)
    cart.pop(str(product_id), None)
    await set_cart(telegram_id, cart)
    return cart


async def set_qty(telegram_id: int, product_id: int, qty: int) -> dict:
    cart = await get_cart(telegram_id)
    key = str(product_id)
    if qty <= 0:
        cart.pop(key, None)
    elif key in cart:
        cart[key]["qty"] = qty
    await set_cart(telegram_id, cart)
    return cart


async def clear(telegram_id: int):
    await redis_clear_cart(telegram_id)


async def get_cart_summary(telegram_id: int, lang: str = "ru") -> dict:
    """
    Returns {items: [...], subtotal_cents, item_count, is_empty}.
    """
    cart = await get_cart(telegram_id)
    items = []
    subtotal_cents = 0
    for pid_str, info in cart.items():
        line_total = info["price_cents"] * info["qty"]
        subtotal_cents += line_total
        items.append({
            "product_id": int(pid_str),
            "display_name": info["display_name"],
            "qty": info["qty"],
            "price_cents": info["price_cents"],
            "line_total_cents": line_total,
        })
    return {
        "items": items,
        "subtotal_cents": subtotal_cents,
        "item_count": sum(i["qty"] for i in items),
        "is_empty": len(items) == 0,
    }
