"""
Tool definitions for Claude Haiku + tool execution.
Each tool is defined in Anthropic format and has a corresponding async handler.
"""
import json
import logging
from datetime import date

from bot.services import catalog as catalog_svc
from bot.services import cart as cart_svc
from bot.services import availability as avail_svc
from bot.utils.formatting import fmt_date, fmt_product_name

logger = logging.getLogger(__name__)

# ── Tool definitions (Anthropic format) ──────────────────────

TOOLS = [
    {
        "name": "get_catalog",
        "description": "Get list of all available bread products with names and prices.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lang": {"type": "string", "enum": ["lv", "ru", "en"], "description": "Language for product names"},
            },
        },
    },
    {
        "name": "get_product_detail",
        "description": "Get detailed information about a specific product: description, ingredients, weight.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer", "description": "ERP product id"},
                "lang": {"type": "string", "enum": ["lv", "ru", "en"]},
            },
            "required": ["product_id"],
        },
    },
    {
        "name": "add_to_cart",
        "description": "Add a product to the user's cart.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer"},
                "quantity": {"type": "integer", "minimum": 1},
            },
            "required": ["product_id", "quantity"],
        },
    },
    {
        "name": "view_cart",
        "description": "Show current cart contents and total price.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "clear_cart",
        "description": "Empty the cart.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "check_availability",
        "description": (
            "Check delivery availability for given items and preferred date. "
            "Returns the best available delivery date considering production capacity and freeze window. "
            "Always call this before creating an order."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "preferred_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Preferred delivery date (YYYY-MM-DD), or omit for earliest available",
                },
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer"},
                            "qty": {"type": "integer"},
                        },
                        "required": ["product_id", "qty"],
                    },
                },
            },
        },
    },
    {
        "name": "create_order",
        "description": "Finalize cart as an order and generate payment link.",
        "input_schema": {
            "type": "object",
            "properties": {
                "delivery_date": {"type": "string", "format": "date"},
                "delivery_type": {"type": "string", "enum": ["pickup", "omniva", "courier"]},
                "delivery_address": {"type": "string"},
                "recipient_name": {"type": "string"},
                "recipient_phone": {"type": "string"},
            },
            "required": ["delivery_date", "delivery_type"],
        },
    },
    {
        "name": "create_subscription",
        "description": "Create a recurring weekly bread subscription with automatic payment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer"},
                            "quantity": {"type": "integer"},
                        },
                        "required": ["product_id", "quantity"],
                    },
                },
                "days_of_week": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 1, "maximum": 7},
                    "description": "ISO weekdays: 1=Mon, 2=Tue, ..., 7=Sun",
                },
                "delivery_type": {"type": "string", "enum": ["pickup", "omniva", "courier"]},
                "delivery_address": {"type": "string"},
            },
            "required": ["items", "days_of_week"],
        },
    },
    {
        "name": "manage_subscription",
        "description": "Pause, resume, cancel, or view the user's subscription.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["view", "pause", "resume", "cancel"],
                },
                "paused_until": {
                    "type": "string",
                    "format": "date",
                    "description": "For pause: date to resume (optional)",
                },
            },
            "required": ["action"],
        },
    },
    {
        "name": "get_order_status",
        "description": "Check the status of the user's most recent order or a specific order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer", "description": "Specific order id, or omit for latest"},
            },
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────

class ToolExecutor:
    """Executes tool calls from LLM, bound to a specific user context."""

    def __init__(self, telegram_id: int, user_id: int, lang: str):
        self.telegram_id = telegram_id
        self.user_id = user_id
        self.lang = lang
        # Pending order data (built across multiple tool calls)
        self._pending_order: dict = {}
        self._pending_subscription: dict = {}

    async def execute(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool call and return result as string for LLM."""
        try:
            handler = getattr(self, f"_tool_{tool_name}", None)
            if not handler:
                return f"Error: unknown tool '{tool_name}'"
            return await handler(**tool_input)
        except Exception as e:
            logger.exception("Tool %s failed", tool_name)
            return f"Error executing {tool_name}: {str(e)}"

    async def _tool_get_catalog(self, lang: str | None = None) -> str:
        lang = lang or self.lang
        products = await catalog_svc.get_all_products(lang)
        if not products:
            return "No products available at the moment."
        lines = []
        for p in products:
            lines.append(
                f"id={p['id']} | {p['display_name']} | €{float(p['price_with_vat']):.2f} | {p.get('weight_kg', 0.5)} kg"
            )
        return "Available products:\n" + "\n".join(lines)

    async def _tool_get_product_detail(self, product_id: int, lang: str | None = None) -> str:
        lang = lang or self.lang
        p = await catalog_svc.get_product(product_id, lang)
        if not p:
            return f"Product {product_id} not found."
        return (
            f"Name: {p['display_name']}\n"
            f"Price: €{float(p['price_with_vat']):.2f} (incl. VAT)\n"
            f"Weight: {p.get('weight_kg', 0.5)} kg\n"
            f"Description: {p.get('description') or 'No description'}"
        )

    async def _tool_add_to_cart(self, product_id: int, quantity: int) -> str:
        cart = await cart_svc.add_to_cart(self.telegram_id, product_id, quantity, self.lang)
        total = sum(v["price_cents"] * v["qty"] for v in cart.values())
        name = cart[str(product_id)]["display_name"]
        return f"Added {name} × {quantity} to cart. Cart total: €{total/100:.2f}"

    async def _tool_view_cart(self) -> str:
        summary = await cart_svc.get_cart_summary(self.telegram_id, self.lang)
        if summary["is_empty"]:
            return "Cart is empty."
        lines = [f"• {i['display_name']} × {i['qty']} — €{i['line_total_cents']/100:.2f}" for i in summary["items"]]
        lines.append(f"Total: €{summary['subtotal_cents']/100:.2f}")
        return "\n".join(lines)

    async def _tool_clear_cart(self) -> str:
        await cart_svc.clear(self.telegram_id)
        return "Cart cleared."

    async def _tool_check_availability(
        self, items: list[dict] | None = None, preferred_date: str | None = None
    ) -> str:
        if items is None:
            # Use cart contents
            summary = await cart_svc.get_cart_summary(self.telegram_id, self.lang)
            items = [{"product_id": i["product_id"], "qty": i["qty"]} for i in summary["items"]]

        pref = date.fromisoformat(preferred_date) if preferred_date else None
        result = await avail_svc.find_available_date(items, pref)

        d = result["date"]
        if result["is_frozen"]:
            note = "Production is already running — order accepted regardless."
        elif result["reason"] == "capacity_moved":
            note = f"Preferred date was at capacity. Suggesting {fmt_date(d, self.lang)} instead."
        else:
            note = "Date available."

        return f"Best delivery date: {d.isoformat()} ({fmt_date(d, self.lang)})\n{note}"

    async def _tool_create_order(
        self,
        delivery_date: str,
        delivery_type: str = "pickup",
        delivery_address: str | None = None,
        recipient_name: str | None = None,
        recipient_phone: str | None = None,
    ) -> str:
        # Store in pending — actual order creation happens in handler after user confirms
        self._pending_order = {
            "delivery_date": delivery_date,
            "delivery_type": delivery_type,
            "delivery_address": delivery_address,
            "recipient_name": recipient_name,
            "recipient_phone": recipient_phone,
        }
        summary = await cart_svc.get_cart_summary(self.telegram_id, self.lang)
        if summary["is_empty"]:
            return "Cart is empty — please add products first."
        return (
            f"Order ready to confirm:\n"
            f"{await self._tool_view_cart()}\n"
            f"Delivery: {delivery_type} on {delivery_date}\n"
            f"Address: {delivery_address or 'self-pickup'}\n"
            f"[Waiting for user confirmation]"
        )

    async def _tool_create_subscription(
        self,
        items: list[dict],
        days_of_week: list[int],
        delivery_type: str = "pickup",
        delivery_address: str | None = None,
    ) -> str:
        self._pending_subscription = {
            "items": items,
            "days_of_week": days_of_week,
            "delivery_type": delivery_type,
            "delivery_address": delivery_address,
        }
        from bot.utils.formatting import fmt_days_of_week
        days_str = fmt_days_of_week(days_of_week, self.lang)
        total_per_week = sum(i.get("quantity", 1) for i in items)
        return (
            f"Subscription ready to confirm:\n"
            f"Items: {json.dumps(items)}\n"
            f"Days: {days_str}\n"
            f"Delivery: {delivery_type}\n"
            f"[Waiting for user confirmation]"
        )

    async def _tool_manage_subscription(
        self, action: str, paused_until: str | None = None
    ) -> str:
        from bot.services.subscription import get_active_subscription, pause_subscription, resume_subscription, cancel_subscription
        sub = await get_active_subscription(self.user_id)
        if not sub:
            return "No active subscription found."
        if action == "view":
            from bot.utils.formatting import fmt_days_of_week, fmt_date
            days = fmt_days_of_week(sub.days_of_week, self.lang)
            return (
                f"Subscription #{sub.id} — status: {sub.status}\n"
                f"Delivery days: {days}\n"
                f"Next delivery: {sub.next_delivery_date}"
            )
        if action == "pause":
            until = date.fromisoformat(paused_until) if paused_until else None
            await pause_subscription(sub.id, until)
            return "Subscription paused."
        if action == "resume":
            await resume_subscription(sub.id)
            return "Subscription resumed."
        if action == "cancel":
            await cancel_subscription(sub.id)
            return "Subscription cancelled."
        return f"Unknown action: {action}"

    async def _tool_get_order_status(self, order_id: int | None = None) -> str:
        from bot.services.order import get_order, get_user_orders
        if order_id:
            order = await get_order(order_id)
            if not order or order.user_id != self.user_id:
                return "Order not found."
        else:
            orders = await get_user_orders(self.user_id, limit=1)
            order = orders[0] if orders else None
            if not order:
                return "No orders found."
        return (
            f"Order #{order.id}\n"
            f"Status: {order.status}\n"
            f"Delivery: {order.delivery_date}\n"
            f"Total: €{order.total_cents/100:.2f}"
        )


def to_openai_tools(tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool format to OpenAI function calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]
