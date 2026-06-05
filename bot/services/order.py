"""
Order service — creates and manages orders.
Flow: cart → create_order (pending) → payment → confirm → ERP sync
"""
import logging
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import AsyncSessionLocal
from bot.models import Order, OrderItem, User
from bot.services.cart import get_cart_summary, clear as clear_cart
from bot.erp_db import erp_aggregate_bot_orders
from bot.config import config
from bot.utils.formatting import eur_to_cents

logger = logging.getLogger(__name__)

# Delivery costs in cents
DELIVERY_COSTS = {
    "pickup": 0,
    "omniva": 250,   # €2.50
    "courier": 500,  # €5.00
}


async def create_pending_order(
    user: User,
    delivery_date: date,
    delivery_type: str = "pickup",
    delivery_address: str | None = None,
    omniva_locker_id: str | None = None,
    recipient_name: str | None = None,
    recipient_phone: str | None = None,
    lang: str = "ru",
) -> Order:
    """
    Create order from user's current cart.
    Applies subscription discount if applicable.
    Returns Order object (not yet paid).
    """
    cart = await get_cart_summary(user.telegram_id, lang)
    if cart["is_empty"]:
        raise ValueError("Cart is empty")

    subtotal_cents = cart["subtotal_cents"]
    delivery_cents = DELIVERY_COSTS.get(delivery_type, 0)

    # Subscription discount
    discount_cents = 0
    item_count = cart["item_count"]
    if item_count >= config.SUBSCRIPTION_DISCOUNT_THRESHOLD:
        discount_cents = round(subtotal_cents * config.SUBSCRIPTION_DISCOUNT_PCT / 100)

    total_cents = subtotal_cents + delivery_cents - discount_cents

    async with AsyncSessionLocal() as session:
        order = Order(
            user_id=user.id,
            delivery_date=delivery_date,
            delivery_addr_type=delivery_type,
            delivery_address=delivery_address,
            omniva_locker_id=omniva_locker_id,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            subtotal_cents=subtotal_cents,
            delivery_cents=delivery_cents,
            discount_cents=discount_cents,
            total_cents=total_cents,
            status="pending",
        )
        session.add(order)
        await session.flush()

        for item in cart["items"]:
            oi = OrderItem(
                order_id=order.id,
                erp_product_id=item["product_id"],
                product_name=item["display_name"],
                quantity=item["qty"],
                unit_price_cents=item["price_cents"],
                line_total_cents=item["line_total_cents"],
            )
            session.add(oi)

        await session.commit()
        await session.refresh(order)

    return order


async def get_order(order_id: int) -> Order | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        return result.scalar_one_or_none()


async def get_user_orders(user_id: int, limit: int = 10) -> list[Order]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def mark_order_paid(order_id: int, klix_purchase_id: str) -> Order | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return None
        order.status = "paid"
        order.klix_purchase_id = klix_purchase_id
        order.paid_at = datetime.now(tz=timezone.utc)
        await session.commit()
        await session.refresh(order)

    # Sync to ERP production plan
    await _sync_to_erp(order)
    return order


async def mark_order_cancelled(order_id: int):
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(status="cancelled")
        )
        await session.commit()

    # Re-aggregate ERP to remove this order's quantities
    order = await get_order(order_id)
    if order:
        await _sync_to_erp_for_date(order.delivery_date, order.delivery_addr_type)


async def _sync_to_erp(order: Order):
    """Push order quantities to ERP daily_delivery_plan."""
    addr_id = _get_erp_addr_id(order.delivery_addr_type)
    if addr_id and config.ERP_ONLINE_CLIENT_ID:
        try:
            await erp_aggregate_bot_orders(order.delivery_date, addr_id, config.ERP_ONLINE_CLIENT_ID)
            async with AsyncSessionLocal() as session:
                await session.execute(
                    update(Order).where(Order.id == order.id).values(erp_synced=True)
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to sync order %d to ERP", order.id)


async def _sync_to_erp_for_date(delivery_date: date, addr_type: str):
    addr_id = _get_erp_addr_id(addr_type)
    if addr_id and config.ERP_ONLINE_CLIENT_ID:
        try:
            await erp_aggregate_bot_orders(delivery_date, addr_id, config.ERP_ONLINE_CLIENT_ID)
        except Exception:
            logger.exception("ERP sync failed for date %s", delivery_date)


def _get_erp_addr_id(addr_type: str) -> int:
    mapping = {
        "pickup": config.ERP_ONLINE_ADDR_PICKUP,
        "omniva": config.ERP_ONLINE_ADDR_OMNIVA,
        "courier": config.ERP_ONLINE_ADDR_COURIER,
    }
    return mapping.get(addr_type, 0)
