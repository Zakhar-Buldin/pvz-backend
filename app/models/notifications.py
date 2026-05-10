from datetime import date
from sqlalchemy import ForeignKey
from sqlalchemy.orm import mapped_column, Mapped
from app.database import Base

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    pvz_id: Mapped[int] = mapped_column(ForeignKey("pvz.id"), nullable=False)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    type_problem: Mapped[int] = mapped_column(nullable=False)
    priority: Mapped[int] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default="pending", nullable=False)
    problem_solution: Mapped[str | None] = mapped_column(nullable=True)
    solution_date: Mapped[date | None] = mapped_column(nullable=True)
    timestamp: Mapped[date] = mapped_column(nullable=False)
