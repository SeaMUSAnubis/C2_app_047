from fastapi import APIRouter, HTTPException, status

from src.backend.app.db import session as database
from src.backend.app.schemas.schemas import EventIngest, EventRead

router = APIRouter(tags=["logs"])


@router.post("/logs", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def create_log(payload: EventIngest) -> dict:
    try:
        return database.ingest_event(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
