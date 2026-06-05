import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class KlixAPIError(Exception):
    """Custom exception for Klix API errors."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Klix API Error {status_code}: {message}")


class KlixClient:
    """Async HTTP client for Klix Payment API."""

    def __init__(
        self,
        brand_id: str,
        secret_key: str,
        base_url: str = "https://portal.klix.app/api/v1/",
    ):
        self.brand_id = brand_id
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/") + "/"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Authorization": f"Bearer {self.secret_key}"},
                base_url=self.base_url,
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        json: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        client = await self._get_client()
        logger.info("Klix API request: %s %s", method, path)
        try:
            response = await client.request(method, path, json=json)
        except httpx.RequestError as e:
            logger.error("Klix API request failed: %s", e)
            raise KlixAPIError(0, str(e)) from e

        logger.info(
            "Klix API response: %s %s -> %d",
            method,
            path,
            response.status_code,
        )
        if response.is_error:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("detail", error_msg)
            except Exception:
                pass
            raise KlixAPIError(response.status_code, error_msg)

        return response.json() if response.text else {}

    async def create_payment(
        self,
        order_id: str,
        amount_cents: int,
        description: str,
        client_email: str,
        success_redirect: str,
        failure_redirect: str,
        webhook_url: str,
        force_recurring: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a payment/checkout session.
        Returns dict with keys: id, checkout_url, status.
        """
        payload = {
            "brand_id": self.brand_id,
            "reference": order_id,
            "force_recurring": force_recurring,
            "success_callback": webhook_url,
            "success_redirect": success_redirect,
            "failure_redirect": failure_redirect,
            "cancel_redirect": failure_redirect,  # same as failure per task example
            "purchase": {
                "currency": "EUR",
                "products": [
                    {
                        "name": description,
                        "price": amount_cents,
                        "quantity": 1,
                    }
                ],
            },
            "client": {
                "email": client_email,
            },
        }
        result = await self._request("POST", "purchases/", json=payload)
        return {
            "id": result.get("id"),
            "checkout_url": result.get("checkout_url"),
            "status": result.get("status"),
        }

    async def charge_recurring(
        self,
        recurring_purchase_id: str,
        order_id: str,
        amount_cents: int,
        description: str,
        client_email: str,
    ) -> Dict[str, Any]:
        """
        Charge from a saved card token (previously created with force_recurring).
        Returns dict with keys: id, status.
        """
        payload = {
            "brand_id": self.brand_id,
            "reference": order_id,
            "purchase": {
                "currency": "EUR",
                "products": [
                    {
                        "name": description,
                        "price": amount_cents,
                        "quantity": 1,
                    }
                ],
            },
            "client": {
                "email": client_email,
            },
        }
        result = await self._request(
            "POST", f"purchases/{recurring_purchase_id}/charge/", json=payload
        )
        return {
            "id": result.get("id"),
            "status": result.get("status"),
        }

    async def get_purchase(self, purchase_id: str) -> Dict[str, Any]:
        """Get status and details of a purchase."""
        return await self._request("GET", f"purchases/{purchase_id}/")

    async def cancel_purchase(self, purchase_id: str) -> bool:
        """Cancel a pending purchase."""
        try:
            await self._request("POST", f"purchases/{purchase_id}/cancel/")
            return True
        except KlixAPIError:
            raise

    async def refund(
        self, purchase_id: str, amount_cents: Optional[int] = None
    ) -> Dict[str, Any]:
        """Refund a purchase (full or partial)."""
        payload = {}
        if amount_cents is not None:
            payload["amount"] = amount_cents
        return await self._request(
            "POST", f"purchases/{purchase_id}/refund/", json=payload
        )

    async def delete_recurring_token(self, purchase_id: str) -> bool:
        """Delete saved card token for the recurring purchase."""
        try:
            await self._request(
                "POST", f"purchases/{purchase_id}/delete_recurring_token/"
            )
            return True
        except KlixAPIError:
            raise

    def parse_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Klix webhook payload and return normalized dict:
        {purchase_id, reference, status, amount_cents, currency}.
        """
        purchase_data = payload.get("purchase", {})
        return {
            "purchase_id": payload.get("id"),
            "reference": payload.get("reference"),
            "status": payload["status"],
            "amount_cents": int(purchase_data.get("total", 0)),
            "currency": purchase_data.get("currency", "EUR"),
        }

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
