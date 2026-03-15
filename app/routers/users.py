from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.users import User as UserModel
from app.models.pvz import PVZ as PVZModel
from app.schemas import UserCreate, User as UserSchema
from app.db_depends import get_async_db
from app.auth import hash_password, verify_password, create_access_token
from fastapi.security import OAuth2PasswordRequestForm


router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_async_db)):
    """
    Эндпоинт для регистрации нового пользователя.
    Если роль оператора, автоматически назначается ПВЗ с наименьшим числом операторов
    (приоритет у ПВЗ без операторов).
    """

    # Проверка на существующее имя пользователя (желательно добавить для надёжности)
    existing = await db.scalar(select(UserModel).where(UserModel.email == user.email))
    if existing:
        raise HTTPException(status_code=409, detail="Пользователь с таким именем уже существует")

    # Создание объекта пользователя
    db_user = UserModel(
        email=user.email,
        hashed_password=hash_password(user.password),
        role=user.role
    )

    # Если роль оператора – ищем оптимальный ПВЗ
    if user.role == "operator":
        # Запрос: для каждого ПВЗ считаем количество привязанных операторов
        result = await db.execute(
            select(PVZModel, func.count(UserModel.id).label("op_count"))
            .outerjoin(UserModel, UserModel.pvz_id == PVZModel.id)
            .group_by(PVZModel.id)
            .order_by(func.count(UserModel.id))  # сортировка по возрастанию числа операторов
        )
        pvz_with_count = result.all()

        if not pvz_with_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нет доступных ПВЗ для назначения оператора"
            )

        # Берём первый ПВЗ (с минимальным количеством операторов)
        best_pvz, _ = pvz_with_count[0]
        db_user.pvz_id = best_pvz.id

    # Сохранение в БД
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(),
                db: AsyncSession = Depends(get_async_db)):
    """
    Аутентифицирует пользователя и возвращает JWT с email, role и id.
    """
    result = await db.scalars(
        select(UserModel).where(UserModel.email == form_data.username))
    user = result.first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email, "role": user.role, "id": user.id})
    return {"access_token": access_token, "token_type": "bearer"}