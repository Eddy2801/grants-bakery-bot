from datetime import datetime
from sqlalchemy import BigInteger, String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from bot.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    username: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    lang: Mapped[str] = mapped_column(String(5), default="ru")
    address: Mapped[str | None] = mapped_column(String(500))
    # Klix: id of first recurring purchase (used for future charges)
    klix_recurring_purchase_id: Mapped[str | None] = mapped_column(String(200))
    balance_cents: Mapped[int] = mapped_column(default=0)  # credit balance in cents
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    orders: Mapped[list["Order"]] = relationship(back_populates="user", lazy="selectin")  # noqa: F821
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user", lazy="selectin")  # noqa: F821
