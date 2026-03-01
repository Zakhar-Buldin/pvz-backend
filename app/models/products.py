from sqlalchemy import String,Numeric
from sqlalchemy.orm import Mapped, mapped_column
from decimal import Decimal
from app.database import Base

class Product(Base):
    # БД, в которой хранятся товары
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))  # название товара
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

