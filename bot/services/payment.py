"""Payment service — wraps KlixClient with bot-specific logic."""
import logging
from typing import Optional

from bot.config import config
from bot.utils.formatting import fmt_price

logger = logging.getLogger(__name__)

_klix: Optional[object] = None


def get_klix():
    global _klix
    if _klix is None:
        from payment.klix_client import KlixClient
        _klix = KlixClient(
            brand_id=config.KLIX_BRAND_ID,
            secret_key=config.KLIX_SECRET_KEY,
            base_url=config.KLIX_BASE_URL,
        )
    return _klix


async def create_order_payment(
    order_id: int,
    total_cents: int,
    client_email: str,
    description: str,
) -> dict:
    """Create one-time payment checkout. Returns {checkout_url, purchase_id}."""
    klix = get_klix()
    result = await klix.create_payment(
        order_id=f"order_{order_id}",
        amount_cents=total_cents,
        description=description,
        client_email=client_email,
        success_redirect=config.KLIX_SUCCESS_REDIRECT,
        failure_redirect=config.KLIX_FAILURE_REDIRECT,
        webhook_url=config.KLIX_WEBHOOK_URL,
        force_recurring=False,
    )
    return result


async def create_subscription_payment(
    sub_id: int,
    total_cents: int,
    client_email: str,
    description: str,
) -> dict:
    """
    Create first subscription payment with force_recurring=True.
    Saves card token for future automatic charges.
    Returns {checkout_url, purchase_id}
    """
    klix = get_klix()
    result = await klix.create_payment(
        order_id=f"sub_{sub_id}_first",
        amount_cents=total_cents,
        description=description,
        client_email=client_email,
        success_redirect=config.KLIX_SUCCESS_REDIRECT,
        failure_redirect=config.KLIX_FAILURE_REDIRECT,
        webhook_url=config.KLIX_WEBHOOK_URL,
        force_recurring=True,
    )
    return result


async def charge_recurring(
    recurring_purchase_id: str,
    sub_id: int,
    total_cents: int,
    client_email: str,
    description: str,
) -> dict:
    """Auto-charge from saved card. Returns {id, status}."""
    klix = get_klix()
    return await klix.charge_recurring(
        recurring_purchase_id=recurring_purchase_id,
        order_id=f"sub_{sub_id}_recurring",
        amount_cents=total_cents,
        description=description,
        client_email=client_email,
    )


async def refund_payment(purchase_id: str, amount_cents: int | None = None) -> dict:
    """Full or partial refund."""
    klix = get_klix()
    return await klix.refund(purchase_id, amount_cents)


async def delete_card_token(recurring_purchase_id: str) -> bool:
    """Delete saved card when subscription is cancelled."""
    klix = get_klix()
    return await klix.delete_recurring_token(recurring_purchase_id)


def parse_webhook(payload: dict) -> dict:
    klix = get_klix()
    return klix.parse_webhook(payload)
