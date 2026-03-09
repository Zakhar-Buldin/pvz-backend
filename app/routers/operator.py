from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db_depends import get_async_db
from app.models.deliveries import DeliveryItem as DeliveryItemModel, Delivery as DeliveryModel
from app.schemas import Delivery as DeliverySchema, DeliveryItem as DeliveryItemSchema
from sqlalchemy.orm import selectinload
from app.models.operations import Operation as OperationModel
from datetime import timedelta, datetime
import random

router = APIRouter(
    prefix="/operator",
    tags=["operator"],
)


# PUT эндпоинт для изменения статуса заказа
@router.put("/status/{delivery_item_id}", response_model=DeliveryItemSchema)
async def update_order_status(
        delivery_item_id: int,
        status: str = Query(..., description="Новый статус товара", pattern=r"^(issued|returned)$"),
        db: AsyncSession = Depends(get_async_db)
):
    """
    Основная функционал оператора: выдача и принятие товара, в случае отказа клиента
    Этот эндпоинт меняет статус заказов (DeliveryItem)
    На вход подается id заказа, с которым собираемся работать, и статус, который оператор хочет присвоить заказу
    """

    # Получаем текущий заказ
    stmt = await db.scalars(
        select(DeliveryItemModel)
        .where(DeliveryItemModel.id == delivery_item_id)
        .options(
            selectinload(DeliveryItemModel.delivery)
        )
    )
    order = stmt.first()

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден"
        )
    if order.status != "received":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Повторная попытка изменить статус заказа"
        )

    # Фиксируем операцию в таблице operations
    operation = OperationModel(
        delivery_item_id=delivery_item_id,
        pvz_id=order.delivery.pvz_id,
        action=status,
    )
    db.add(operation)

    # Обновляем статус напрямую
    await db.execute(
        update(DeliveryItemModel)
        .where(DeliveryItemModel.id == delivery_item_id)
        .values(status=status)  # просто передаём строку
    )
    await db.commit()

    # Обновляем объект для ответа
    await db.refresh(order)
    return order

# PUT эндпоинт для получения оператором всех заказов (изменения их статуса на received)
@router.put("/received_delivery/{delivery_id}", response_model=DeliverySchema)
async def receive_all(delivery_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Эндпоинт для получения оператором доставки (меняют статус всех заказов на received)
    """
    stmt = await db.scalars(
                         select(DeliveryModel)
                  .where(DeliveryModel.id == delivery_id)
                  .options(selectinload(DeliveryModel.items)))

    delivery = stmt.first()

    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Объект доставки еще не сформирован складе, или неверный ID доставки')

    start_time = datetime.now()

    for i, item in enumerate(delivery.items):
        if item.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Повторная попытка изменить статус заказа"
            )
        item_time = start_time + timedelta(seconds=random.randint(30, 120) * i)
        item.status = "received"
        operation = OperationModel(
            delivery_item_id=item.id,
            pvz_id=delivery.pvz_id,
            action="received",
            timestamp=item_time
        )
        db.add(operation)

    await db.commit()

    # 6. Загружаем связанные товары для ответа
    await db.refresh(delivery, attribute_names=["items"])

    return delivery

# GET эндпоинт для получения списка заказов
@router.get("/delivery/{pvz_id}", response_model=list[DeliverySchema])
async def get_orders(pvz_id: int, db: AsyncSession = Depends(get_async_db)):
    """Возвращает список заказов конкретного ПВЗ"""
    delivery = await db.scalars(
        select(DeliveryModel)
        .options(selectinload(DeliveryModel.items))
        .where(DeliveryModel.pvz_id == pvz_id)
    )
    return delivery.all()



