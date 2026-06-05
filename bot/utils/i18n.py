"""
Multilingual strings for LV / RU / EN.
Usage:  t("welcome", lang="ru")
        t("product_price", lang="lv", price="4.13")
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "welcome": {
        "lv": "Sveiki! Es esmu Grant's Bakery bots. Mēs cepam amatnieku rudzu maizi uz skābrās mīklas — bez raugiem, bez piedevām.\n\nVaru parādīt katalogu, palīdzēt ar pasūtījumu vai noformēt iknedēļas abonementu. Ko jūs vēlaties?",
        "ru": "Привет! Я бот пекарни Grant's Bakery. Мы печём ремесленный хлеб на закваске — без дрожжей, без добавок.\n\nМогу показать каталог, помочь с заказом или оформить подписку. Чем могу помочь?",
        "en": "Hi! I'm the Grant's Bakery bot. We bake artisan sourdough bread — no yeast, no additives.\n\nI can show you our catalog, help with an order, or set up a weekly subscription. What would you like?",
    },
    "welcome_back": {
        "lv": "Sveiki atpakaļ, {name}! Kā varu palīdzēt?",
        "ru": "С возвращением, {name}! Чем могу помочь?",
        "en": "Welcome back, {name}! How can I help you?",
    },
    "choose_language": {
        "lv": "Izvēlieties valodu:",
        "ru": "Выберите язык:",
        "en": "Choose language:",
    },
    "language_set": {
        "lv": "Valoda iestatīta: Latviešu",
        "ru": "Язык установлен: Русский",
        "en": "Language set: English",
    },
    "catalog_title": {
        "lv": "Mūsu maize:",
        "ru": "Наш хлеб:",
        "en": "Our bread:",
    },
    "catalog_item": {
        "lv": "{name} — {price} €",
        "ru": "{name} — {price} €",
        "en": "{name} — {price} €",
    },
    "product_detail": {
        "lv": "{name}\n\nSvars: {weight} kg\nCena: {price} € (ar PVN)\n\n{description}",
        "ru": "{name}\n\nВес: {weight} кг\nЦена: {price} € (с НДС)\n\n{description}",
        "en": "{name}\n\nWeight: {weight} kg\nPrice: {price} € (incl. VAT)\n\n{description}",
    },
    "add_to_cart": {
        "lv": "✓ {name} × {qty} pievienots grozam",
        "ru": "✓ {name} × {qty} добавлено в корзину",
        "en": "✓ {name} × {qty} added to cart",
    },
    "cart_empty": {
        "lv": "Jūsu grozs ir tukšs. Skatiet katalogu ar /catalog",
        "ru": "Ваша корзина пуста. Посмотрите каталог: /catalog",
        "en": "Your cart is empty. Browse the catalog: /catalog",
    },
    "cart_title": {
        "lv": "Jūsu grozs:",
        "ru": "Ваша корзина:",
        "en": "Your cart:",
    },
    "cart_item": {
        "lv": "• {name} × {qty} — {total} €",
        "ru": "• {name} × {qty} — {total} €",
        "en": "• {name} × {qty} — {total} €",
    },
    "cart_total": {
        "lv": "Kopā: {total} €",
        "ru": "Итого: {total} €",
        "en": "Total: {total} €",
    },
    "cart_cleared": {
        "lv": "Grozs iztīrīts.",
        "ru": "Корзина очищена.",
        "en": "Cart cleared.",
    },
    "ask_delivery_date": {
        "lv": "Kāda piegādes datums? Pieejamās datumi:\n{dates}",
        "ru": "Какая дата доставки? Доступные даты:\n{dates}",
        "en": "What delivery date? Available dates:\n{dates}",
    },
    "ask_delivery_type": {
        "lv": "Kā piegādāt?\n• Pašizņemšana (bezmaksas)\n• Omniva pakomāts\n• Kurjers (+{courier_price} €)",
        "ru": "Как доставить?\n• Самовывоз (бесплатно)\n• Omniva пакомат\n• Курьер (+{courier_price} €)",
        "en": "How to deliver?\n• Self-pickup (free)\n• Omniva parcel locker\n• Courier (+{courier_price} €)",
    },
    "ask_address": {
        "lv": "Norādiet piegādes adresi:",
        "ru": "Укажите адрес доставки:",
        "en": "Please provide your delivery address:",
    },
    "order_summary": {
        "lv": "Pasūtījuma kopsavilkums:\n{items}\nPiegāde: {delivery}\nKopā: {total} €\nDatums: {date}\n\nApmaksāt?",
        "ru": "Итог заказа:\n{items}\nДоставка: {delivery}\nИтого: {total} €\nДата: {date}\n\nОплатить?",
        "en": "Order summary:\n{items}\nDelivery: {delivery}\nTotal: {total} €\nDate: {date}\n\nProceed to payment?",
    },
    "payment_link": {
        "lv": "Nospiediet pogu, lai samaksātu:",
        "ru": "Нажмите кнопку для оплаты:",
        "en": "Press the button to pay:",
    },
    "pay_button": {
        "lv": "Apmaksāt {total} €",
        "ru": "Оплатить {total} €",
        "en": "Pay {total} €",
    },
    "payment_success": {
        "lv": "Paldies! Jūsu pasūtījums #{order_id} ir apstiprināts. Piegāde {date}.",
        "ru": "Спасибо! Ваш заказ #{order_id} подтверждён. Доставка {date}.",
        "en": "Thank you! Order #{order_id} confirmed. Delivery on {date}.",
    },
    "payment_failed": {
        "lv": "Maksājums neizdevās. Mēģiniet vēlreiz.",
        "ru": "Оплата не прошла. Попробуйте ещё раз.",
        "en": "Payment failed. Please try again.",
    },
    "subscription_title": {
        "lv": "Abonements",
        "ru": "Подписка",
        "en": "Subscription",
    },
    "subscription_created": {
        "lv": "Abonements izveidots! Maize tiks piegādāta katru {days}.\nNākamā piegāde: {next_date}",
        "ru": "Подписка оформлена! Хлеб будет доставляться каждый {days}.\nСледующая доставка: {next_date}",
        "en": "Subscription created! Bread will be delivered every {days}.\nNext delivery: {next_date}",
    },
    "subscription_paused": {
        "lv": "Abonements apturēts.",
        "ru": "Подписка приостановлена.",
        "en": "Subscription paused.",
    },
    "subscription_resumed": {
        "lv": "Abonements atjaunots.",
        "ru": "Подписка возобновлена.",
        "en": "Subscription resumed.",
    },
    "subscription_cancelled": {
        "lv": "Abonements atcelts.",
        "ru": "Подписка отменена.",
        "en": "Subscription cancelled.",
    },
    "no_active_subscription": {
        "lv": "Jums nav aktīva abonements.",
        "ru": "У вас нет активной подписки.",
        "en": "You have no active subscription.",
    },
    "date_frozen": {
        "lv": "Ražošana šai datumam jau ir uzsākta. Piedāvājam nākamo pieejamo datumu: {date}",
        "ru": "Производство на эту дату уже запущено. Предлагаем следующую доступную дату: {date}",
        "en": "Production for this date has started. We suggest the next available date: {date}",
    },
    "date_busy": {
        "lv": "Šī datuma kapacitāte ir ierobežota. Piedāvājam {date}.",
        "ru": "Мощности на эту дату ограничены. Предлагаем {date}.",
        "en": "Capacity for this date is limited. We suggest {date}.",
    },
    "ask_phone": {
        "lv": "Kāds ir jūsu tālrunis? (nepieciešams piegādei)",
        "ru": "Какой ваш номер телефона? (нужен для доставки)",
        "en": "What's your phone number? (needed for delivery)",
    },
    "unknown_command": {
        "lv": "Atvainojiet, es nesaprotu. Izmantojiet /help, lai redzētu pieejamās komandas.",
        "ru": "Извините, не понял. Используйте /help для списка команд.",
        "en": "Sorry, I didn't understand. Use /help to see available commands.",
    },
    "error_generic": {
        "lv": "Kļūda. Lūdzu, mēģiniet vēlreiz vai sazinieties ar mums.",
        "ru": "Произошла ошибка. Попробуйте ещё раз или свяжитесь с нами.",
        "en": "An error occurred. Please try again or contact us.",
    },
    "help": {
        "lv": (
            "Pieejamās komandas:\n"
            "/catalog — skatīt katalogu\n"
            "/cart — skatīt grozu\n"
            "/order — izveidot pasūtījumu\n"
            "/subscribe — pārvaldīt abonementu\n"
            "/myorders — mani pasūtījumi\n"
            "/lang — mainīt valodu\n"
            "/help — šī palīdzība"
        ),
        "ru": (
            "Доступные команды:\n"
            "/catalog — каталог хлеба\n"
            "/cart — моя корзина\n"
            "/order — создать заказ\n"
            "/subscribe — управление подпиской\n"
            "/myorders — мои заказы\n"
            "/lang — сменить язык\n"
            "/help — эта справка"
        ),
        "en": (
            "Available commands:\n"
            "/catalog — browse catalog\n"
            "/cart — view cart\n"
            "/order — create order\n"
            "/subscribe — manage subscription\n"
            "/myorders — my orders\n"
            "/lang — change language\n"
            "/help — this help"
        ),
    },
    "btn_catalog": {"lv": "Katalogs", "ru": "Каталог", "en": "Catalog"},
    "btn_cart": {"lv": "Grozs", "ru": "Корзина", "en": "Cart"},
    "btn_order": {"lv": "Pasūtīt", "ru": "Заказать", "en": "Order"},
    "btn_subscribe": {"lv": "Abonements", "ru": "Подписка", "en": "Subscribe"},
    "btn_confirm": {"lv": "Apstiprināt", "ru": "Подтвердить", "en": "Confirm"},
    "btn_cancel": {"lv": "Atcelt", "ru": "Отмена", "en": "Cancel"},
    "btn_yes": {"lv": "Jā", "ru": "Да", "en": "Yes"},
    "btn_no": {"lv": "Nē", "ru": "Нет", "en": "No"},
    "btn_pickup": {"lv": "Pašizņemšana", "ru": "Самовывоз", "en": "Self-pickup"},
    "btn_omniva": {"lv": "Omniva", "ru": "Omniva", "en": "Omniva"},
    "btn_courier": {"lv": "Kurjers", "ru": "Курьер", "en": "Courier"},
    "btn_pause_sub": {"lv": "Apturēt", "ru": "Приостановить", "en": "Pause"},
    "btn_cancel_sub": {"lv": "Atcelt abonementu", "ru": "Отменить подписку", "en": "Cancel subscription"},
    "btn_change_bread": {"lv": "Mainīt maizi", "ru": "Изменить хлеб", "en": "Change bread"},
    "charge_reminder": {
        "lv": "Atgādinājums: rīt tiks iekasēti {amount} € par jūsu abonementu.",
        "ru": "Напоминание: завтра будет списано {amount} € за вашу подписку.",
        "en": "Reminder: {amount} € will be charged tomorrow for your subscription.",
    },
    "subscription_charge_ok": {
        "lv": "Abonements atjaunots. Nākamā piegāde: {date}",
        "ru": "Подписка продлена. Следующая доставка: {date}",
        "en": "Subscription renewed. Next delivery: {date}",
    },
    "subscription_charge_failed": {
        "lv": "Maksājums neizdevās. Lūdzu, atjauniniet maksāšanas metodi.",
        "ru": "Не удалось списать оплату. Пожалуйста, обновите способ оплаты.",
        "en": "Payment failed. Please update your payment method.",
    },
    "discount_applied": {
        "lv": "Abonements atlaide {pct}% piemērota.",
        "ru": "Применена скидка {pct}% за подписку.",
        "en": "Subscription discount {pct}% applied.",
    },
}


def t(key: str, lang: str = "ru", **kwargs: str) -> str:
    """Translate a string key to the given language."""
    lang = lang if lang in ("lv", "ru", "en") else "ru"
    text = STRINGS.get(key, {}).get(lang) or STRINGS.get(key, {}).get("ru") or key
    return text.format(**kwargs) if kwargs else text
