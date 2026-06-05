"""
Intent router — fast keyword-based classification before hitting LLM.
Covers ~80% of cases without any LLM call.
"""
import re
from enum import Enum


class Intent(str, Enum):
    GREETING = "greeting"
    CATALOG = "catalog_browse"
    ORDER = "order_create"
    CART = "cart"
    SUBSCRIPTION = "subscription_manage"
    ORDER_STATUS = "order_status"
    LANGUAGE = "language"
    HELP = "help"
    PRODUCT_QUESTION = "product_question"
    OTHER = "other"


_PATTERNS: list[tuple[Intent, list[str]]] = [
    (Intent.GREETING, [
        r"\b(привет|здравствуй|сало|hi|hello|hey|sveiki|labdien|доброе|добрый|добро)\b",
        r"^(привет|hi|hello|hey|sveiki)$",
    ]),
    (Intent.CATALOG, [
        r"\b(каталог|catalog|katalog|ассортимент|хлеб.*есть|что есть|покажи|show|maize|maizi)\b",
        r"\b(что.*печёт|что.*продаёт|какой.*хлеб|виды.*хлеб)\b",
    ]),
    (Intent.ORDER, [
        r"\b(заказ(ать|ываю|ывать)?|order|pasūtīt|хочу.*купить|купить.*хлеб|взять.*хлеб)\b",
        r"\b(хочу.*буханк|возьму.*буханк)\b",
    ]),
    (Intent.CART, [
        r"\b(корзин|cart|grozs|корзина|что.*корзин|мой.*заказ)\b",
    ]),
    (Intent.SUBSCRIPTION, [
        r"\b(подписк|subscribe|abonement|каждую неделю|еженедельно|регулярно|regular)\b",
        r"\b(пауза|отмен.*подписк|pause.*sub|cancel.*sub|изменить.*подписк)\b",
    ]),
    (Intent.ORDER_STATUS, [
        r"\b(статус|status|где.*заказ|когда.*доставк|мой.*заказ)\b",
        r"\b(отследить|tracking|pasūtījums)\b",
    ]),
    (Intent.LANGUAGE, [
        r"^/lang",
        r"\b(язык|language|valoda|сменить язык|change language)\b",
    ]),
    (Intent.HELP, [
        r"^/help",
        r"\b(помощь|помоги|help|palīdzība)\b",
    ]),
    (Intent.PRODUCT_QUESTION, [
        r"\b(состав|ingredient|sastāvs|глютен|gluten|аллерги|allergi|калори|калорийн|kkal)\b",
        r"\b(закваска|sourdough|skābā mīkla|без дрожжей|yeast.free|рецепт|recipe)\b",
        r"\b(чем.*отличается|разница.*между|difference between)\b",
    ]),
]


def classify(text: str) -> Intent:
    """Classify message intent. Returns Intent enum."""
    text_lower = text.lower().strip()
    for intent, patterns in _PATTERNS:
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return intent
    return Intent.OTHER
