"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("first_name", sa.String(100)),
        sa.Column("last_name", sa.String(100)),
        sa.Column("username", sa.String(100)),
        sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(255)),
        sa.Column("lang", sa.String(5), nullable=False, server_default="ru"),
        sa.Column("address", sa.String(500)),
        sa.Column("klix_recurring_purchase_id", sa.String(200)),
        sa.Column("balance_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "bot_products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ean", sa.String(20)),
        sa.Column("name_lv", sa.String(255), nullable=False),
        sa.Column("name_ru", sa.String(255)),
        sa.Column("name_en", sa.String(255)),
        sa.Column("description", sa.Text),
        sa.Column("weight_kg", sa.Numeric(10, 3)),
        sa.Column("price_without_vat", sa.Numeric(10, 4), nullable=False),
        sa.Column("price_with_vat", sa.Numeric(10, 4), nullable=False),
        sa.Column("category_id", sa.Integer),
        sa.Column("photo_file_id", sa.String(300)),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("days_of_week", JSONB, nullable=False),
        sa.Column("delivery_addr_type", sa.String(30), nullable=False, server_default="pickup"),
        sa.Column("delivery_address", sa.String(500)),
        sa.Column("omniva_locker_id", sa.String(50)),
        sa.Column("discount_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("klix_recurring_purchase_id", sa.String(200)),
        sa.Column("next_delivery_date", sa.Date),
        sa.Column("next_charge_at", sa.DateTime(timezone=True)),
        sa.Column("paused_until", sa.Date),
        sa.Column("started_at", sa.Date, nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    op.create_table(
        "subscription_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("subscription_id", sa.Integer, sa.ForeignKey("subscriptions.id"), nullable=False),
        sa.Column("erp_product_id", sa.Integer, nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("erp_standing_order_item_id", sa.Integer),
    )

    op.create_table(
        "bot_orders",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subscription_id", sa.Integer, sa.ForeignKey("subscriptions.id")),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("delivery_date", sa.Date, nullable=False),
        sa.Column("delivery_addr_type", sa.String(30), nullable=False, server_default="pickup"),
        sa.Column("delivery_address", sa.String(500)),
        sa.Column("omniva_locker_id", sa.String(50)),
        sa.Column("recipient_name", sa.String(200)),
        sa.Column("recipient_phone", sa.String(30)),
        sa.Column("subtotal_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("delivery_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("discount_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("klix_purchase_id", sa.String(200)),
        sa.Column("klix_checkout_url", sa.Text),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("erp_synced", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_gift", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("gift_message", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_bot_orders_user_id", "bot_orders", ["user_id"])
    op.create_index("ix_bot_orders_delivery_date", "bot_orders", ["delivery_date"])

    op.create_table(
        "bot_order_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("bot_orders.id"), nullable=False),
        sa.Column("erp_product_id", sa.Integer, nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("unit_price_cents", sa.Integer, nullable=False),
        sa.Column("line_total_cents", sa.Integer, nullable=False),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("bot_orders.id")),
        sa.Column("subscription_id", sa.Integer, sa.ForeignKey("subscriptions.id")),
        sa.Column("klix_purchase_id", sa.String(200), unique=True, nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("type", sa.String(20), nullable=False, server_default="one_time"),
        sa.Column("refunded_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("refund_type", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("intent", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("conversations")
    op.drop_table("payments")
    op.drop_table("bot_order_items")
    op.drop_table("bot_orders")
    op.drop_table("subscription_items")
    op.drop_table("subscriptions")
    op.drop_table("bot_products")
    op.drop_table("users")
