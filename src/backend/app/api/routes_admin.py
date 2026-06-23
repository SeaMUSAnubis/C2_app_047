"""Admin endpoints for the Phase 3 normalizer + ML scoring worker.

Auth: admin role only (JWT bearer).

Endpoints:
- POST /api/admin/run-normalizer          → triggers one normalizer tick synchronously
- GET  /api/admin/normalizer-stats        → snapshot of normalizer stats + pending count
- POST /api/admin/score-user/{user_id}    → triggers score_user for a single user
- GET  /api/admin/scoring-stats           → snapshot of user_scoring stats
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.backend.app.db import session as database
from src.backend.app.services.normalizer import get_normalizer
from src.backend.app.services.user_scoring import get_user_scoring

router = APIRouter()
_bearer = HTTPBearer()


def _require_admin_dep():
    from src.backend.app.core.security import decode_access_token

    async def dep(
        credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    ) -> dict[str, Any]:
        payload = decode_access_token(credentials.credentials)
        account = database.get_account_by_id(int(payload["sub"]))
        if not account or not account["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Account is inactive"
            )
        if account["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
            )
        return account

    return dep


_admin_dep = _require_admin_dep()


@router.post("/admin/run-normalizer")
async def run_normalizer_endpoint(
    current_account: Annotated[dict, Depends(_admin_dep)],
    batch_size: int | None = None,
    trigger_scoring: bool = True,
) -> dict[str, Any]:
    """Manually trigger one normalizer tick.

    `trigger_scoring=True` (default) will also call `score_user` for each
    user with new events in this tick. Set to False to only normalise raw
    logs (e.g. for backfill scenarios).
    """
    _ = current_account
    normalizer = get_normalizer()

    if not trigger_scoring:

        def _noop(_uid: str) -> None:
            return None

        result = normalizer.run_once(batch_size=batch_size, on_user_scored=_noop)
    else:
        user_scoring = get_user_scoring()

        def _score(uid: str) -> None:
            try:
                user_scoring.score_user(uid)
            except Exception:
                # Already logged in score_user; keep going for other users.
                pass

        result = normalizer.run_once(batch_size=batch_size, on_user_scored=_score)
    return result


@router.get("/admin/normalizer-stats")
async def normalizer_stats_endpoint(
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    _ = current_account
    normalizer = get_normalizer()
    stats = normalizer.get_stats()
    # Also include live pending count (stats.last_pending is from the last run).
    try:
        stats["pending_now"] = database.count_pending_raw_logs()
    except Exception:
        stats["pending_now"] = None
    return stats


@router.post("/admin/score-user/{user_id}")
async def score_user_endpoint(
    user_id: str,
    current_account: Annotated[dict, Depends(_admin_dep)],
    lookback_minutes: int | None = None,
) -> dict[str, Any]:
    _ = current_account
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    user = database.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    user_scoring = get_user_scoring()
    result = user_scoring.score_user(user_id, lookback_minutes=lookback_minutes)
    return result


@router.get("/admin/scoring-stats")
async def scoring_stats_endpoint(
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    _ = current_account
    user_scoring = get_user_scoring()
    return user_scoring.get_stats()
