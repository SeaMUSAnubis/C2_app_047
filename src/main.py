from fastapi import FastAPI

from src.api.routes import router
from src.config import settings
from src.services.database import initialize_database

app = FastAPI(title=settings.app_name, version=settings.app_version)
initialize_database()
app.include_router(router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok"}
