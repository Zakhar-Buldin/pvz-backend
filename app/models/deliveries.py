from sqlalchemy import  DateTime, ForeignKey, String, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from datetime import date
from decimal import Decimal


class Delivery(Base):
    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    pvz_id: Mapped[int] = mapped_column(ForeignKey("pvz.id"), nullable=False)  # ← unique!
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[date] = mapped_column(nullable=False)

    # Связь с ПВЗ (один к одному)
    pvz: Mapped["PVZ"] = relationship(back_populates="deliveries")

    # Связь с товарами в поставке (один ко многим)
    items: Mapped[list["DeliveryItem"]] = relationship(back_populates="delivery")


class DeliveryItem(Base):
    __tablename__ = "delivery_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20))

    # Связи
    delivery: Mapped["Delivery"] = relationship(back_populates="items")
    operations: Mapped[list["Operation"]] = relationship(back_populates="delivery_item")
    product: Mapped["Product"] = relationship()