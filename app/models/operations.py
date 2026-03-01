from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    delivery_item_id: Mapped[int] = mapped_column(ForeignKey("delivery_items.id"), nullable=False)
    pvz_id: Mapped[int] = mapped_column(ForeignKey("pvz.id"), nullable=False)  # денормализация
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # например 'received', 'issued', 'returned'
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # связи
    delivery_item: Mapped["DeliveryItem"] = relationship(back_populates="operations")
    pvz: Mapped["PVZ"] = relationship(back_populates="operations")