"""Order flow handler — /order, /cart, cart management."""
import logging
from datetime import date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from bot.services.user import get_or_create_user
from bot.services.cart import get_cart_summary, clear
from bot.services.order import create_pending_order, DELIVERY_COSTS
from bot.services.availability import find_available_date, get_available_dates_for_display
from bot.services.payment import create_order_payment
from bot.utils.i18n import t
from bot.utils.formatting import fmt_date, fmt_price

logger = logging.getLogger(__name__)


async def cmd_cart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user)
    await _show_cart(update, user.lang)


async def _show_cart(update, lang: str):
    tg_id = (update.message or update.callback_query).from_user.id
    summary = await get_cart_summary(tg_id, lang)

    if summary["is_empty"]:
        text = t("cart_empty", lang)
        keyboard = [[InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog:0")]]
    else:
        lines = [t("cart_title", lang)]
        for item in summary["items"]:
            lines.append(t("cart_item", lang,
                           name=item["display_name"],
                           qty=item["qty"],
                           total=fmt_price(item["line_total_cents"])))
        lines.append(t("cart_total", lang, total=fmt_price(summary["subtotal_cents"])))
        text = "\n".join(lines)
        keyboard = [
            [InlineKeyboardButton(t("btn_order", lang), callback_data="order:start")],
            [InlineKeyboardButton("🗑 " + t("cart_cleared", lang), callback_data="cart:clear")],
        ]

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def cb_cart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = await get_or_create_user(query.from_user)

    if query.data == "cart:clear":
        await clear(query.from_user.id)
        await query.edit_message_text(t("cart_cleared", user.lang))
        return

    await _show_cart(update, user.lang)


async def cmd_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user)
    await _start_order(update, user)


async def _start_order(update, user):
    tg_id = (update.message or update.callback_query).from_user.id
    lang = user.lang
    summary = await get_cart_summary(tg_id, lang)

    if summary["is_empty"]:
        text = t("cart_empty", lang)
        if update.message:
            await update.message.reply_text(text)
        else:
            await update.callback_query.edit_message_text(text)
        return

    # Show available dates
    dates = await get_available_dates_for_display(days_ahead=10)
    if not dates:
        await (update.message or update.callback_query.message).reply_text(t("error_generic", lang))
        return

    items = [{"product_id": i["product_id"], "qty": i["qty"]} for i in summary["items"]]
    avail = await find_available_date(items)
    suggested = avail["date"]

    keyboard = []
    for d_info in dates[:7]:
        d = d_info["date"]
        label = fmt_date(d, lang)
        if d == suggested:
            label = "✓ " + label
        keyboard.append([InlineKeyboardButton(label, callback_data=f"order:date:{d.isoformat()}")])

    text = t("ask_delivery_date", lang, dates="\n".join(fmt_date(d["date"], lang) for d in dates[:7]))

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def cb_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = await get_or_create_user(query.from_user)
    parts = query.data.split(":")
    action = parts[1] if len(parts) > 1 else ""

    if action == "start":
        await _start_order(update, user)

    elif action == "date":
        # User picked delivery date — ask delivery type
        chosen_date = parts[2]
        ctx.user_data["order_date"] = chosen_date
        lang = user.lang
        courier_price = fmt_price(DELIVERY_COSTS["courier"])
        text = t("ask_delivery_type", lang, courier_price=courier_price)
        keyboard = [
            [InlineKeyboardButton(t("btn_pickup", lang), callback_data="order:type:pickup")],
            [InlineKeyboardButton(t("btn_omniva", lang), callback_data="order:type:omniva")],
            [InlineKeyboardButton(t("btn_courier", lang), callback_data="order:type:courier")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == "type":
        delivery_type = parts[2]
        ctx.user_data["order_type"] = delivery_type
        lang = user.lang

        if delivery_type in ("omniva", "courier"):
            # Ask for address
            ctx.user_data["awaiting"] = "address"
            await query.edit_message_text(t("ask_address", lang))
        else:
            # Self-pickup — show summary
            await _show_order_summary(query, ctx, user)

    elif action == "confirm":
        await _confirm_order(query, ctx, user)


async def _show_order_summary(query, ctx, user):
    lang = user.lang
    delivery_date = ctx.user_data.get("order_date")
    delivery_type = ctx.user_data.get("order_type", "pickup")
    address = ctx.user_data.get("order_address", "")
    summary = await get_cart_summary(query.from_user.id, lang)

    items_text = "\n".join(
        f"  • {i['display_name']} × {i['qty']} — €{i['line_total_cents']/100:.2f}"
        for i in summary["items"]
    )
    delivery_cents = DELIVERY_COSTS.get(delivery_type, 0)
    delivery_text = f"€{delivery_cents/100:.2f}" if delivery_cents else t("btn_pickup", lang)
    total = (summary["subtotal_cents"] + delivery_cents) / 100

    text = t("order_summary", lang,
             items=items_text,
             delivery=delivery_text,
             total=f"{total:.2f}",
             date=delivery_date)

    keyboard = [
        [InlineKeyboardButton(t("btn_confirm", lang), callback_data="order:confirm")],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data="order:start")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def _confirm_order(query, ctx, user):
    lang = user.lang
    delivery_date_str = ctx.user_data.get("order_date")
    delivery_type = ctx.user_data.get("order_type", "pickup")
    address = ctx.user_data.get("order_address")

    if not delivery_date_str:
        await query.edit_message_text(t("error_generic", lang))
        return

    try:
        order = await create_pending_order(
            user=user,
            delivery_date=date.fromisoformat(delivery_date_str),
            delivery_type=delivery_type,
            delivery_address=address,
            lang=lang,
        )
        # Create Klix payment
        email = user.email or f"tg{user.telegram_id}@grantsbakery.lv"
        payment = await create_order_payment(
            order_id=order.id,
            total_cents=order.total_cents,
            client_email=email,
            description=f"Grant's Bakery order #{order.id}",
        )
        # Save checkout URL to order
        from sqlalchemy import update
        from bot.database import AsyncSessionLocal
        from bot.models import Order
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(Order).where(Order.id == order.id).values(
                    klix_purchase_id=payment["id"],
                    klix_checkout_url=payment["checkout_url"],
                    status="awaiting_payment",
                )
            )
            await session.commit()

        keyboard = [[InlineKeyboardButton(
            t("pay_button", lang, total=fmt_price(order.total_cents)),
            url=payment["checkout_url"],
        )]]
        await query.edit_message_text(
            t("payment_link", lang),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception:
        logger.exception("Order creation failed")
        await query.edit_message_text(t("error_generic", lang))


def register(app):
    app.add_handler(CommandHandler("cart", cmd_cart))
    app.add_handler(CommandHandler("order", cmd_order))
    app.add_handler(CallbackQueryHandler(cb_cart, pattern=r"^cart"))
    app.add_handler(CallbackQueryHandler(cb_order, pattern=r"^order:"))
