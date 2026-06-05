"""
Subscription service.
Creates/manages subscriptions, syncs to ERP standing_order_items,
handles pause/cancel/modify.
"""
import logging
from datetime import date, datetime, timezone, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import AsyncSessionLocal
from bot.models import Subscription, SubscriptionItem, User
from bot.config import config
from bot.erp_db import (
    erp_upsert_standing_order, erp_deactivate_standing_order, erp_seed_plan,
)
from bot.utils.formatting import fmt_days_of_week

logger = logging.getLogger(__name__)


def _next_delivery_date(days_of_week: list[int]) -> date:
    """Find the next occurrence of any day_of_week (ISO: 1=Mon…7=Sun)."""
    today = date.today()
    for delta in range(1, 8):
        d = today + timedelta(days=delta)
        if d.isoweekday() in days_of_week:
            return d
    return today + timedelta(days=1)


def _calc_next_charge(next_delivery: date) -> datetime:
    """Charge 1 day before delivery at 09:00 UTC."""
    charge_day = next_delivery - timedelta(days=1)
    return datetime(charge_day.year, charge_day.month, charge_day.day, 9, 0, tzinfo=timezone.utc)


def _calc_weekly_total_cents(items: list[dict], days_of_week: list[int]) -> int:
    """Total cost per week = sum(price_cents * qty) * deliveries_per_week."""
    per_delivery = sum(i["price_cents"] * i["qty"] for i in items)
    return per_delivery * len(days_of_week)


def _calc_discount(item_count_per_delivery: int) -> float:
    if item_count_per_delivery >= config.SUBSCRIPTION_DISCOUNT_THRESHOLD:
        return config.SUBSCRIPTION_DISCOUNT_PCT
    return 0.0


async def create_subscription(
    user: User,
    items: list[dict],              # [{product_id, qty, display_name, price_cents}]
    days_of_week: list[int],        # ISO: 1=Mon…7=Sun
    delivery_type: str = "pickup",
    delivery_address: str | None = None,
    omniva_locker_id: str | None = None,
    lang: str = "ru",
) -> Subscription:
    """
    Create subscription:
    1. Save to bot DB
    2. For each day_of_week × product → upsert standing_order_items in ERP
    3. Seed delivery plan for next 60 days
    """
    next_delivery = _next_delivery_date(days_of_week)
    next_charge = _calc_next_charge(next_delivery)
    item_count = sum(i["qty"] for i in items)
    discount_pct = _calc_discount(item_count)

    async with AsyncSessionLocal() as session:
        sub = Subscription(
            user_id=user.id,
            days_of_week=days_of_week,
            delivery_addr_type=delivery_type,
            delivery_address=delivery_address,
            omniva_locker_id=omniva_locker_id,
            discount_pct=discount_pct,
            next_delivery_date=next_delivery,
            next_charge_at=next_charge,
            started_at=date.today(),
            status="pending_payment",
        )
        session.add(sub)
        await session.flush()

        for item in items:
            si = SubscriptionItem(
                subscription_id=sub.id,
                erp_product_id=item["product_id"],
                product_name=item.get("display_name", ""),
                quantity=item["qty"],
            )
            session.add(si)

        await session.commit()
        await session.refresh(sub)

    return sub


async def activate_subscription(sub_id: int, klix_recurring_purchase_id: str):
    """Called after first successful payment. Activates sub and syncs to ERP."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            return

        sub.status = "active"
        sub.klix_recurring_purchase_id = klix_recurring_purchase_id
        await session.commit()
        await session.refresh(sub)

    # Sync to ERP standing orders
    await _sync_standing_orders(sub)


async def _sync_standing_orders(sub: Subscription):
    """Upsert standing_order_items in ERP for each item × day_of_week."""
    if not config.ERP_ONLINE_CLIENT_ID:
        logger.warning("ERP_ONLINE_CLIENT_ID not set — skipping ERP sync")
        return

    addr_id = _get_erp_addr_id(sub.delivery_addr_type)
    if not addr_id:
        logger.warning("No ERP addr_id for delivery type %s", sub.delivery_addr_type)
        return

    # Re-fetch items
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SubscriptionItem).where(SubscriptionItem.subscription_id == sub.id)
        )
        items = list(result.scalars().all())

    for dow in sub.days_of_week:
        for item in items:
            erp_id = await erp_upsert_standing_order(
                client_id=config.ERP_ONLINE_CLIENT_ID,
                client_address_id=addr_id,
                product_id=item.erp_product_id,
                day_of_week=dow,
                quantity=item.quantity,
            )
            # Save ERP id back (only for first dow — simplified)
            if item.erp_standing_order_item_id is None:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        update(SubscriptionItem)
                        .where(SubscriptionItem.id == item.id)
                        .values(erp_standing_order_item_id=erp_id)
                    )
                    await session.commit()

    # Seed plan for next 60 days
    today = date.today()
    await erp_seed_plan(today, today + timedelta(days=60))


async def pause_subscription(sub_id: int, paused_until: date | None = None):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Subscription).where(Subscription.id == sub_id))
        sub = result.scalar_one_or_none()
        if not sub:
            return
        sub.status = "paused"
        sub.paused_until = paused_until
        await session.commit()

    # Deactivate ERP standing orders
    await _deactivate_erp_standing_orders(sub_id)


async def resume_subscription(sub_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Subscription).where(Subscription.id == sub_id))
        sub = result.scalar_one_or_none()
        if not sub:
            return
        sub.status = "active"
        sub.paused_until = None
        next_delivery = _next_delivery_date(sub.days_of_week)
        sub.next_delivery_date = next_delivery
        sub.next_charge_at = _calc_next_charge(next_delivery)
        await session.commit()

    await _sync_standing_orders(sub)


async def cancel_subscription(sub_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Subscription).where(Subscription.id == sub_id))
        sub = result.scalar_one_or_none()
        if not sub:
            return
        sub.status = "cancelled"
        sub.cancelled_at = datetime.now(tz=timezone.utc)
        await session.commit()

    await _deactivate_erp_standing_orders(sub_id)


async def get_active_subscription(user_id: int) -> Subscription | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id, Subscription.status == "active")
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def get_subscriptions_due_for_charge() -> list[Subscription]:
    """Return active subscriptions where next_charge_at <= now."""
    now = datetime.now(tz=timezone.utc)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.status == "active",
                Subscription.next_charge_at <= now,
                Subscription.klix_recurring_purchase_id.isnot(None),
            )
        )
        return list(result.scalars().all())


async def advance_subscription(sub_id: int):
    """Called after successful recurring charge. Advance dates."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Subscription).where(Subscription.id == sub_id))
        sub = result.scalar_one_or_none()
        if not sub:
            return
        next_delivery = _next_delivery_date(sub.days_of_week)
        sub.next_delivery_date = next_delivery
        sub.next_charge_at = _calc_next_charge(next_delivery)
        await session.commit()


async def _deactivate_erp_standing_orders(sub_id: int):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SubscriptionItem).where(SubscriptionItem.subscription_id == sub_id)
        )
        items = list(result.scalars().all())
    for item in items:
        if item.erp_standing_order_item_id:
            try:
                await erp_deactivate_standing_order(item.erp_standing_order_item_id)
            except Exception:
                logger.exception("Failed to deactivate ERP standing order %d", item.erp_standing_order_item_id)


def _get_erp_addr_id(addr_type: str) -> int:
    mapping = {
        "pickup": config.ERP_ONLINE_ADDR_PICKUP,
        "omniva": config.ERP_ONLINE_ADDR_OMNIVA,
        "courier": config.ERP_ONLINE_ADDR_COURIER,
    }
    return mapping.get(addr_type, 0)
