from fastapi import APIRouter, HTTPException, status, Query
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db_depends import get_async_db
from app.schemas import DailyLoadReport as DailyLoadReportSchema, WeeklyLoadReport as WeeklyLoadReportSchema, Operation as OperationSchema, Delivery as DeliverySchema
from sqlalchemy import select, update
from app.models.deliveries import DeliveryItem as DeliveryItemModel, Delivery as DeliveryModel
from app.schemas import DeliveryItem as DeliveryItemSchema, PVZ as PVZSchema
from app.models.redirections import Redirection as RedirectionModel
from app.services.overloads_service import get_daily_load_data, get_weekly_load_data
from datetime import datetime
from app.services.operations_service import PVZNotFoundError
from app.services.overloads_service import InvalidDateError
from app.models import User as UserModel
from app.auth import get_current_supervisor
from app.models.pvz import PVZ as PVZModel
from sqlalchemy.orm import selectinload
from app.schemas import User as UserSchema
from app.models.notifications import Notification as NotificationModel
from app.schemas import Notification as NotificationSchema
from datetime import timedelta


router = APIRouter(
    prefix="/supervisor",
    tags=["supervisor"],
)


@router.get("/statistics/one_day/{pvz_id}", response_model=DailyLoadReportSchema)
async def get_daily_load(
    pvz_id: int,
    date: str,  # формат YYYY-MM-DD
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_supervisor),
):
    """
    Возвращает почасовую нагрузку на ПВЗ за указанную дату.
    """
    try:
        report = await get_daily_load_data(pvz_id, date, db)
    except PVZNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidDateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return report

@router.get("/statistics/week/{pvz_id}", response_model=WeeklyLoadReportSchema)
async def get_weekly_load(
        pvz_id: int,
        start_date: str = Query(..., description="Дата начала недели (понедельник) в формате YYYY-MM-DD"),
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_supervisor)
):
    """
    Возвращает недельный отчёт о нагрузке ПВЗ.
    Начинает с указанной даты (start_date) и собирает данные за 7 дней.
    """
    try:
        report = await get_weekly_load_data(pvz_id, start_date, db)
    except PVZNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidDateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return report


@router.put("/change_delivery/{delivery_item_id}", response_model=DeliveryItemSchema)
async def change_delivery(delivery_item_id: int,
                          new_delivery_id: int,
                          db: AsyncSession = Depends(get_async_db),
                          current_user: UserModel = Depends(get_current_supervisor)
                          ):
    """
    Перенаправляет заказы в другие доставки
    """
    stmt_1 = await db.scalars(select(DeliveryItemModel)
                      .where(DeliveryItemModel.id == delivery_item_id)
                      .options(
                            selectinload(DeliveryItemModel.delivery).selectinload(DeliveryModel.pvz)
                      )
    )
    item = stmt_1.first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден!")

    if item.delivery.id == new_delivery_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Заказ уже находится в данной доставке")

    new_delivery = await db.get(DeliveryModel, new_delivery_id)

    if new_delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Доставка не найдена!")

    delivery_date = new_delivery.created_at

    if item.delivery.created_at != delivery_date:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Нельзя перенаправлять заказ в доставку, которая запланирована на другую дату!")

    if item.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Действие над данным товаром производить нельзя, т.к. он уже обработан!")

    redirection = RedirectionModel(
        delivery_item_id=delivery_item_id,
        old_delivery_id=item.delivery_id,
        new_delivery_id=new_delivery_id,
        timestamp=delivery_date
    )
    db.add(redirection)

    await db.execute(
        update(DeliveryItemModel)
        .where(DeliveryItemModel.id == delivery_item_id)
        .values(delivery_id=new_delivery_id)
    )

    await db.commit()
    result = await db.scalars(
        select(DeliveryItemModel)
        .where(DeliveryItemModel.id == delivery_item_id)
        .options(selectinload(DeliveryItemModel.delivery).selectinload(DeliveryModel.pvz))
    )
    item = result.first()
    return item

@router.patch("/change_pvz_for_operator/{operator_id}")
async def change_pvz_for_operator(
                                operator_id: int,
                                new_pvz_id: int,
                                db: AsyncSession = Depends(get_async_db),
                                current_user: UserModel = Depends(get_current_supervisor)):
    stmt_1 = await db.scalars(select(UserModel)
                              .where(UserModel.id == operator_id)
                              .where(UserModel.role == "operator"))
    operator = stmt_1.first()
    if operator is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оператор не найден")

    if new_pvz_id == operator.pvz_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Оператор уже закреплён за этим ПВЗ")

    stmt = await db.scalars(select(PVZModel).where(PVZModel.id == new_pvz_id))
    pvz = stmt.first()

    if pvz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ПВЗ не найден")

    operator.pvz_id = new_pvz_id
    await db.commit()
    await db.refresh(operator)
    return {"message": f"Оператор {operator_id} закреплён за ПВЗ {operator.pvz_id}"}

@router.get("/operators", response_model=list[UserSchema])
async def get_operators(db: AsyncSession = Depends(get_async_db),
                        current_user: UserModel = Depends(get_current_supervisor)):
    stmt = await db.scalars(
        select(UserModel).where(UserModel.role == "operator")
        .options(selectinload(UserModel.pvz))
        .order_by(UserModel.id)
    )
    return stmt.all()


@router.get("/delivery_items/{pvz_id}", response_model=list[DeliveryItemSchema])
async def get_deliveries(
                     pvz_id: int,
                     created_date: str  = Query(...,
                                            description="Дата формате YYYY-MM-DD (к примеру, 2024-01-01)",
                                            pattern=r"^\d{4}-\d{2}-\d{2}$"
                                            ),
                     db: AsyncSession = Depends(get_async_db),
                     current_user: UserModel = Depends(get_current_supervisor)
):
    """Возвращает список заказов ПВЗ за конкретную дату"""
    pvz = await db.get(PVZModel, pvz_id)
    if pvz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ПВЗ не найден!")

    try:
        target_date = datetime.strptime(created_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат даты. Ожидается YYYY-MM-DD."
            )

    items = await db.scalars(
        select(DeliveryItemModel)
        .join(DeliveryModel)
        .options(
            selectinload(DeliveryItemModel.delivery).selectinload(DeliveryModel.pvz)
        )
        .where(DeliveryModel.pvz_id == pvz_id)
        .where(DeliveryModel.created_at == target_date)
        .where(DeliveryItemModel.status == "pending")
    )
    return items.all()

@router.get("/deliveries_for_redirect/{delivery_item_id}", response_model=list[DeliverySchema])
async def get_all_pvz(
                        delivery_item_id: int,
                        db: AsyncSession = Depends(get_async_db),
                        current_user: UserModel = Depends(get_current_supervisor)
):
    stmt = await db.scalars(
        select(DeliveryItemModel)
        .options(selectinload(DeliveryItemModel.delivery))
        .where(DeliveryItemModel.id == delivery_item_id)
    )

    item = stmt.first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден!")

    deliveries = await db.scalars(
        select(DeliveryModel)
        .options(selectinload(DeliveryModel.pvz))
        .where(DeliveryModel.created_at == item.delivery.created_at)
        .where(DeliveryModel.id != item.delivery.id)
    )
    return deliveries.all()

@router.get("/all_pvz", response_model=list[PVZSchema])
async def get_all_pvz(
        db_user: UserModel = Depends(get_current_supervisor),
        db: AsyncSession = Depends(get_async_db)
):
    pvz_list = await db.scalars(select(PVZModel))
    return pvz_list.all()

@router.get("/all_notifications", response_model=list[NotificationSchema])
async def get_all_notifications(
        db_user: UserModel = Depends(get_current_supervisor),
        db: AsyncSession = Depends(get_async_db)
):
    current_date = datetime.today().date()
    week_ago = current_date - timedelta(days=7)

    notifications = await db.scalars(
        select(NotificationModel)
        .where(NotificationModel.status == "pending")
        .where(NotificationModel.timestamp <= current_date)
        .where(NotificationModel.timestamp >= week_ago)
        .order_by(NotificationModel.priority, NotificationModel.timestamp, NotificationModel.id)
    )
    return notifications.all()

@router.patch("/change_status_notification/{notification_id}", response_model=NotificationSchema)
async def change_status_notification(
        notification_id: int,
        db_user: UserModel = Depends(get_current_supervisor),
        db: AsyncSession = Depends(get_async_db)
):
    notification = await db.get(NotificationModel, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")

    if notification.status == "completed":
        raise HTTPException(status_code=409, detail="Уведомление уже обработано")

    notification.status = "completed"
    await db.commit()
    await db.refresh(notification)
    return notification