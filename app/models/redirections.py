from datetime import date
from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.orm import mapped_column, relationship, Mapped
from app.database import Base

class Redirection(Base):
    __tablename__ = "redirections"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    delivery_item_id: Mapped[int] = mapped_column(ForeignKey("delivery_items.id"))
    old_delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id"))
    new_delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id"))
    timestamp: Mapped[date] = mapped_column(nullable=False)

    delivery_item: Mapped["DeliveryItem"] = relationship()