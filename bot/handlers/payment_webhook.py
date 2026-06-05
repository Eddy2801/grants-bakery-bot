"""
Klix payment webhook handler (HTTP endpoint).
python-telegram-bot does not handle non-Telegram HTTP, so this is a
standalone aiohttp route added to the Application's web server.
"""
import json
import logging

from aiohttp import web
from sqlalchemy import select

from bot.config import config
from bot.database import AsyncSessionLocal
from bot.models import Order, Subscription, Payment
from bot.services.payment import parse_webhook
from bot.services.order import mark_order_paid, mark_order_cancelled
from bot.services.subscription import activate_subscription, advance_subscription
from bot.services.user import save_recurring_token

logger = logging.getLogger(__name__)


async def klix_webhook(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400, text="Bad JSON")

    try:
        event = parse_webhook(body)
    except Exception:
        logger.exception("Failed to parse Klix webhook: %s", body)
        return web.Response(status=200, text="ok")

    logger.info("Klix webhook: purchase_id=%s status=%s ref=%s",
                event["purchase_id"], event["status"], event["reference"])

    reference = event["reference"] or ""
    status = event["status"]

    if reference.startswith("order_"):
        await _handle_order_webhook(event, reference, status)
    elif reference.startswith("sub_"):
        await _handle_subscription_webhook(event, reference, status)

    return web.Response(status=200, text="ok")


async def _handle_order_webhook(event: dict, reference: str, status: str):
    order_id = int(reference.split("_")[1])

    if status == "paid":
        order = await mark_order_paid(order_id, event["purchase_id"])
        if order and order.user_id:
            # Notify user via Telegram
            await _notify_user(
                order.user_id,
                f"✓ Заказ #{order.id} оплачен! Доставка {order.delivery_date}.",
            )

    elif status in ("cancelled", "error"):
        await mark_order_cancelled(order_id)

    # Save payment record
    async with AsyncSessionLocal() as session:
        p = Payment(
            user_id=_get_user_id_from_order(order_id),
            order_id=order_id,
            klix_purchase_id=event["purchase_id"],
            amount_cents=event["amount_cents"],
            status=status,
            type="one_time",
        )
        try:
            session.add(p)
            await session.commit()
        except Exception:
            pass  # duplicate payment_id — ignore


async def _handle_subscription_webhook(event: dict, reference: str, status: str):
    parts = reference.split("_")
    sub_id = int(parts[1])
    is_first = parts[2] == "first" if len(parts) > 2 else False

    if status == "paid":
        if is_first:
            # First payment — activate subscription, save recurring token
            await activate_subscription(sub_id, event["purchase_id"])
            # Find user by subscription
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Subscription).where(Subscription.id == sub_id)
                )
                sub = result.scalar_one_or_none()
                if sub:
                    await save_recurring_token(
                        (await _get_telegram_id_by_user_id(sub.user_id)),
                        event["purchase_id"],
                    )
                    await _notify_user(sub.user_id,
                                       f"✓ Подписка #{sub_id} активирована! Первая доставка {sub.next_delivery_date}.")
        else:
            # Recurring charge succeeded
            await advance_subscription(sub_id)


async def _notify_user(user_id: int, text: str):
    """Send notification to user via Telegram bot."""
    # Import here to avoid circular; bot app instance stored in module-level var set in main.py
    try:
        from bot.main import get_bot_app
        app = get_bot_app()
        if app:
            async with AsyncSessionLocal() as session:
                from bot.models import User
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    await app.bot.send_message(chat_id=user.telegram_id, text=text)
    except Exception:
        logger.exception("Failed to notify user %d", user_id)


async def _get_telegram_id_by_user_id(user_id: int) -> int:
    async with AsyncSessionLocal() as session:
        from bot.models import User
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        return user.telegram_id if user else 0


async def _get_user_id_from_order(order_id: int) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        return order.user_id if order else 0
