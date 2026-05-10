from pydantic import BaseModel, Field, ConfigDict, EmailStr
from decimal import Decimal
from datetime import datetime, date
from typing import Optional, Annotated
from fastapi import Form



class PVZ(BaseModel):
    id: int = Field(..., description="ID ПВЗ")
    address: str = Field(..., description="Адрес ПВЗ")
    work_start: str = Field(..., description="Время начала рабочего дня")
    work_end: str = Field(..., description="Время конца рабочего дня")
    model_config = ConfigDict(from_attributes=True)

class Delivery(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор поставки")
    pvz_id: int = Field(..., description="ID пункта выдачи")
    total_price: Decimal = Field(gt=0, decimal_places=2)
    created_at: date
    pvz: Optional[PVZ] = None
    model_config = ConfigDict(from_attributes=True)

class DeliveryItem(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор записи")
    delivery_id: int = Field(..., description="ID поставки")
    product_id: int = Field(..., description="ID товара")
    status: str = Field(default="pending", description="Статус товара")
    delivery: Delivery = Field(..., description="Доставка, в которой находится заказ")

class Operation(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор операции")
    delivery_item_id: int = Field(..., description="ID заказа")
    pvz_id: int = Field(..., description="ID пункта выдачи")
    action: str = Field(..., description="Название операции")
    timestamp: datetime = Field(..., description="Дата создания отзыва")
    model_config = ConfigDict(from_attributes=True)

class HourlyLoad(BaseModel):
    hour: int = Field(..., description="Час")               # 0-23
    operations: int = Field(..., description="Количество операций за конкретный час")
    overload: bool = Field(..., description="Наличие перегрузки")

class DailyLoadReport(BaseModel):
    pvz_id: int = Field(..., description="ID пункта выдачи")
    date: str = Field(..., description="Дата")
    capacity_per_hour: int = Field(..., description="Пропускная способность ПВЗ")
    hourly: list[HourlyLoad] = Field(..., description="Массив объектов почасовой нагрузки")
    total_operations: int = Field(..., description="Количество операций за весь день")
    overload_hours: int = Field(..., description="Количество перегрузок в день")

class WeeklyLoadReport(BaseModel):
    pvz_id: int = Field(..., description="ID пункта выдачи")
    start_date: str = Field(..., description="Дата начала недели")
    daily: list[DailyLoadReport] = Field(..., description="Массив дневных отчётов за неделю")
    total_overload_hours: int = Field(..., description="Общее количество перегрузок за неделю")

class Redirection(BaseModel):
    id: int = Field(..., description="ID перенаправления")
    delivery_item_id: int = Field(..., description="ID заказа")
    old_delivery_id: int = Field(..., description="ID старой доставки")
    new_delivery_id: int = Field(..., description="ID новой доставки")
    timestamp: datetime = Field(..., description="Время операции перенаправления")
    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50, description="Имя пользователя")
    email: EmailStr = Field(..., description="Email пользователя")
    password: str = Field(..., min_length=8, description="Пароль (минимум 8 символов)")
    role: str = Field(..., pattern="^(operator|supervisor|tester|analyst)$", description="Роли: operator, supervisor, tester или analyst")
    @classmethod
    def as_form(cls,
                  name: Annotated[str, Form(...)],
                  email: Annotated[EmailStr, Form(...)],
                  password: Annotated[str, Form(...)],
                  role: Annotated[str, Form(...)]
    ) -> "UserCreate":
        return cls(
            name=name,
            email=email,
            password=password,
            role=role
        )

class User(BaseModel):
    id: int = Field(..., description="ID пользователя")
    name: str = Field(..., description="Имя пользователя")
    email: EmailStr = Field(description="Email пользователя")
    role: str = Field(..., description="Роли: operator, supervisor, tester или analyst")
    pvz: PVZ | None = Field(description="ПВЗ оператора")
    image_url: str = Field(..., description="Фотография профиля")
    model_config = ConfigDict(from_attributes=True)

class NotificationCreate(BaseModel):
    """
    Типы проблем:
        1 - техническая проблема
        2 - проблема с заказом
        3 - конфликт с клиентом
        4 - неисправность оборудования
        5 - Другое
    """
    type_problem: int = Field(..., ge=1, le=5, description="Тип проблемы")
    priority: int = Field(..., ge=1, le=3, description="Приоритет проблемы")
    message: str = Field(..., min_length=3, max_length=1000, description="Описание проблемы")

class Notification(BaseModel):
    id: int = Field(..., description="ID уведомления")
    pvz_id: int = Field(..., description="ID ПВЗ")
    operator_id: int = Field(..., description="ID оператора")
    type_problem: int = Field(..., description="Тип проблемы")
    priority: int = Field(..., description="Приоритет проблемы")
    message: str = Field(..., min_length=3, max_length=1000, description="Описание проблемы")
    status: str = Field(..., pattern="^(pending|completed)")
    problem_solution: str | None = Field(description="Описание решения проблемы")
    solution_date: date | None = Field(description="Дата решения проблемы")
    timestamp: date = Field(..., description="Дата отправки уведомления")
    model_config = ConfigDict(from_attributes=True)


class NotificationUpdate(BaseModel):
    problem_solution: str = Field(..., min_length=3, max_length=1000, description="Описание решения проблемы")
