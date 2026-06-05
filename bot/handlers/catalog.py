"""Catalog handler — /catalog command and inline browsing."""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from bot.services.user import get_or_create_user
from bot.services.catalog import get_all_products, get_product
from bot.services.cart import add_to_cart
from bot.utils.i18n import t
from bot.utils.formatting import fmt_product_name

logger = logging.getLogger(__name__)

_PAGE_SIZE = 5


async def cmd_catalog(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = await get_or_create_user(update.effective_user)
    await _show_catalog(update, user.lang, page=0)


async def _show_catalog(update, lang: str, page: int = 0):
    products = await get_all_products(lang)
    start = page * _PAGE_SIZE
    page_products = products[start:start + _PAGE_SIZE]

    if not page_products:
        text = "Каталог пуст. / Katalogs ir tukšs. / Catalog is empty."
        if update.message:
            await update.message.reply_text(text)
        else:
            await update.callback_query.edit_message_text(text)
        return

    lines = [t("catalog_title", lang)]
    keyboard_rows = []
    for p in page_products:
        price = f"€{float(p['price_with_vat']):.2f}"
        lines.append(f"• {p['display_name']} — {price}")
        keyboard_rows.append([
            InlineKeyboardButton(f"ℹ {p['display_name']}", callback_data=f"pdetail:{p['id']}"),
            InlineKeyboardButton(f"+ В корзину", callback_data=f"addcart:{p['id']}:1"),
        ])

    # Pagination
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("← Назад", callback_data=f"catalog:{page-1}"))
    if start + _PAGE_SIZE < len(products):
        nav_row.append(InlineKeyboardButton("Вперёд →", callback_data=f"catalog:{page+1}"))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append([InlineKeyboardButton(t("btn_cart", lang), callback_data="cart")])

    markup = InlineKeyboardMarkup(keyboard_rows)
    text = "\n".join(lines)

    if update.message:
        await update.message.reply_text(text, reply_markup=markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=markup)


async def cb_catalog(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = await get_or_create_user(query.from_user)
    page = int(query.data.split(":")[1]) if ":" in query.data else 0
    await _show_catalog(update, user.lang, page)


async def cb_product_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = await get_or_create_user(query.from_user)
    product_id = int(query.data.split(":")[1])
    p = await get_product(product_id, user.lang)
    if not p:
        await query.answer("Продукт не найден", show_alert=True)
        return
    text = t("product_detail", user.lang,
             name=p["display_name"],
             weight=p.get("weight_kg", "0.5"),
             price=f"{float(p['price_with_vat']):.2f}",
             description=p.get("description") or "")
    keyboard = [
        [InlineKeyboardButton("+ В корзину", callback_data=f"addcart:{p['id']}:1")],
        [InlineKeyboardButton("← Каталог", callback_data="catalog:0")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def cb_add_to_cart(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, product_id_str, qty_str = query.data.split(":")
    product_id = int(product_id_str)
    qty = int(qty_str)
    user = await get_or_create_user(query.from_user)
    try:
        await add_to_cart(query.from_user.id, product_id, qty, user.lang)
        p = await get_product(product_id, user.lang)
        name = p["display_name"] if p else str(product_id)
        await query.answer(t("add_to_cart", user.lang, name=name, qty=qty), show_alert=False)
    except Exception as e:
        logger.exception("add_to_cart failed")
        await query.answer(t("error_generic", user.lang), show_alert=True)


def register(app):
    app.add_handler(CommandHandler("catalog", cmd_catalog))
    app.add_handler(CallbackQueryHandler(cb_catalog, pattern=r"^catalog"))
    app.add_handler(CallbackQueryHandler(cb_product_detail, pattern=r"^pdetail:"))
    app.add_handler(CallbackQueryHandler(cb_add_to_cart, pattern=r"^addcart:"))
