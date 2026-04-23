from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.users import User as UserModel
from app.models.pvz import PVZ as PVZModel
from app.schemas import UserCreate, User as UserSchema
from app.db_depends import get_async_db
from app.auth import hash_password, verify_password, create_access_token
from fastapi.security import OAuth2PasswordRequestForm
from app.auth import get_current_user
from app.services.image_service import save_user_image, remove_user_image


router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate = Depends(UserCreate.as_form),
                      image: UploadFile | None = File(None),
                      db: AsyncSession = Depends(get_async_db)):
    """
    Эндпоинт для регистрации нового пользователя.
    Если роль оператора, автоматически назначается ПВЗ с наименьшим числом операторов
    (приоритет у ПВЗ без операторов).
    """

    # Проверка на существующее имя пользователя (желательно добавить для надёжности)
    existing = await db.scalar(select(UserModel).where(UserModel.email == user.email))
    if existing:
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")

    image_url = await save_user_image(image) if image else "/media/default_avatar.webp"
    # Создание объекта пользователя
    db_user = UserModel(
        name=user.name,
        email=user.email,
        hashed_password=hash_password(user.password),
        role=user.role,
        image_url=image_url
    )

    # Если роль оператора – ищем оптимальный ПВЗ
    if user.role == "operator":
        # Запрос: для каждого ПВЗ считаем количество привязанных операторов
        result = await db.execute(
            select(PVZModel, func.count(UserModel.id).label("op_count"))
            .outerjoin(UserModel, UserModel.pvz_id == PVZModel.id)
            .group_by(PVZModel.id)
            .order_by(func.count(UserModel.id), PVZModel.id)  # сортировка по возрастанию числа операторов
        )
        pvz_with_count = result.all()

        if pvz_with_count:
            best_pvz, _ = pvz_with_count[0]
            db_user.pvz_id = best_pvz.id

    # Сохранение в БД
    db.add(db_user)
    await db.commit()

    stmt = select(UserModel).where(UserModel.id == db_user.id).options(selectinload(UserModel.pvz))
    result = await db.scalars(stmt)
    db_user = result.first()
    return db_user


@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(),
                db: AsyncSession = Depends(get_async_db)):
    """
    Аутентифицирует пользователя и возвращает JWT с email, role и id,
    а также данные пользователя (включая ПВЗ для оператора).
    В user_data вшиты все необходимые данные для фронтенда
    """
    # Загружаем пользователя с подгрузкой связи pvz
    result = await db.scalars(
        select(UserModel)
        .where(UserModel.email == form_data.username)
        .options(selectinload(UserModel.pvz))
    )
    user = result.first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email, "role": user.role, "id": user.id})

    # Формируем данные пользователя с ПВЗ (если есть)
    user_data = {
        "id": user.id,
        "name": user.name,
        "image_url": user.image_url,
        "email": user.email,
        "role": user.role,
        "pvz": {
            "address": user.pvz.address,
            "work_start": user.pvz.work_start,
            "work_end": user.pvz.work_end
        } if user.pvz else None
    }

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    }

@router.patch("/update_name", response_model=UserSchema, status_code=200)
async def update_name(
        new_name: str = Query(..., min_length=3, max_length=50, description="Новое имя пользователя"),
        db_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_db)
):
    """
    Эндпоинт для обновления имени
    """
    db_user.name = new_name
    await db.commit()

    stmt = await db.scalars(
        select(UserModel).where(UserModel.id == db_user.id).options(selectinload(UserModel.pvz))
    )
    db_user = stmt.first()
    return db_user



@router.patch("/update_image", status_code=status.HTTP_200_OK)
async def update_image(
    image: UploadFile = File(...),
    db_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Эндпоинт для обновления аватарки
    """
    if not image.filename:
        raise HTTPException(400, "Файл не выбран")

    new_image_url = await save_user_image(image)
    old_image_url = db_user.image_url

    # Сначала обновляем БД
    db_user.image_url = new_image_url
    await db.commit()

    # После успешного коммита удаляем старый файл (если не дефолтный)
    if old_image_url and old_image_url != "/media/default_avatar.webp":
        remove_user_image(old_image_url)

    return {"message": "Фотография профиля успешно поменяна",
            "image_url": new_image_url}

@router.patch("/delete_image", status_code=status.HTTP_200_OK)
async def delete_image(
        db_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_db)
):
    """
    Эндпоинт для удаления аватарки и замены на дефолтную с Грю
    """
    old_image_url = db_user.image_url

    db_user.image_url = "/media/default_avatar.webp"
    await db.commit()

    if old_image_url  and old_image_url != "/media/default_avatar.webp":
        remove_user_image(old_image_url)

    return {"message": "Фотография профиля сброшена на стандартную",
            "image_url": "/media/default_avatar.webp"}