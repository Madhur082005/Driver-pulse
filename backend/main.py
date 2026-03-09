from fastapi import FastAPI
from routers.earnings_router import router as earnings_router

app = FastAPI()

app.include_router(earnings_router)