from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    pvz_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pvz.id"), nullable=True)
    pvz: Mapped[Optional["PVZ"]] = relationship("PVZ", back_populates="operators")