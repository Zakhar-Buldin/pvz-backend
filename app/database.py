from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase


# --------------- Асинхронное подключение к PostgreSQL -------------------------
# Строка подключения для PostgreSQl

DATABASE_URL = "postgresql+asyncpg://pvz_user:zahar71104@localhost:5432/pvz_db"

# Создаём Engine
async_engine = create_async_engine(DATABASE_URL, echo=True)

# Настраиваем фабрику сеансов
async_session_maker = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass