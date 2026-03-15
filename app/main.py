from fastapi import FastAPI
from app.routers import operator, supervisor, tester, analyst, users

app = FastAPI(title="PVZ Management System", version="0.1.0")
app.include_router(operator.router)
app.include_router(supervisor.router)
app.include_router(tester.router)
app.include_router(analyst.router)
app.include_router(users.router)

@app.get("/")
async def root():
    """
    Корневой маршрут, подтверждающий, что API работает.
    """
    return {"message": "Добро пожаловать в API!"}