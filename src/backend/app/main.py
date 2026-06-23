import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, FileResponse as StarletteFileResponse


class NoCacheStaticFiles(StaticFiles):
    """StaticFiles that force no-cache headers on every response."""

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, StarletteFileResponse):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

from src.backend.app.api.routes import router
from src.backend.app.api.routes_admin import router as admin_router
from src.backend.app.api.routes_agents import router as agents_router
from src.backend.app.api.routes_alerts import router as alerts_router
from src.backend.app.api.routes_health import router as health_router
from src.backend.app.api.routes_llm import router as llm_router
from src.backend.app.api.routes_logs import router as logs_router
from src.backend.app.api.routes_ml import router as ml_router
from src.backend.app.config import settings
from src.backend.app.db.pool import close_pool, init_pool
from src.backend.app.db.session import initialize_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    # Phase A.0: initialise the DB connection pool before any other code
    # touches the database. Failure here is fatal — surface it.
    init_pool()
    initialize_database()

    # Phase 3: start the normalizer/scoring background loop.
    stop_event = asyncio.Event()
    normalizer_task: asyncio.Task | None = None
    if settings.normalizer_enabled:
        from src.backend.app.services.normalizer import normalizer_loop

        normalizer_task = asyncio.create_task(
            normalizer_loop(stop_event), name="normalizer-loop"
        )
        logger.info("lifespan: normalizer-loop scheduled")
    else:
        logger.info("lifespan: normalizer disabled (NORMALIZER_ENABLED=false)")

    app.state.normalizer_stop_event = stop_event
    app.state.normalizer_task = normalizer_task

    try:
        yield
    finally:
        # Phase 3: signal the background loop to exit and wait briefly.
        if normalizer_task is not None:
            stop_event.set()
            try:
                await asyncio.wait_for(normalizer_task, timeout=5.0)
            except TimeoutError:
                normalizer_task.cancel()
                try:
                    await normalizer_task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass
            except Exception:  # noqa: BLE001
                logger.exception("lifespan: error stopping normalizer-loop")

        # Phase A.0: close the DB pool last so any in-flight requests finish
        # before the connections are dropped.
        close_pool()

        # Phase 3: close the LLM provider's HTTP clients (reused across calls,
        # so we must close them on shutdown to avoid leaking connections).
        try:
            from src.backend.app.services.llm.providers import get_provider
            provider = get_provider()
            if hasattr(provider, "aclose"):
                await provider.aclose()
        except RuntimeError:
            # Provider was never initialised (e.g. no API key); skip.
            pass
        except Exception:  # noqa: BLE001
            logger.exception("lifespan: error closing LLM provider")


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

# NOTE: the admin router must be included BEFORE the catch-all {agent_id}
# routes if we ever add them under /api/admin/* with conflicting patterns.
# The current admin paths are all unique (/admin/run-normalizer etc.) so
# order with the other routers is irrelevant, but we keep it grouped with
# agents for clarity.
app.include_router(router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(health_router)
app.include_router(logs_router)
app.include_router(alerts_router)
app.include_router(ml_router)
app.include_router(llm_router, prefix="/api")

# Inject no-cache headers into every frontend response (HTML + /assets/*).
class NoCacheFrontendMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/assets") or not path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheFrontendMiddleware)

_frontend_dist = Path(os.getenv("FRONTEND_DIST_DIR", "src/frontend/dist"))
_frontend_index = _frontend_dist / "index.html"
if (_frontend_dist / "assets").is_dir():
    app.mount("/assets", NoCacheStaticFiles(directory=_frontend_dist / "assets"), name="frontend-assets")


# No-cache headers for all frontend files. The dist/ is bind-mounted from the
# host and changes constantly during development; without these headers the
# browser will keep serving stale bundles even after we deploy new ones.
_NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/", response_model=None)
async def root():
    if _frontend_index.is_file():
        return FileResponse(_frontend_index, headers=_NO_CACHE)
    return {"service": settings.app_name, "status": "ok"}


@app.get("/{full_path:path}", include_in_schema=False)
async def frontend_spa(full_path: str) -> FileResponse:
    if not _frontend_index.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    if full_path.startswith(("api/", "health", "ml/")):
        raise HTTPException(status_code=404, detail="Not found")

    requested_file = _frontend_dist / full_path
    if requested_file.is_file():
        return FileResponse(requested_file, headers=_NO_CACHE)
    return FileResponse(_frontend_index, headers=_NO_CACHE)
