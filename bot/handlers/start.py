"""Handlers: /start, /help, /lang"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from bot.services.user import get_or_create_user, update_user_lang
from bot.utils.i18n import t
from bot.utils.lang_detect import LANG_LABELS

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    text = update.message.text or ""
    user = await get_or_create_user(tg_user, first_message=text)
    lang = user.lang

    name = user.first_name or "друг"
    if user.created_at == user.created_at:  # always true — check if new user
        msg = t("welcome", lang)
    else:
        msg = t("welcome_back", lang, name=name)

    keyboard = [
        [
            InlineKeyboardButton(t("btn_catalog", lang), callback_data="catalog"),
            InlineKeyboardButton(t("btn_order", lang), callback_data="order"),
        ],
        [
            InlineKeyboardButton(t("btn_subscribe", lang), callback_data="subscribe"),
            InlineKeyboardButton(t("btn_cart", lang), callback_data="cart"),
        ],
    ]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    user = await get_or_create_user(tg_user)
    await update.message.reply_text(t("help", user.lang))


async def cmd_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"setlang:{code}")]
        for code, label in LANG_LABELS.items()
    ]
    tg_user = update.effective_user
    user = await get_or_create_user(tg_user)
    await update.message.reply_text(
        t("choose_language", user.lang),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def cb_setlang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    if lang not in ("lv", "ru", "en"):
        return
    await update_user_lang(query.from_user.id, lang)
    await query.edit_message_text(t("language_set", lang))


def register(app):
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("lang", cmd_lang))
    app.add_handler(CallbackQueryHandler(cb_setlang, pattern=r"^setlang:"))
