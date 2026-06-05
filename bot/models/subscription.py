from datetime import datetime, date
from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from bot.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(20), default="active")
    # active | paused | cancelled | pending_payment

    # Days of week (ISO: 1=Mon…7=Sun), stored as JSON array, e.g. [1, 4]
    days_of_week: Mapped[list[int]] = mapped_column(JSON, nullable=False)

    # Delivery preferences
    delivery_addr_type: Mapped[str] = mapped_column(String(30), default="pickup")
    delivery_address: Mapped[str | None] = mapped_column(String(500))
    omniva_locker_id: Mapped[str | None] = mapped_column(String(50))

    # Discount
    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=0)

    # Klix recurring token (purchase id from first payment with force_recurring=True)
    klix_recurring_purchase_id: Mapped[str | None] = mapped_column(String(200))

    # Scheduling
    next_delivery_date: Mapped[date | None] = mapped_column(Date)
    next_charge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_until: Mapped[date | None] = mapped_column(Date)

    started_at: Mapped[date] = mapped_column(Date, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="subscriptions")  # noqa: F821
    items: Mapped[list["SubscriptionItem"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan", lazy="selectin"
    )


class SubscriptionItem(Base):
    """One product line in a subscription."""
    __tablename__ = "subscription_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey("subscriptions.id"), nullable=False, index=True)
    erp_product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # ERP standing_order_items.id — set after ERP sync
    erp_standing_order_item_id: Mapped[int | None] = mapped_column(Integer)

    subscription: Mapped["Subscription"] = relationship(back_populates="items")
