from datetime import datetime, date
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from bot.database import Base


class Order(Base):
    __tablename__ = "bot_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id"), index=True)

    status: Mapped[str] = mapped_column(String(30), default="pending")
    # pending → awaiting_payment → paid → confirmed → packed → delivered → cancelled

    delivery_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    delivery_addr_type: Mapped[str] = mapped_column(String(30), default="pickup")
    # pickup | omniva | courier
    delivery_address: Mapped[str | None] = mapped_column(String(500))
    omniva_locker_id: Mapped[str | None] = mapped_column(String(50))
    recipient_name: Mapped[str | None] = mapped_column(String(200))
    recipient_phone: Mapped[str | None] = mapped_column(String(30))

    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0)
    delivery_cents: Mapped[int] = mapped_column(Integer, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)

    klix_purchase_id: Mapped[str | None] = mapped_column(String(200))
    klix_checkout_url: Mapped[str | None] = mapped_column(Text)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Is this order already reflected in ERP daily_delivery_plan?
    erp_synced: Mapped[bool] = mapped_column(Boolean, default=False)

    # Gift order
    is_gift: Mapped[bool] = mapped_column(Boolean, default=False)
    gift_message: Mapped[str | None] = mapped_column(Text)

    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="orders")  # noqa: F821
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan", lazy="selectin")


class OrderItem(Base):
    __tablename__ = "bot_order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("bot_orders.id"), nullable=False, index=True)
    erp_product_id: Mapped[int] = mapped_column(Integer, nullable=False)  # ERP products.id
    product_name: Mapped[str] = mapped_column(String(255))  # snapshot at order time
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # price_with_vat in cents
    line_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
