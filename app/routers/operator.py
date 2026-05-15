from fastapi import APIRouter, HTTPException, status
from fastapi.params import Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db_depends import get_async_db
from app.models.deliveries import DeliveryItem as DeliveryItemModel, Delivery as DeliveryModel
from app.schemas import DeliveryItem as DeliveryItemSchema
from sqlalchemy.orm import selectinload
from app.models.operations import Operation as OperationModel
from datetime import datetime
from app.auth import get_current_operator
from app.models.users import User as UserModel
from app.models.pvz import PVZ as PVZModel
from app.schemas import NotificationCreate, Notification as NotificationSchema
from app.models.notifications import Notification as NotificationModel

router = APIRouter(
    prefix="/operator",
    tags=["operator"],
)

# PUT эндпоинт для изменения статуса заказа
@router.put("/status/{delivery_item_id}", response_model=DeliveryItemSchema)
async def update_order_status(
        delivery_item_id: int,
        change_status: str = Query(...,
                            description="Новый статус товара",
                            pattern=r"^(issued|returned)$"),
        operation_time: str = Query(...,
                                            description="Время в формате HH:MM (к примеру, 14:30)",
                                            pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$"),
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_operator)
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
            detail="Повторная попытка изменить статус заказа, либо заказ ещё не доставлен на ПВЗ"
        )

    pvz_id = order.delivery.pvz_id
    pvz = await db.get(PVZModel, pvz_id)

    if pvz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ПВЗ не найден!"
        )

    if current_user.pvz_id != pvz_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Оператор не может изменить статус заказа, который находится в другом ПВЗ!"
        )
    if operation_time < pvz.work_start or operation_time > pvz.work_end:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Попытка установить некорректное время операции! ПВЗ в это время не работает!")

    delivery_date = order.delivery.created_at
    try:
        target_time = datetime.strptime(operation_time, "%H:%M").time()
        result_datetime = datetime.combine(delivery_date, target_time)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат времени. Ожидается HH:MM (например, 14:30)."
        )

    # Фиксируем операцию в таблице operations

    operation = OperationModel(
        delivery_item_id=delivery_item_id,
        pvz_id=order.delivery.pvz_id,
        action=change_status,
        timestamp=result_datetime

    )
    db.add(operation)

    # Обновляем статус напрямую
    await db.execute(
        update(DeliveryItemModel)
        .where(DeliveryItemModel.id == delivery_item_id)
        .values(status=change_status)  # просто передаём строку
    )
    await db.commit()

    # Обновляем объект для ответа
    result = await db.scalars(
        select(DeliveryItemModel)
        .where(DeliveryItemModel.id == delivery_item_id)
        .options(selectinload(DeliveryItemModel.delivery).selectinload(DeliveryModel.pvz))
    )
    return result.first()

# PUT эндпоинт для получения оператором всех заказов (изменения их статуса на received)
@router.put("/received_delivery_item/{delivery_item_id}", response_model=DeliveryItemSchema)
async def receive_item(delivery_item_id: int,
                      db: AsyncSession = Depends(get_async_db),
                      receiving_time: str = Query(...,
                                                        description="Время в формате HH:MM (к примеру, 14:30)",
                                                        pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$"),
                      current_user: UserModel = Depends(get_current_operator)
    ):
    """
    Эндпоинт принятия доставки со склада
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
    if order.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Повторная попытка изменить статус заказа"
        )

    pvz_id = order.delivery.pvz_id
    pvz = await db.get(PVZModel, pvz_id)

    if pvz is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ПВЗ не найден!"
        )
    if current_user.pvz_id != pvz_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Оператор не может изменить статус заказа, который закреплен за другим ПВЗ!"
        )

    if receiving_time < pvz.work_start or receiving_time > pvz.work_end:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Попытка установить некорректное время операции! ПВЗ в это время не работает!")

    delivery_date = order.delivery.created_at
    try:
        target_time = datetime.strptime(receiving_time, "%H:%M").time()
        result_datetime = datetime.combine(delivery_date, target_time)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат времени. Ожидается HH:MM (например, 14:30)."
        )

    # Фиксируем операцию в таблице operations

    operation = OperationModel(
        delivery_item_id=delivery_item_id,
        pvz_id=order.delivery.pvz_id,
        action="received",
        timestamp=result_datetime

    )
    db.add(operation)

    # Обновляем статус напрямую
    await db.execute(
        update(DeliveryItemModel)
        .where(DeliveryItemModel.id == delivery_item_id)
        .values(status="received")
    )
    await db.commit()

    result = await db.scalars(
        select(DeliveryItemModel)
        .where(DeliveryItemModel.id == delivery_item_id)
        .options(selectinload(DeliveryItemModel.delivery).selectinload(DeliveryModel.pvz))
    )
    return result.first()


# GET эндпоинт для получения списка заказов
@router.get("/delivery_items", response_model=list[DeliveryItemSchema])
async def get_deliveries(
                     created_date: str | None = Query(None,
                                            description="Дата формате YYYY-MM-DD (к примеру, 2024-01-01)",
                                            pattern=r"^\d{4}-\d{2}-\d{2}$"
                                            ),
                     status_order: str | None = Query(None,
                                            description="Фильтрация по статусу заказа",
                                            pattern=r"^(pending|received|issued|returned)$"),
                     db: AsyncSession = Depends(get_async_db),
                     current_user: UserModel = Depends(get_current_operator)):
    """Возвращает список заказов конкретного ПВЗ"""

    if current_user.pvz_id is None:
        raise HTTPException(status_code=403, detail="Оператор не привязан к ПВЗ")
    filters = [DeliveryModel.pvz_id == current_user.pvz_id]

    if created_date:
        try:
            target_date = datetime.strptime(created_date, "%Y-%m-%d").date()
            filters.append(DeliveryModel.created_at == target_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Ожидается YYYY-MM-DD."
            )
    else:
        filters.append(DeliveryModel.created_at == datetime.now().date())

    if status_order:
        filters.append(DeliveryItemModel.status == status_order)

    items = await db.scalars(
        select(DeliveryItemModel)
        .join(DeliveryModel)
        .options(selectinload(DeliveryItemModel.delivery).selectinload(DeliveryModel.pvz))
        .where(*filters)
    )
    return items.all()

@router.post("/create_notification", response_model=NotificationSchema)
async def create_notification(
        create_notif: NotificationCreate,
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_operator)
):
    notification = NotificationModel(
        pvz_id=current_user.pvz_id,
        operator_id=current_user.id,
        type_problem=create_notif.type_problem,
        priority=create_notif.priority,
        message=create_notif.message,
        status="pending",
        timestamp=datetime.now().date()
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return notification

@router.get("/notifications", response_model=list[NotificationSchema])
async def get_notifications(
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_operator),
        status_notification: str | None = Query(None, pattern=r"^(pending|completed)$")
):
    filters = [NotificationModel.pvz_id == current_user.pvz_id]
    if status_notification:
        filters.append(NotificationModel.status == status_notification)

    notifications = await db.scalars(
        select(NotificationModel)
        .where(*filters)
        .order_by(NotificationModel.priority, NotificationModel.timestamp.desc()))
    return notifications.all()
