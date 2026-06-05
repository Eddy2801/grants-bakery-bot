"""
Main message handler — routes all free-text to intent router → LLM agent or fast handler.
Also handles text input for multi-step flows (address entry, etc.)
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.agent.router import classify, Intent
from bot.agent.llm import run_agent
from bot.services.user import get_or_create_user
from bot.services.cart import get_cart_summary
from bot.services.availability import get_available_dates_for_display, find_available_date
from bot.utils.i18n import t
from bot.utils.formatting import fmt_date

logger = logging.getLogger(__name__)


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    user = await get_or_create_user(update.effective_user, first_message=text)
    lang = user.lang
    tg_id = update.effective_user.id

    # ── Multi-step flow: waiting for text input ─────────────────
    awaiting = ctx.user_data.get("awaiting")
    if awaiting == "address":
        ctx.user_data["order_address"] = text
        ctx.user_data.pop("awaiting", None)
        # Show order summary
        from bot.handlers.order import _show_order_summary
        class _FakeQuery:
            from_user = update.effective_user
            async def edit_message_text(self, t, **kw):
                await update.message.reply_text(t, **kw)
        await _show_order_summary(_FakeQuery(), ctx, user)
        return

    if awaiting == "phone":
        from bot.services.user import update_user_phone
        await update_user_phone(tg_id, text)
        ctx.user_data.pop("awaiting", None)
        await update.message.reply_text("✓ " + text)
        return

    # ── Intent routing ──────────────────────────────────────────
    intent = classify(text)
    logger.debug("User %d intent=%s text=%r", tg_id, intent, text[:50])

    # Fast handlers (no LLM)
    if intent == Intent.CATALOG:
        from bot.handlers.catalog import _show_catalog
        await _show_catalog(update, lang, page=0)
        return

    if intent == Intent.CART:
        from bot.handlers.order import _show_cart
        await _show_cart(update, lang)
        return

    if intent == Intent.HELP:
        await update.message.reply_text(t("help", lang))
        return

    # ── LLM agent for everything else ───────────────────────────
    await update.message.chat.send_action("typing")
    try:
        response_text, pending = await run_agent(
            telegram_id=tg_id,
            user_id=user.id,
            user_message=text,
            intent=intent.value,
            lang=lang,
        )
        await update.message.reply_text(response_text)

        # If LLM decided to create an order, show confirm button
        if pending.get("pending_order"):
            po = pending["pending_order"]
            keyboard = [
                [InlineKeyboardButton(t("btn_confirm", lang), callback_data="order:confirm")],
                [InlineKeyboardButton(t("btn_cancel", lang), callback_data="cart")],
            ]
            ctx.user_data["order_date"] = po.get("delivery_date")
            ctx.user_data["order_type"] = po.get("delivery_type", "pickup")
            ctx.user_data["order_address"] = po.get("delivery_address")
            await update.message.reply_text(
                t("btn_confirm", lang),
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

        # If LLM decided to create a subscription, show confirm button
        if pending.get("pending_subscription"):
            ps = pending["pending_subscription"]
            ctx.user_data["pending_sub"] = ps
            keyboard = [
                [InlineKeyboardButton(t("btn_confirm", lang), callback_data="sub:confirm")],
                [InlineKeyboardButton(t("btn_cancel", lang), callback_data="sub:cancel")],
            ]
            await update.message.reply_text(
                t("btn_confirm", lang),
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    except Exception:
        logger.exception("LLM agent failed for user %d", tg_id)
        await update.message.reply_text(t("error_generic", lang))


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Catch-all for unhandled callbacks."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "catalog":
        from bot.handlers.catalog import _show_catalog
        user = await get_or_create_user(query.from_user)
        await _show_catalog(update, user.lang, page=0)

    elif data == "subscribe":
        user = await get_or_create_user(query.from_user)
        await query.edit_message_text(
            "Чтобы оформить подписку, напишите мне:\n"
            "«Хочу каждую среду 2 классик и 1 с шоколадом»"
        )

    elif data == "sub:cancel":
        user = await get_or_create_user(query.from_user)
        ctx.user_data.pop("pending_sub", None)
        await query.edit_message_text(t("btn_cancel", user.lang))

    elif data == "sub:confirm":
        user = await get_or_create_user(query.from_user)
        ps = ctx.user_data.get("pending_sub")
        if not ps:
            await query.edit_message_text(t("error_generic", user.lang))
            return
        await _confirm_subscription(query, ctx, user, ps)


async def _confirm_subscription(query, ctx, user, ps: dict):
    from bot.services.subscription import create_subscription
    from bot.services.payment import create_subscription_payment
    from bot.utils.formatting import fmt_days_of_week, fmt_date
    lang = user.lang
    try:
        sub = await create_subscription(
            user=user,
            items=[{"product_id": i["product_id"], "qty": i.get("quantity", 1),
                    "display_name": "", "price_cents": 0}
                   for i in ps["items"]],
            days_of_week=ps["days_of_week"],
            delivery_type=ps.get("delivery_type", "pickup"),
            delivery_address=ps.get("delivery_address"),
            lang=lang,
        )
        # Calculate weekly total from catalog
        from bot.services.catalog import get_product
        total_cents = 0
        for item in ps["items"]:
            p = await get_product(item["product_id"], lang)
            if p:
                total_cents += p["price_cents"] * item.get("quantity", 1)
        total_cents *= len(ps["days_of_week"])

        email = user.email or f"tg{user.telegram_id}@grantsbakery.lv"
        payment = await create_subscription_payment(
            sub_id=sub.id,
            total_cents=total_cents,
            client_email=email,
            description=f"Grant's Bakery subscription #{sub.id}",
        )
        keyboard = [[InlineKeyboardButton(
            f"Привязать карту и активировать (€{total_cents/100:.2f})",
            url=payment["checkout_url"],
        )]]
        days_str = fmt_days_of_week(ps["days_of_week"], lang)
        await query.edit_message_text(
            t("subscription_created", lang,
              days=days_str,
              next_date=str(sub.next_delivery_date)),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        ctx.user_data.pop("pending_sub", None)
    except Exception:
        logger.exception("Subscription creation failed")
        await query.edit_message_text(t("error_generic", user.lang))


def register(app):
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    # Catch-all callback (lowest priority)
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(handle_callback), group=99)
