from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import csv
import io

from app.db_depends import get_async_db
from app.models.products import Product as ProductModel
from app.models.pvz import PVZ as PVZModel
from app.models.operations import Operation as OperationModel
from app.models.redirections import Redirection as RedirectionModel
from datetime import datetime, timedelta
from app.services.overloads_service import InvalidDateError, PVZNotFoundError, get_daily_load_data, get_weekly_load_data
router = APIRouter(prefix="/export", tags=["export"])

@router.get("/products")
async def export_products(
    db: AsyncSession = Depends(get_async_db)
):
    """
    Выгружает все
    товары в формате CSV.
    """
    # Формируем запрос к БД
    query = select(ProductModel)

    result = await db.scalars(query)
    products = result.all()

    # Создаём CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')  # точка с запятой для 1С
    writer.writerow(['id', 'name', 'price'])     # заголовки

    for p in products:
        writer.writerow([p.id, p.name, str(p.price)])

    output.seek(0)

    # Генерируем имя файла
    filename = "products.csv"

    return StreamingResponse(
        output,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/pvz")
async def export_products(
    db: AsyncSession = Depends(get_async_db)
):
    """
    Выгружает все
    ПВЗ в формате CSV.
    """
    # Формируем запрос к БД

    query = select(PVZModel)

    result = await db.scalars(query)
    pvz = result.all()

    # Создаём CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')  # точка с запятой для 1С
    writer.writerow(['id', 'address', 'capacity_per_hour', 'is_active', 'work_start', 'work_end'])     # заголовки

    for p in pvz:
        writer.writerow([p.id, p.address, str(p.capacity_per_hour), str(p.is_active), str(p.work_start), str(p.work_end)])

    output.seek(0)

    # Генерируем имя файла
    filename = "pvz.csv"

    return StreamingResponse(
        output,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/operations")
async def export_operations(
    pvz_id: int | None,
    start_date_str: str | None = Query(None,
                                description="Дата формате YYYY-MM-DD",
                                pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date_str: str | None = Query(None,
                                description="Дата в формате YYYY-MM-DD",
                                pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Выгружает все
    операции в формате CSV.
    """
    filters = []
    # Формируем запрос к БД
    if pvz_id:
        stmt = await db.scalars(select(PVZModel).where(PVZModel.id == pvz_id))
        find_pvz = stmt.first()
        if find_pvz is None:
            raise HTTPException(status_code=404, detail="PVZ not found")
        filters.append(OperationModel.pvz_id == pvz_id)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            filters.append(OperationModel.timestamp >= start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат start_date. Ожидается YYYY-MM-DD")

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            filters.append(OperationModel.timestamp < end_date + timedelta(days=1))
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат end_date. Ожидается YYYY-MM-DD")

    query = select(OperationModel)

    result = await db.scalars(query.where(*filters))
    operations = result.all()

    # Создаём CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')  # точка с запятой для 1С
    writer.writerow(['id', 'delivery_item_id', 'pvz_id', 'action', 'timestamp']) # заголовки

    for op in operations:
        writer.writerow([op.id, op.delivery_item_id, op.pvz_id, op.action, op.timestamp.isoformat()])

    output.seek(0)

    # Генерируем имя файла
    filename = "operations.csv"

    return StreamingResponse(
        output,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/redirections")
async def export_redirections(
    start_date_str: str | None = Query(None,
                                description="Дата в формате YYYY-MM-DD",
                                pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date_str: str | None = Query(None,
                                description="Дата в формате YYYY-MM-DD",
                                pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Выгружает все
    перенаправления в формате CSV.
    """
    filters = []
    # Формируем запрос к БД

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            filters.append(RedirectionModel.timestamp >= start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат start_date. Ожидается YYYY-MM-DD")

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            filters.append(RedirectionModel.timestamp < end_date + timedelta(days=1))
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат end_date. Ожидается YYYY-MM-DD")

    query = select(RedirectionModel)

    result = await db.scalars(query.where(*filters))
    redirections = result.all()

    # Создаём CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')  # точка с запятой для 1С
    writer.writerow(['id', 'delivery_item_id', 'old_delivery_id', 'new_delivery_id', 'timestamp']) # заголовки

    for r in redirections:
        writer.writerow([r.id, r.delivery_item_id, r.old_delivery_id, r.new_delivery_id, r.timestamp.isoformat()])

    output.seek(0)

    # Генерируем имя файла
    filename = "redirections.csv"

    return StreamingResponse(
        output,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/statistics/one_day")
async def export_daily_load(
    pvz_id: int,
    date: str = Query(...,
                description="Дата в формате YYYY-MM-DD",
                pattern = r"^\d{4}-\d{2}-\d{2}$"),

    db: AsyncSession = Depends(get_async_db)
):
    """
    Возвращает почасовую нагрузку на ПВЗ за указанную дату.
    """
    try:
        report = await get_daily_load_data(pvz_id, date, db)
        # Создаём CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['pvz_id', 'date', 'hour', 'operations', 'overload'])

        for hour_data in report.hourly:
            writer.writerow([
                report.pvz_id,
                report.date,
                hour_data.hour,
                hour_data.operations,
                hour_data.overload
            ])

        output.seek(0)
        filename = f"daily_load_pvz{pvz_id}_{date}.csv"
        return StreamingResponse(
            output,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except PVZNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidDateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/statistics/week")
async def export_weekly_load(
        pvz_id: int,
        start_date: str = Query(...,
                                description="Дата начала недели (понедельник) в формате YYYY-MM-DD",
                                pattern=r"^\d{4}-\d{2}-\d{2}$"),

        db: AsyncSession = Depends(get_async_db)
):
    """
    Возвращает недельный отчёт о нагрузке ПВЗ.
    Начинает с указанной даты (start_date) и собирает данные за 7 дней.
    """
    try:
        report = await get_weekly_load_data(pvz_id, start_date, db)
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['pvz_id', 'date', 'hour', 'operations', 'overload'])

        for day_report in report.daily:
            for hour_data in day_report.hourly:
                writer.writerow([
                    report.pvz_id,
                    day_report.date,
                    hour_data.hour,
                    hour_data.operations,
                    hour_data.overload
                ])

        output.seek(0)
        filename = f"weekly_hourly_pvz{pvz_id}_{start_date}.csv"
        return StreamingResponse(
            output,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except PVZNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidDateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))