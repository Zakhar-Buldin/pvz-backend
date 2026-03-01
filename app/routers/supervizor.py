from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta
from fastapi.params import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_depends import get_async_db
from app.models.operations import Operation as OperationModel
from app.schemas import DailyLoadReport as DailyLoadReportSchema,  HourlyLoad as HourlyLoadSchema, WeeklyLoadReport as WeeklyLoadReportSchema, Operation as OperationSchema
from app.models.pvz import PVZ as PVZModel
from sqlalchemy import select, func, extract, text, update
from app.models.deliveries import DeliveryItem as DeliveryItemModel, Delivery as DeliveryModel
from app.schemas import Delivery as DeliverySchema, DeliveryItem as DeliveryItemSchema
from app.models.products import Product as ProductModel
from random import randint, sample

router = APIRouter(
    prefix="/supervizor",
    tags=["supervizor"],
)

from sqlalchemy import func, extract
from datetime import datetime, timedelta


@router.get("/statistics/one_day/{pvz_id}", response_model=DailyLoadReportSchema)
async def get_daily_load(
        pvz_id: int,
        date: str,  # формат "2026-02-22"
        db: AsyncSession = Depends(get_async_db)
):
    """
    Эндпоинт для оценки работы ПВЗ за один день
    """
    # Проверяем существование ПВЗ
    pvz = await db.get(PVZModel, pvz_id)
    if not pvz:
        raise HTTPException(404, "ПВЗ не найден")

    # Определяем границы дня
    target_date = datetime.strptime(date, "%Y-%m-%d")
    start = target_date
    end = target_date + timedelta(days=1)

    # Группируем операции по часам
    result = await db.execute(
        select(
            extract('hour', OperationModel.timestamp).label('hour'),
            func.count(OperationModel.id).label('count')
        )
        .where(OperationModel.pvz_id == pvz_id)
        .where(OperationModel.timestamp >= start)
        .where(OperationModel.timestamp < end)
        .group_by(extract('hour', OperationModel.timestamp))
        .order_by('hour')
    )
    rows = result.all()

    # Преобразуем в словарь для удобства
    hourly_counts = {int(row.hour): row.count for row in rows}

    # Формируем почасовой список (все часы с 0 до 23)
    hourly = []
    total_ops = 0
    overload_hours = 0
    for hour in range(24):
        ops = hourly_counts.get(hour, 0)
        total_ops += ops
        overload = ops > pvz.capacity_per_hour
        if overload:
            overload_hours += 1
        hourly.append(HourlyLoadSchema(
            hour=hour,
            operations=ops,
            overload=overload
        ))

    return DailyLoadReportSchema(
        pvz_id=pvz_id,
        date=date,
        capacity_per_hour=pvz.capacity_per_hour,
        hourly=hourly,
        total_operations=total_ops,
        overload_hours=overload_hours
    )


@router.get("/statistics/week/{pvz_id}", response_model=WeeklyLoadReportSchema)
async def get_weekly_load(
        pvz_id: int,
        start_date: str,  # дата понедельника (первого дня недели)
        db: AsyncSession = Depends(get_async_db)
):
    """
    Эндпоинт для оценки недельной работы одного ПВЗ
    """

    current = datetime.strptime(start_date, "%Y-%m-%d")
    daily_reports = []
    total_overload = 0

    for i in range(7):
        day_str = current.strftime("%Y-%m-%d")
        # Вызываем существующий эндпоинт или его внутреннюю логику
        report = await get_daily_load(pvz_id, day_str, db)
        daily_reports.append(report)
        total_overload += report.overload_hours
        current += timedelta(days=1)

    return WeeklyLoadReportSchema(
        pvz_id=pvz_id,
        start_date=start_date,
        daily=daily_reports,
        total_overload_hours=total_overload
    )


@router.get("/operations/{pvz_id}", response_model=list[OperationSchema])
async def get_operations(pvz_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Вовращает все операции, которые были совершены на ПВЗ
    """
    pvz = await db.scalars(select(PVZModel).where(PVZModel.id == pvz_id))
    if pvz.first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ПВЗ с ID {pvz_id} не найден")

    operations = await db.scalars(select(OperationModel).where(OperationModel.pvz_id == pvz_id))
    return operations.all()



@router.put("/change_delivery/{delivery_item_id}", response_model=DeliveryItemSchema)
async def change_delivery(delivery_item_id: int,
                          new_delivery_id: int,
                          db: AsyncSession = Depends(get_async_db)):
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

    await db.execute(
        update(DeliveryItemModel)
        .where(DeliveryItemModel.id == delivery_item_id)
        .values(delivery_id=new_delivery_id)
    )

    await db.commit()
    await db.refresh(item)
    return item
