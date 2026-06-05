"""
Availability service — implements the smart date-selection logic.

Rule (from spec):
  For each candidate date (starting from tomorrow):
    1. If date is FROZEN → production is locked → ANYTHING GOES (accept)
    2. If not frozen → check capacity:
       new_qty_total ≤ FREEZE_CAPACITY_PCT% of existing plan total for that date
       If fits → suggest this date
       If doesn't fit → try next date
  Returns (suggested_date, is_frozen, reason)
"""
import logging
from datetime import date, datetime, timedelta, timezone, time

from bot.config import config
from bot.erp_db import erp_get_available_dates, erp_get_plan_total, erp_is_date_frozen

logger = logging.getLogger(__name__)


async def find_available_date(
    items: list[dict],
    preferred_date: date | None = None,
    days_ahead: int = 14,
) -> dict:
    """
    Find the best delivery date for the given items.

    Args:
        items: list of {product_id, qty}
        preferred_date: client's preference (may be adjusted)
        days_ahead: how far ahead to look

    Returns:
        {
            date: date,
            is_frozen: bool,
            reason: "ok" | "preferred" | "capacity_moved" | "frozen_ok",
            original_preferred: date | None
        }
    """
    new_qty = sum(i.get("qty", 1) for i in items)
    available_dates = await erp_get_available_dates(days_ahead)

    if not available_dates:
        # No production scheduled — fallback to tomorrow
        return {
            "date": date.today() + timedelta(days=1),
            "is_frozen": False,
            "reason": "no_schedule",
            "original_preferred": preferred_date,
        }

    # If preferred_date is given, start from it; otherwise start from tomorrow
    start_date = preferred_date or (date.today() + timedelta(days=1))
    candidates = [d for d in available_dates if d >= start_date]
    if not candidates:
        candidates = available_dates  # wrap around

    for d in candidates:
        frozen = await erp_is_date_frozen(d)
        if frozen:
            # Production locked — can accept anything
            reason = "frozen_ok" if (preferred_date and d != preferred_date) else "preferred"
            return {
                "date": d,
                "is_frozen": True,
                "reason": reason,
                "original_preferred": preferred_date,
            }

        # Not frozen — check capacity
        plan = await erp_get_plan_total(d)
        existing_total = sum(plan.values())

        if existing_total == 0:
            # No orders yet for this date — always accept
            reason = "ok" if d == start_date else "capacity_moved"
            return {
                "date": d,
                "is_frozen": False,
                "reason": reason,
                "original_preferred": preferred_date,
            }

        # Check 25% rule
        capacity_limit = existing_total * (config.FREEZE_CAPACITY_PCT / 100)
        if new_qty <= capacity_limit:
            reason = "ok" if d == start_date else "capacity_moved"
            return {
                "date": d,
                "is_frozen": False,
                "reason": reason,
                "original_preferred": preferred_date,
            }

        # Date is too full → try next
        logger.debug(
            "Date %s at capacity: existing=%d, new=%d, limit=%.1f → trying next",
            d, existing_total, new_qty, capacity_limit
        )

    # All non-frozen dates are full → return last available (frozen zone)
    last = candidates[-1]
    return {
        "date": last,
        "is_frozen": await erp_is_date_frozen(last),
        "reason": "last_resort",
        "original_preferred": preferred_date,
    }


async def get_available_dates_for_display(days_ahead: int = 14) -> list[dict]:
    """
    Return list of {date, is_frozen, day_name_short} for showing to user.
    Filters out dates that are too full (non-frozen, capacity exceeded for typical order).
    """
    dates = await erp_get_available_dates(days_ahead)
    result = []
    for d in dates:
        frozen = await erp_is_date_frozen(d)
        result.append({"date": d, "is_frozen": frozen})
    return result
