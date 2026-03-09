from app.schemas import WeeklyLoadReport as WeeklyLoadReportSchema
from datetime import datetime, timedelta
from sqlalchemy import select, func, extract
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.pvz import PVZ as PVZModel
from app.models.operations import Operation as OperationModel
from app.schemas import HourlyLoad as HourlyLoadSchema, DailyLoadReport as DailyLoadReportSchema

class PVZNotFoundError(Exception):
    """ПВЗ не найден"""
    pass

class InvalidDateError(Exception):
    """Неверный формат даты"""
    pass

async def get_daily_load_data(
    pvz_id: int,
    date_str: str,
    db: AsyncSession
) -> DailyLoadReportSchema:
    """
    Возвращает отчёт о почасовой нагрузке ПВЗ за указанную дату.
    Если ПВЗ не существует – выбрасывает PVZNotFoundError.
    Если формат даты неверен – выбрасывает InvalidDateError.
    """
    # Проверяем существование ПВЗ
    pvz = await db.get(PVZModel, pvz_id)
    if not pvz:
        raise PVZNotFoundError(f"ПВЗ с ID {pvz_id} не найден")

    # Парсим дату
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise InvalidDateError("Неверный формат даты. Ожидается YYYY-MM-DD")

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

    hourly_counts = {int(row.hour): row.count for row in rows}

    hourly = []
    total_ops = 0
    overload_hours = 0

    start_hour = int(pvz.work_start.split(':')[0])
    end_hour = int(pvz.work_end.split(':')[0])

    for hour in range(start_hour, end_hour + 1, 1):
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
        date=date_str,
        capacity_per_hour=pvz.capacity_per_hour,
        hourly=hourly,
        total_operations=total_ops,
        overload_hours=overload_hours
    )


async def get_weekly_load_data(
    pvz_id: int,
    start_date: str,
    db: AsyncSession
) -> WeeklyLoadReportSchema:
    """
    Формирует недельный отчёт о нагрузке ПВЗ.
    Начинает с указанной даты (start_date) и собирает данные за 7 дней.
    """
    try:
        current = datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        raise InvalidDateError("Неверный формат даты начала. Ожидается YYYY-MM-DD")

    daily_reports = []
    total_overload = 0

    for _ in range(7):
        day_str = current.strftime("%Y-%m-%d")
        report = await get_daily_load_data(pvz_id, day_str, db)
        daily_reports.append(report)
        total_overload += report.overload_hours
        current += timedelta(days=1)

    return WeeklyLoadReportSchema(
        pvz_id=pvz_id,
        start_date=start_date,
        daily=daily_reports,
        total_overload_hours=total_overload
    )