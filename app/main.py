from fastapi import FastAPI
from app.routers import operator, supervisor, tester, analyst, users
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="PVZ Management System", version="0.1.0")
app.include_router(operator.router)
app.include_router(supervisor.router)
app.include_router(tester.router)
app.include_router(analyst.router)
app.include_router(users.router)

# Разрешает только localhost и 127.0.0.1 с любыми портами из 4 цифр
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d{4}$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """
    Корневой маршрут, подтверждающий, что API работает.
    """
    return {"message": "Добро пожаловать в API!"}