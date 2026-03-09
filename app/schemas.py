from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal
from datetime import datetime

class DeliveryItem(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор записи")
    delivery_id: int = Field(..., description="ID поставки")
    product_id: int = Field(..., description="ID товара")
    status: str = Field(default="pending", description="Статус товара")

    model_config = ConfigDict(from_attributes=True)

class Delivery(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор поставки")
    pvz_id: int = Field(..., description="ID пункта выдачи")
    total_price: Decimal = Field(gt=0, decimal_places=2)
    items: list[DeliveryItem] = Field(..., description="Товары в поставке")
    model_config = ConfigDict(from_attributes=True)

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
