from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta
from fastapi.params import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.db_depends import get_async_db
from app.models.operations import Operation as OperationModel
from app.models.pvz import PVZ as PVZModel
from sqlalchemy import select, text
from app.models.deliveries import DeliveryItem as DeliveryItemModel, Delivery as DeliveryModel
from app.schemas import Delivery as DeliverySchema
from app.models.products import Product as ProductModel
from app.auth import get_current_tester
from app.models import User as UserModel
from app.models import Redirection as RedirectionModel
import random



router = APIRouter(
    prefix="/tester",
    tags=["tester"],
)

# POST эндпоинт для создания поставки на ПВЗ
@router.post("/accept_delivery/{pvz_id}", response_model=DeliverySchema)
async def accept_random_delivery(
        pvz_id: int,
        db: AsyncSession = Depends(get_async_db),
        created_date: str = Query(...,
                          description="Предполагаемая дата поставки на ПВЗ формате YYYY-MM-DD",
                          pattern=r"^\d{4}-\d{2}-\d{2}$"),
        min_quan: int = Query(default=1, description="Минимальное кол-во генерируемых заказов"),
        max_quan: int = Query(..., description="Максимальное кол-во генерируемых заказов"),
        current_user: UserModel = Depends(get_current_tester)
):
    """
    Создаёт объект Delivery, который имитирует поставку товаров на ПВЗ.
    Из списка всех товаров, которые лежат на складе в таблице products, выбираются рандомные индексы товаров.
    На их основе собирается объект Delivery, который представляет собой большую коробку, в которой хранятся все заказы
    и которая поставляется на ПВЗ.
    """
    if min_quan < 1 or max_quan < 1 or min_quan > max_quan:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Некорретные данные диапазона чисел для генерации заказов!")

    try:
        result_date = datetime.strptime(created_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат date. Ожидается YYYY-MM-DD")

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
    selected_products = [available_products[random.randint(0, len(available_products) - 1)] for _ in range(random.randint(min_quan, max_quan))]

    # 3. Создаём поставку
    new_delivery = DeliveryModel(
        pvz_id=pvz_id,
        total_price=sum(i.price for i in selected_products),
        created_at=result_date
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
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_tester)
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
    await db.execute(text("TRUNCATE TABLE redirections RESTART IDENTITY CASCADE;"))

    await db.commit()
    return None


@router.post("/generate_evening_flow/{pvz_id}")
async def generate_evening_flow(
        pvz_id: int,
        delivery_id: int,
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_tester)
):
    """
    Генерирует поток клиентов (выдачи/возвраты) преимущественно в вечерние часы.
    Использует ту же логику, что и реальный оператор.
    """
    delivery = await db.get(DeliveryModel, delivery_id)
    if delivery is None:
        raise HTTPException(404, "Доставки не существует!")

    # Получаем все товары этого ПВЗ, которые уже приняты (status='received')
    result = await db.scalars(
        select(DeliveryItemModel)
        .join(DeliveryModel)
        .where(DeliveryModel.id == delivery_id)
        .where(DeliveryModel.pvz_id == pvz_id)
        .where(DeliveryItemModel.status == "received")
    )

    items = result.all()
    if not items:
        raise HTTPException(404, "Нет доступных заказов для генерации операций")

    # Нагрузка на ПВЗ в часы работы 9:00 - 21:00
    hours_weights = [1, 1, 1, 1, 1, 2, 2, 3, 3, 4, 4, 3, 2]

    created = 0
    selected_items = random.sample(items, len(items))

    for item in selected_items:
        # выбираем час с учётом веса
        hour = random.choices(range(9, 22), weights=hours_weights)[0]
        minute = random.randint(0, 59)
        op_time = datetime(delivery.created_at.year, delivery.created_at.month, delivery.created_at.day).replace(hour=hour, minute=minute)

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

@router.post("/generate_morning_flow/{pvz_id}")
async def generate_morning_flow(
        pvz_id: int,
        delivery_id: int,
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_tester)
):
    """
    Генерирует поток клиентов (выдачи/возвраты) преимущественно в утренние/обеденные часы.
    Использует ту же логику, что и реальный оператор.
    """
    stmt = await db.scalars(
                         select(DeliveryModel)
                  .where(DeliveryModel.id == delivery_id)
                  .options(selectinload(DeliveryModel.items)))

    delivery = stmt.first()

    if delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Объект доставки еще не сформирован складе, или неверный ID доставки')

    if delivery.pvz_id != pvz_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Эта доставка не связана с данным пунктом выдачи!')

    hour = random.randint(9, 12)
    minute = random.randint(0, 59)
    created = 0
    start_time = datetime(delivery.created_at.year, delivery.created_at.month, delivery.created_at.day).replace(hour=hour, minute=minute)

    for i, item in enumerate(delivery.items):
        if item.status != "pending":
                continue

        item_time = start_time + timedelta(minutes=i) + timedelta(seconds=random.randint(0, 59))
        item.status = "received"
        operation = OperationModel(
            delivery_item_id=item.id,
            pvz_id=pvz_id,
            action="received",
            timestamp=item_time
        )
        db.add(operation)
        created += 1

    await db.commit()
    return {"message": f"Создано {created} операций для ПВЗ {pvz_id}"}

@router.post("/create_new_pvz")
async def create_new_pvz(
        address: str = Query(..., min_length=5, max_length=50),
        capacity_per_hour: int = Query(10, gt=0, le=100),
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_tester)
):
    pvz = PVZModel(
        address=address,
        capacity_per_hour=capacity_per_hour,
    )

    db.add(pvz)
    await db.commit()

    await db.refresh(pvz)
    return {"message": f"ПВЗ {pvz.id} успешно создан"}


@router.post("/create_products")
async def create_100_products(db: AsyncSession = Depends(get_async_db),
                              current_user: UserModel = Depends(get_current_tester)):
    """
    Создаёт 100 тестовых товаров в таблице products.
    Предварительно очищает таблицу.
    """
    # Очищаем таблицу products
    await db.execute(text("TRUNCATE TABLE products RESTART IDENTITY CASCADE;"))

    # Генерируем 100 товаров со случайными ценами
    products = []
    for i in range(1, 101):
        product = ProductModel(
            name=f"Товар {i}",
            price=round(random.uniform(100, 10000), 2)  # случайная цена от 100 до 10000
        )
        products.append(product)

    db.add_all(products)
    await db.commit()

    return {"message": "100 товаров успешно созданы"}

@router.post("/redirect_orders/{delivery_id}")
async def change_delivery(
        delivery_id: int,
        new_delivery_id: int,
        quantity: int = Query(ge=1, le=100),
        db: AsyncSession = Depends(get_async_db),
        current_user: UserModel = Depends(get_current_tester)
):
    if delivery_id == new_delivery_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Нельзя перенаправить заказы в ту же доставку")

    stmt = await db.scalars(
        select(DeliveryModel)
        .where(DeliveryModel.id == delivery_id)
        .options(selectinload(DeliveryModel.items)))
    old_delivery = stmt.first()

    if old_delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Доставка не найдена")

    new_delivery = await db.get(DeliveryModel, new_delivery_id)
    if new_delivery is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Доставка для перенаправления не найдена")

    if old_delivery.created_at != new_delivery.created_at:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Нельзя перенаправлять заказы в доставку, которая запланирована на другую дату")

    items = list(filter(lambda a: a.status == "pending", old_delivery.items))
    length_items = len(items)
    if length_items < quantity:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"В доставке нет такого количества заказов. Доступно только {length_items} заказов")

    selected_items = random.sample(items, quantity)

    for item in selected_items:
        redirection = RedirectionModel(
            delivery_item_id=item.id,
            old_delivery_id=delivery_id,
            new_delivery_id=new_delivery_id,
            timestamp=old_delivery.created_at
        )
        db.add(redirection)
        item.delivery_id = new_delivery_id

    await db.commit()
    return {"message": f"Заказы успешно перенаправлены в доставку {new_delivery_id}",
            "count": len(selected_items)}
