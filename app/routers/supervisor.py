from fastapi import APIRouter, HTTPException, status, Query
from fastapi.params import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_depends import get_async_db
from app.schemas import DailyLoadReport as DailyLoadReportSchema, WeeklyLoadReport as WeeklyLoadReportSchema, Operation as OperationSchema
from sqlalchemy import select, update
from app.models.deliveries import DeliveryItem as DeliveryItemModel, Delivery as DeliveryModel
from app.schemas import DeliveryItem as DeliveryItemSchema
from app.models.redirections import Redirection as RedirectionModel
from app.services.overloads_service import get_daily_load_data, get_weekly_load_data
from app.services.operations_service import get_operations_data
from datetime import datetime
from app.services.operations_service import PVZNotFoundError
from app.services.overloads_service import InvalidDateError
from app.models import User as UserModel
from app.auth import get_current_supervisor
from app.models.pvz import PVZ as PVZModel
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


@router.get("/operations/{pvz_id}", response_model=list[OperationSchema])
async def get_operations(
    pvz_id: int,
    str_date: str | None = Query(
        None,
        description="Дата в формате YYYY-MM-DD",
        pattern=r"^\d{4}-\d{2}-\d{2}$"  # опциональная проверка формата
    ),
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_supervisor)
):
    """
    Возвращает все операции, совершённые на ПВЗ.
    Можно фильтровать по дате (параметр str_date).
    """
    # Преобразуем строку в datetime, если передана
    target_date = None
    if str_date:
        try:
            target_date = datetime.strptime(str_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Ожидается YYYY-MM-DD."
            )

    try:
        operations = await get_operations_data(pvz_id, db, target_date)
    except PVZNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return operations



@router.put("/change_delivery/{delivery_item_id}", response_model=DeliveryItemSchema)
async def change_delivery(delivery_item_id: int,
                          new_delivery_id: int,
                          db: AsyncSession = Depends(get_async_db),
                          current_user: UserModel = Depends(get_current_supervisor)
                          ):
    """
    Перенаправляет заказы в другие доставки
    """
    stmt_1 = await db.scalars(select(DeliveryModel)
                        .where(DeliveryModel.id == new_delivery_id))

    delivery = stmt_1.first()
    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Доставка не найдена!")

    stmt_2 = await db.scalars(select(DeliveryItemModel)
                      .where(DeliveryItemModel.id == delivery_item_id))

    item = stmt_2.first()

    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден!")

    if item.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Действие над данным товаром производить нельзя, т.к. он уже обработан!")

    redirection = RedirectionModel(
        delivery_item_id=delivery_item_id,
        old_delivery_id=item.delivery_id,
        new_delivery_id=new_delivery_id,
    )
    db.add(redirection)

    await db.execute(
        update(DeliveryItemModel)
        .where(DeliveryItemModel.id == delivery_item_id)
        .values(delivery_id=new_delivery_id)
    )

    await db.commit()
    await db.refresh(item)
    return item

@router.put("/change_pvz_for_operator/{operator_id}")
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



