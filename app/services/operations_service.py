from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.operations import Operation as OperationModel
from app.models.pvz import PVZ as PVZModel

class PVZNotFoundError(Exception):
    """Кастомное исключение для отсутствующего ПВЗ"""
    pass

async def get_operations_data(
    pvz_id: int,
    db: AsyncSession,
    target_date: Optional[datetime] = None
) -> List[OperationModel]:
    """
    Возвращает список операций для ПВЗ.
    Если ПВЗ не существует – выбрасывает PVZNotFoundError.
    """
    # Проверяем существование ПВЗ
    pvz = await db.scalar(select(PVZModel).where(PVZModel.id == pvz_id))
    if not pvz:
        raise PVZNotFoundError(f"ПВЗ с ID {pvz_id} не найден")

    filters = [OperationModel.pvz_id == pvz_id]

    if target_date:
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        filters.append(OperationModel.timestamp >= start_of_day)
        filters.append(OperationModel.timestamp < end_of_day)

    result = await db.scalars(select(OperationModel).where(*filters))
    return result.all()