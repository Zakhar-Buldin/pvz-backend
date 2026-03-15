from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.users import User as UserModel
from app.config import SECRET_KEY, ALGORITHM
from app.db_depends import get_async_db


# Создаём контекст для хеширования с использованием bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="users/token")

def hash_password(password: str) -> str:
    """
    Преобразует пароль в хеш с использованием bcrypt.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет, соответствует ли введённый пароль сохранённому хешу.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
    """
    Создаёт JWT с payload (sub, role, id, exp).
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme),
                           db: AsyncSession = Depends(get_async_db)):
    """
    Проверяет JWT и возвращает пользователя из базы.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception
    result = await db.scalars(
        select(UserModel).where(UserModel.email == email))
    user = result.first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_operator(current_user: UserModel = Depends(get_current_user)):
    """
    Проверяет, что пользователь имеет роль 'operator'.
    """
    if current_user.role != "operator":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Данное действие доступно только оператору!")
    return current_user

async def get_current_supervisor(current_user: UserModel = Depends(get_current_user)):
    """
    Проверяет, что пользователь имеет роль 'supervisor'.
    """
    if current_user.role != "supervisor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Данное действие доступно только супервайзеру!")
    return current_user

async def get_current_tester(current_user: UserModel = Depends(get_current_user)):
    """
    Проверяет, что пользователь имеет роль 'tester'.
    """
    if current_user.role != "tester":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Данное действие доступно только тестировщику!")
    return current_user

async def get_current_analyst(current_user: UserModel = Depends(get_current_user)):
    """
    Проверяет, что пользователь имеет роль 'analyst'.
    """
    if current_user.role != "analyst":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Данное действие доступно только аналитику!")
    return current_user