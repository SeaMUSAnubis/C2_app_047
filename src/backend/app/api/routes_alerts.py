from fastapi import APIRouter, HTTPException

from src.backend.app.db import session as database

router = APIRouter(tags=["alerts"])


@router.get("/alerts")
async def list_alerts() -> list[dict]:
    try:
        return database.list_alerts(limit=200)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
