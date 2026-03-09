from fastapi import FastAPI
from app.routers import operator, supervizor, tester, export

app = FastAPI(title="PVZ Management System", version="0.1.0")
app.include_router(operator.router)
app.include_router(supervizor.router)
app.include_router(tester.router)
app.include_router(export.router)
@app.get("/")
async def root():
    """
    Корневой маршрут, подтверждающий, что API работает.
    """
    return {"message": "Добро пожаловать в API!"}