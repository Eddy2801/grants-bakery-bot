"""
Language detection from first message text.
Falls back to 'ru' on any error.
"""
import logging
import re

logger = logging.getLogger(__name__)

# Cyrillic range (Russian)
_RE_CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")
# Latvian-specific characters (ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž)
_RE_LATVIAN = re.compile(r"[āčēģīķļņšūžĀČĒĢĪĶĻŅŠŪŽ]")


def detect_lang(text: str) -> str:
    """
    Detect language from text:
    - Latvian special characters → 'lv'
    - Cyrillic → 'ru'
    - Otherwise → 'en'
    """
    if not text:
        return "ru"
    text_lower = text.lower()
    if _RE_LATVIAN.search(text_lower):
        return "lv"
    if _RE_CYRILLIC.search(text):
        return "ru"
    # Try langdetect as fallback for longer texts
    if len(text) > 10:
        try:
            from langdetect import detect, LangDetectException
            detected = detect(text)
            if detected == "lv":
                return "lv"
            if detected in ("ru", "be", "uk", "bg"):
                return "ru"
            if detected == "en":
                return "en"
        except Exception:
            pass
    return "en"


LANG_LABELS = {
    "lv": "🇱🇻 Latviešu",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
}
