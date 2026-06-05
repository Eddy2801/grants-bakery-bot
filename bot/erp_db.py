"""
Direct psycopg2 connection to the ERP PostgreSQL database.
Used for reading products/prices and writing to production plan.
All methods are wrapped in asyncio.to_thread for non-blocking execution.
"""
import asyncio
import logging
from contextlib import contextmanager
from datetime import date
from typing import Optional

import psycopg2
import psycopg2.extras

from bot.config import config

logger = logging.getLogger(__name__)


def _connect():
    return psycopg2.connect(
        host=config.ERP_DB_HOST,
        port=config.ERP_DB_PORT,
        dbname=config.ERP_DB_NAME,
        user=config.ERP_DB_USER,
        password=config.ERP_DB_PASS,
    )


@contextmanager
def _erp_cursor():
    conn = _connect()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur, conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Sync helpers (run via asyncio.to_thread) ──────────────────

def _get_products_sync() -> list[dict]:
    with _erp_cursor() as (cur, _):
        cur.execute("""
            SELECT id, ean, name_lv, name_ru, name_en, description,
                   weight_kg, unit,
                   price_without_vat, price_with_vat,
                   active, category_id
            FROM products
            WHERE active = true
            ORDER BY id
        """)
        return [dict(r) for r in cur.fetchall()]


def _get_product_sync(product_id: int) -> Optional[dict]:
    with _erp_cursor() as (cur, _):
        cur.execute("""
            SELECT id, ean, name_lv, name_ru, name_en, description,
                   weight_kg, unit, price_without_vat, price_with_vat, active
            FROM products WHERE id = %s
        """, (product_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def _get_available_delivery_dates_sync(days_ahead: int = 14) -> list[date]:
    """Return dates with active production (via production_day_schedule)."""
    with _erp_cursor() as (cur, _):
        cur.execute("""
            SELECT DISTINCT (CURRENT_DATE + o)::date AS delivery_date
            FROM production_day_schedule, UNNEST(delivery_offsets) AS o
            WHERE (CURRENT_DATE + o)::date > CURRENT_DATE
              AND (CURRENT_DATE + o)::date <= CURRENT_DATE + %s
            ORDER BY 1
        """, (days_ahead,))
        return [r["delivery_date"] for r in cur.fetchall()]


def _get_plan_total_sync(delivery_date: date) -> dict:
    """Return {product_id: quantity} for a given date (all sources)."""
    with _erp_cursor() as (cur, _):
        cur.execute("""
            SELECT product_id, SUM(quantity) AS qty
            FROM daily_delivery_plan
            WHERE delivery_date = %s AND quantity > 0
            GROUP BY product_id
        """, (delivery_date,))
        return {r["product_id"]: r["qty"] for r in cur.fetchall()}


def _is_date_frozen_sync(delivery_date: date) -> bool:
    """Check if production for this delivery date is past freeze window."""
    from datetime import datetime, timezone, timedelta
    with _erp_cursor() as (cur, _):
        # Check plan_deadlines override first
        cur.execute(
            "SELECT testo_deadline FROM plan_deadlines WHERE delivery_date = %s",
            (delivery_date,)
        )
        row = cur.fetchone()
        if row and row["testo_deadline"]:
            return datetime.now(tz=timezone.utc) > row["testo_deadline"]

        # Find production date via production_day_schedule
        cur.execute("""
            SELECT (%s::date - o)::date AS prod_date
            FROM production_day_schedule, UNNEST(delivery_offsets) AS o
            WHERE EXTRACT(ISODOW FROM (%s::date - o)::date)::smallint = day_of_week
            LIMIT 1
        """, (delivery_date, delivery_date))
        row = cur.fetchone()
        if not row:
            return False  # No production covers this date

        prod_date = row["prod_date"]
        freeze_day = prod_date - timedelta(days=1)
        freeze_dt = datetime(
            freeze_day.year, freeze_day.month, freeze_day.day,
            17, 0, tzinfo=timezone.utc
        )
        return datetime.now(tz=timezone.utc) > freeze_dt


def _aggregate_bot_orders_sync(delivery_date: date, addr_id: int, client_id: int):
    """
    Re-aggregate all paid bot orders for a delivery_date into daily_delivery_plan.
    Deletes existing bot rows for the date+address, then inserts fresh aggregate.
    """
    with _erp_cursor() as (cur, conn):
        cur.execute("""
            DELETE FROM daily_delivery_plan
            WHERE delivery_date = %s
              AND client_address_id = %s
              AND source = 'bot'
        """, (delivery_date, addr_id))

        cur.execute("""
            INSERT INTO daily_delivery_plan
                (delivery_date, client_id, client_address_id, product_id, quantity, source, updated_at)
            SELECT
                %s,
                %s,
                %s,
                oi.erp_product_id,
                SUM(oi.quantity),
                'bot',
                NOW()
            FROM bot_order_items oi
            JOIN bot_orders o ON o.id = oi.order_id
            WHERE o.delivery_date = %s
              AND o.status IN ('paid', 'confirmed', 'processing')
              AND o.delivery_addr_type = (
                  SELECT label FROM client_addresses WHERE id = %s LIMIT 1
              )
              AND oi.erp_product_id IS NOT NULL
            GROUP BY oi.erp_product_id
            HAVING SUM(oi.quantity) > 0
        """, (delivery_date, client_id, addr_id, delivery_date, addr_id))


def _upsert_standing_order_sync(
    client_id: int, client_address_id: int,
    product_id: int, day_of_week: int, quantity: int
) -> int:
    """Create or update a standing_order_item. Returns its id."""
    with _erp_cursor() as (cur, _):
        cur.execute("""
            INSERT INTO standing_order_items
                (client_id, client_address_id, product_id, day_of_week, base_quantity, active)
            VALUES (%s, %s, %s, %s, %s, true)
            ON CONFLICT (client_id, client_address_id, product_id, day_of_week)
            DO UPDATE SET base_quantity = EXCLUDED.base_quantity, active = true, updated_at = NOW()
            RETURNING id
        """, (client_id, client_address_id, product_id, day_of_week, quantity))
        return cur.fetchone()["id"]


def _deactivate_standing_order_sync(standing_order_item_id: int):
    with _erp_cursor() as (cur, _):
        cur.execute(
            "UPDATE standing_order_items SET active = false, updated_at = NOW() WHERE id = %s",
            (standing_order_item_id,)
        )


def _seed_delivery_plan_sync(from_date: date, to_date: date):
    with _erp_cursor() as (cur, _):
        cur.execute("SELECT * FROM seed_delivery_plan(%s::date, %s::date)", (from_date, to_date))
        cur.fetchall()


# ── Async wrappers ────────────────────────────────────────────

async def erp_get_products() -> list[dict]:
    return await asyncio.to_thread(_get_products_sync)


async def erp_get_product(product_id: int) -> Optional[dict]:
    return await asyncio.to_thread(_get_product_sync, product_id)


async def erp_get_available_dates(days_ahead: int = 14) -> list[date]:
    return await asyncio.to_thread(_get_available_delivery_dates_sync, days_ahead)


async def erp_get_plan_total(delivery_date: date) -> dict:
    return await asyncio.to_thread(_get_plan_total_sync, delivery_date)


async def erp_is_date_frozen(delivery_date: date) -> bool:
    return await asyncio.to_thread(_is_date_frozen_sync, delivery_date)


async def erp_aggregate_bot_orders(delivery_date: date, addr_id: int, client_id: int):
    await asyncio.to_thread(_aggregate_bot_orders_sync, delivery_date, addr_id, client_id)


async def erp_upsert_standing_order(
    client_id: int, client_address_id: int,
    product_id: int, day_of_week: int, quantity: int
) -> int:
    return await asyncio.to_thread(
        _upsert_standing_order_sync,
        client_id, client_address_id, product_id, day_of_week, quantity
    )


async def erp_deactivate_standing_order(standing_order_item_id: int):
    await asyncio.to_thread(_deactivate_standing_order_sync, standing_order_item_id)


async def erp_seed_plan(from_date: date, to_date: date):
    await asyncio.to_thread(_seed_delivery_plan_sync, from_date, to_date)
