from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import router
from src.config import settings
from src.services.database import initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    initialize_database()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.include_router(router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok"}
