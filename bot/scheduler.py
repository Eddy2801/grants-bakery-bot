"""
APScheduler jobs:
 - subscription_charges: charge active subscriptions whose next_charge_at <= now (every 30 min)
 - charge_reminders: send reminder 24h before charge (every hour)
 - sync_products: refresh ERP product cache (every 15 min)
"""
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="UTC")


@scheduler.scheduled_job("interval", minutes=30, id="subscription_charges")
async def run_subscription_charges():
    from bot.services.subscription import get_subscriptions_due_for_charge, advance_subscription
    from bot.services.payment import charge_recurring
    from bot.database import AsyncSessionLocal
    from bot.models import Subscription
    from sqlalchemy import select

    logger.info("Running subscription charges job")
    due = await get_subscriptions_due_for_charge()
    for sub in due:
        try:
            # Calculate amount
            from bot.services.catalog import get_product
            from bot.database import AsyncSessionLocal
            from bot.models import SubscriptionItem
            from sqlalchemy import select as sa_select

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    sa_select(SubscriptionItem).where(SubscriptionItem.subscription_id == sub.id)
                )
                items = list(result.scalars().all())

            total_cents = 0
            for item in items:
                p = await get_product(item.erp_product_id)
                if p:
                    total_cents += p["price_cents"] * item.quantity

            # Apply discount
            if sub.discount_pct:
                total_cents = round(total_cents * (1 - sub.discount_pct / 100))

            # Get user email
            from bot.services.user import get_user_by_telegram_id
            from bot.database import AsyncSessionLocal
            from bot.models import User
            from sqlalchemy import select as ssa
            async with AsyncSessionLocal() as session:
                result = await session.execute(ssa(User).where(User.id == sub.user_id))
                user = result.scalar_one_or_none()

            email = (user.email if user else None) or f"sub{sub.id}@grantsbakery.lv"

            result = await charge_recurring(
                recurring_purchase_id=sub.klix_recurring_purchase_id,
                sub_id=sub.id,
                total_cents=total_cents,
                client_email=email,
                description=f"Grant's Bakery subscription #{sub.id}",
            )
            logger.info("Charged subscription %d: %s", sub.id, result.get("status"))
            # advance_subscription is called from webhook after paid confirmation
        except Exception:
            logger.exception("Failed to charge subscription %d", sub.id)


@scheduler.scheduled_job("interval", hours=1, id="charge_reminders")
async def send_charge_reminders():
    from bot.config import config
    from bot.database import AsyncSessionLocal
    from bot.models import Subscription, User
    from sqlalchemy import select

    now = datetime.now(tz=timezone.utc)
    reminder_window_start = now + timedelta(hours=config.CHARGE_REMINDER_HOURS - 0.5)
    reminder_window_end = now + timedelta(hours=config.CHARGE_REMINDER_HOURS + 0.5)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.status == "active",
                Subscription.next_charge_at.between(reminder_window_start, reminder_window_end),
            )
        )
        subs = list(result.scalars().all())

    for sub in subs:
        try:
            from bot.handlers.payment_webhook import _get_telegram_id_by_user_id, _notify_user
            from bot.services.catalog import get_product
            from bot.models import SubscriptionItem
            from sqlalchemy import select as sa_select

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    sa_select(SubscriptionItem).where(SubscriptionItem.subscription_id == sub.id)
                )
                items = list(result.scalars().all())

            total_cents = sum(
                (await get_product(i.erp_product_id) or {}).get("price_cents", 0) * i.quantity
                for i in items
            )
            if sub.discount_pct:
                total_cents = round(total_cents * (1 - sub.discount_pct / 100))

            from bot.utils.formatting import fmt_price
            from bot.utils.i18n import t
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(User).where(User.id == sub.user_id)
                )
                user = result.scalar_one_or_none()

            if user:
                msg = t("charge_reminder", user.lang, amount=fmt_price(total_cents))
                await _notify_user(sub.user_id, msg)
        except Exception:
            logger.exception("Failed to send reminder for sub %d", sub.id)


@scheduler.scheduled_job("interval", minutes=15, id="sync_products")
async def sync_products():
    """Refresh ERP product cache in Redis."""
    from bot.services.catalog import invalidate_cache
    await invalidate_cache()
    logger.debug("Product cache invalidated")


def start_scheduler():
    scheduler.start()
    logger.info("Scheduler started")
