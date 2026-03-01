from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta
from fastapi.params import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_depends import get_async_db
from app.models.operations import Operation as OperationModel
from app.models.pvz import PVZ as PVZModel
from sqlalchemy import select, func, extract, text, update
from app.models.deliveries import DeliveryItem as DeliveryItemModel, Delivery as DeliveryModel
from app.schemas import Delivery as DeliverySchema, DeliveryItem as DeliveryItemSchema
from app.models.products import Product as ProductModel
import random



router = APIRouter(
    prefix="/tester",
    tags=["tester"],
)

# POST эндпоинт для создания поставки на ПВЗ
@router.post("/accept_delivery/{pvz_id}", response_model=DeliverySchema)
async def accept_random_delivery(
        pvz_id: int,
        db: AsyncSession = Depends(get_async_db)
):
    """
    Создаёт объект Delivery, который имитирует поставку товаров на ПВЗ.
    Из списка всех товаров, которые лежат на складе в таблице products, выбираются рандомные индексы товаров.
    На их основе собирается объект Delivery, который представляет собой большую коробку, в которой хранятся все заказы
    и которая поставляется на ПВЗ.
    """
    # Проверяем существование ПВЗ
    pvz = await db.get(PVZModel, pvz_id)
    if not pvz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ПВЗ с ID {pvz_id} не найден"
        )

    # 1. Получаем все товары, которые есть в наличии
    products_query = await db.scalars(
        select(ProductModel)
    )
    available_products = products_query.all()


    # 2. Выбираем случайное количество товаров для поставки
    selected_products = random.sample(available_products, random.randint(25, len(available_products)))

    # 3. Создаём поставку
    new_delivery = DeliveryModel(
        pvz_id=pvz_id,
        total_price=sum(i.price for i in selected_products)
    )

    db.add(new_delivery)
    await db.flush()  # получаем ID новой поставки

    # 4. Создаём товары для поставки (все со статусом received)
    delivery_items = []
    for product in selected_products:

        delivery_item = DeliveryItemModel(
            delivery_id=new_delivery.id,
            product_id=product.id,
            status="pending"
        )
        delivery_items.append(delivery_item)
        db.add(delivery_item)


    # 5. Сохраняем всё в БД
    await db.commit()

    # 6. Загружаем связанные товары для ответа
    await db.refresh(new_delivery, attribute_names=["items"])

    return new_delivery


@router.delete("/clear_all_data", status_code=status.HTTP_204_NO_CONTENT)
async def clear_all_data(
    confirm: bool = Query(False, description="Подтверждение очистки (обязательно)"),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Удаляет все данные из таблиц operations, delivery_items, deliveries.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо подтверждение: confirm=true"
        )

    # Удаляем в правильном порядке (дочерние → родительские)
    await db.execute(text("TRUNCATE TABLE operations RESTART IDENTITY CASCADE;"))
    await db.execute(text("TRUNCATE TABLE delivery_items RESTART IDENTITY CASCADE;"))
    await db.execute(text("TRUNCATE TABLE deliveries RESTART IDENTITY CASCADE;"))

    await db.commit()
    return None


@router.post("/generate_evening_flow/{pvz_id}")
async def generate_evening_flow(
        pvz_id: int,
        date: str,
        db: AsyncSession = Depends(get_async_db)
):
    """
    Генерирует поток клиентов (выдачи/возвраты) преимущественно в вечерние часы.
    Использует ту же логику, что и реальный оператор.
    """
    # Получаем все товары этого ПВЗ, которые уже приняты (status='received')
    result = await db.execute(
        select(DeliveryItemModel)
        .join(DeliveryModel)
        .where(DeliveryModel.pvz_id == pvz_id)
        .where(DeliveryItemModel.status == "received")
    )
    items = result.scalars().all()
    if not items:
        raise HTTPException(404, "Нет доступных заказов для генерации операций")

    # Нагрузка на ПВЗ в часы работы 9:00 - 21:00
    hours_weights = [1, 1, 1, 1, 1, 1, 1, 1, 4, 4, 4, 4, 2]

    created = 0
    selected_items = random.sample(items, min(50, len(items)))

    for item in selected_items[:50]:
        # выбираем час с учётом веса
        hour = random.choices(range(9, 22), weights=hours_weights)[0]
        minute = random.randint(0, 59)
        op_time = datetime.strptime(date, "%Y-%m-%d").replace(hour=hour, minute=minute)

        action = random.choices(["issued", "returned"], weights=[0.8, 0.2])[0]

        item.status = action
        operation = OperationModel(
            delivery_item_id=item.id,
            pvz_id=pvz_id,
            action=action,
            timestamp=op_time
        )
        db.add(operation)
        created += 1

    await db.commit()
    return {"message": f"Создано {created} операций для ПВЗ {pvz_id}"}