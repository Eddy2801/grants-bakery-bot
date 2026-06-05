"""
Local cache of ERP products (synced periodically from ERP DB).
Source of truth is ERP, this is a read-cache for fast bot responses.
"""
from datetime import datetime
from sqlalchemy import String, Numeric, Boolean, Integer, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from bot.database import Base


class BotProduct(Base):
    __tablename__ = "bot_products"

    id: Mapped[int] = mapped_column(primary_key=True)  # same as ERP products.id
    ean: Mapped[str | None] = mapped_column(String(20))
    name_lv: Mapped[str] = mapped_column(String(255))
    name_ru: Mapped[str | None] = mapped_column(String(255))
    name_en: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(10, 3))
    price_without_vat: Mapped[float] = mapped_column(Numeric(10, 4))
    price_with_vat: Mapped[float] = mapped_column(Numeric(10, 4))
    category_id: Mapped[int | None] = mapped_column(Integer)
    # Telegram file_id for fast photo delivery (set manually or via /admin)
    photo_file_id: Mapped[str | None] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
