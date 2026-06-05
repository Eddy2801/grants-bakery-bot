"""Formatting helpers for prices, dates, quantities."""
from datetime import date

_DAY_NAMES = {
    "lv": ["", "pirmdiena", "otrdiena", "trešdiena", "ceturtdiena", "piektdiena", "sestdiena", "svētdiena"],
    "ru": ["", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"],
    "en": ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}

_MONTH_NAMES = {
    "lv": ["", "janv.", "febr.", "marts", "apr.", "maijs", "jūn.", "jūl.", "aug.", "sept.", "okt.", "nov.", "dec."],
    "ru": ["", "янв.", "фев.", "мар.", "апр.", "май", "июн.", "июл.", "авг.", "сен.", "окт.", "ноя.", "дек."],
    "en": ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def fmt_price(cents: int) -> str:
    """Format cents to "4.13" string."""
    return f"{cents / 100:.2f}"


def fmt_price_eur(cents: int) -> str:
    return f"€{cents / 100:.2f}"


def eur_to_cents(eur: float) -> int:
    return round(eur * 100)


def cents_to_eur(cents: int) -> float:
    return cents / 100


def fmt_date(d: date, lang: str = "ru") -> str:
    """Format date as 'Monday, 9 Jun' in the given language."""
    dow = d.isoweekday()
    day_name = _DAY_NAMES.get(lang, _DAY_NAMES["ru"])[dow]
    month = _MONTH_NAMES.get(lang, _MONTH_NAMES["ru"])[d.month]
    return f"{day_name.capitalize()}, {d.day} {month}"


def fmt_days_of_week(days: list[int], lang: str = "ru") -> str:
    """Format [1, 4] as 'Monday, Thursday'."""
    names = _DAY_NAMES.get(lang, _DAY_NAMES["ru"])
    return ", ".join(names[d].capitalize() for d in sorted(days) if 1 <= d <= 7)


def fmt_product_name(product: dict, lang: str = "ru") -> str:
    return (
        product.get(f"name_{lang}")
        or product.get("name_ru")
        or product.get("name_lv")
        or product.get("name_en")
        or product.get("product_name", "?")
    )
