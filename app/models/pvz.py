from sqlalchemy import Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class PVZ(Base):
    __tablename__ = "pvz"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    address: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity_per_hour: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)

    work_start: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    work_end: Mapped[str] = mapped_column(String(5), nullable=False, default="21:00")
    deliveries: Mapped[list["Delivery"]] = relationship(
        "Delivery",
        back_populates="pvz"
    )
    operations: Mapped[list["Operation"]] = relationship(back_populates="pvz")
