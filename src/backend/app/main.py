import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.backend.app.api.routes import router
from src.backend.app.api.routes_agents import router as agents_router
from src.backend.app.api.routes_alerts import router as alerts_router
from src.backend.app.api.routes_health import router as health_router
from src.backend.app.api.routes_logs import router as logs_router
from src.backend.app.api.routes_ml import router as ml_router
from src.backend.app.config import settings
from src.backend.app.db.session import initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    initialize_database()
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

app.include_router(router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(health_router)
app.include_router(logs_router)
app.include_router(alerts_router)
app.include_router(ml_router)

_frontend_dist = Path(os.getenv("FRONTEND_DIST_DIR", "src/frontend/dist"))
_frontend_index = _frontend_dist / "index.html"
if (_frontend_dist / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_frontend_dist / "assets"), name="frontend-assets")


@app.get("/", response_model=None)
async def root():
    if _frontend_index.is_file():
        return FileResponse(_frontend_index)
    return {"service": settings.app_name, "status": "ok"}


@app.get("/{full_path:path}", include_in_schema=False)
async def frontend_spa(full_path: str) -> FileResponse:
    if not _frontend_index.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    if full_path.startswith(("api/", "health", "logs", "alerts", "ml/")):
        raise HTTPException(status_code=404, detail="Not found")

    requested_file = _frontend_dist / full_path
    if requested_file.is_file():
        return FileResponse(requested_file)
    return FileResponse(_frontend_index)
