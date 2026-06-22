"""Router cho endpoint agent enrollment, heartbeat, config, blocklist, admin CRUD.

Auth model:
- /agents/enrollment-tokens (POST)         -> admin (JWT)
- /agents/register (POST)                  -> public (enrollment token in body)
- /agents/heartbeat (POST)                 -> agent (X-API-Key)
- /agents/me/config (GET)                  -> agent (X-API-Key)
- /agents (GET)                            -> admin (JWT)
- /agents/{agent_id} (GET/PATCH/DELETE)    -> admin (JWT)
- /agents/blocklist (GET/POST)             -> admin (JWT)
- /agents/blocklist/{entry_id} (PATCH/DEL) -> admin (JWT)
- /agents/policy (GET/PATCH)               -> admin (JWT)
- /admin/agents/mark-stale (POST)          -> admin (JWT)
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.backend.app.core.security import (
    require_agent,
)
from src.backend.app.db import agents as agent_db
from src.backend.app.schemas.schemas import (
    AgentConfigResponse,
    AgentEnrollRequest,
    AgentEnrollResponse,
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    AgentPolicyUpdate,
    AgentRead,
    AgentUpdate,
    BlocklistEntryCreate,
    BlocklistEntryRead,
    BlocklistEntryUpdate,
    EnrollmentTokenCreate,
    EnrollmentTokenRead,
    PaginatedResponse,
    Role,
)

router = APIRouter()
_bearer = HTTPBearer()


def _require_role_dep(*roles: Role):
    """Local copy to avoid circular import with routes.py's require_role."""
    from src.backend.app.core.security import decode_access_token
    from src.backend.app.db import session as database

    async def dep(
        credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    ) -> dict[str, Any]:
        payload = decode_access_token(credentials.credentials)
        account = database.get_account_by_id(int(payload["sub"]))
        if not account or not account["is_active"]:
            raise HTTPException(status_code=401, detail="Account is inactive")
        if roles and account["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return account

    return dep


_admin_dep = _require_role_dep("admin")
_admin_or_analyst_dep = _require_role_dep("admin", "security_manager", "analyst")


# ---------------------------------------------------------------------------
# Enrollment tokens (admin issues; agent consumes on register)
# ---------------------------------------------------------------------------


@router.post(
    "/agents/enrollment-tokens",
    response_model=EnrollmentTokenRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_enrollment_token_endpoint(
    payload: EnrollmentTokenCreate,
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    """Issue a one-time enrollment token. Give this to the agent installer.

    The plaintext `token` is only returned once — store it securely.
    """
    result = agent_db.create_enrollment_token(
        created_by_account_id=int(current_account["id"]),
        expires_minutes=payload.expires_minutes,
    )
    return result


# ---------------------------------------------------------------------------
# Agent enrollment (public, uses enrollment token)
# ---------------------------------------------------------------------------


@router.post(
    "/agents/register",
    response_model=AgentEnrollResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_agent_endpoint(payload: AgentEnrollRequest) -> dict[str, Any]:
    """Enroll a new endpoint agent. Returns `agent_id` + plaintext `api_key`.

    The `api_key` is only returned once. Store it at perm 0600 on the agent host.
    """
    try:
        result = agent_db.register_agent(
            enrollment_token=payload.enrollment_token,
            hostname=payload.hostname,
            os=payload.os,
            os_version=payload.os_version,
            device_id=payload.device_id,
            assigned_user_id=payload.assigned_user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


# ---------------------------------------------------------------------------
# Agent self endpoints (X-API-Key auth)
# ---------------------------------------------------------------------------


@router.post("/agents/heartbeat", response_model=AgentHeartbeatResponse)
async def heartbeat_endpoint(
    payload: AgentHeartbeatRequest,
    agent: Annotated[dict, Depends(require_agent)],
) -> dict[str, Any]:
    updated = agent_db.update_agent_heartbeat(agent["agent_id"], payload.metrics)
    if not updated:
        raise HTTPException(status_code=403, detail="Agent is revoked")
    return {
        "status": updated["status"],
        "policy_version": updated["policy_version"],
        "last_heartbeat": updated["last_heartbeat"],
    }


@router.get("/agents/me/config", response_model=AgentConfigResponse)
async def get_my_config_endpoint(
    agent: Annotated[dict, Depends(require_agent)],
) -> dict[str, Any]:
    """Agent pulls blocklist + sampling + enabled collectors on startup + periodically."""
    return agent_db.get_agent_config(agent["agent_id"])


# ---------------------------------------------------------------------------
# Admin agent management (JWT auth)
# ---------------------------------------------------------------------------


def _serialize_agent(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


@router.get("/agents", response_model=PaginatedResponse)
async def list_agents_endpoint(
    current_account: Annotated[dict, Depends(_admin_or_analyst_dep)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    _ = current_account
    items = [_serialize_agent(r) for r in agent_db.list_agents(status_filter, limit, offset)]
    total = agent_db.count_agents(status_filter)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Admin blocklist management (must be declared BEFORE /agents/{agent_id} so
# the static path segments "blocklist" and "policy" are not captured by the
# {agent_id} path parameter).
# ---------------------------------------------------------------------------


@router.get("/agents/blocklist", response_model=list[BlocklistEntryRead])
async def list_blocklist_endpoint(
    current_account: Annotated[dict, Depends(_admin_or_analyst_dep)],
    enabled_only: bool = False,
) -> list[dict[str, Any]]:
    _ = current_account
    return agent_db.list_blocklist(enabled_only=enabled_only)


@router.post(
    "/agents/blocklist",
    response_model=BlocklistEntryRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_blocklist_endpoint(
    payload: BlocklistEntryCreate,
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    _ = current_account
    return agent_db.create_blocklist_entry(
        pattern=payload.pattern,
        pattern_type=payload.pattern_type,
        category=payload.category,
        reason=payload.reason,
        enabled=payload.enabled,
    )


@router.patch("/agents/blocklist/{entry_id}", response_model=BlocklistEntryRead)
async def update_blocklist_endpoint(
    entry_id: int,
    payload: BlocklistEntryUpdate,
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    _ = current_account
    fields = payload.model_dump(exclude_unset=True)
    updated = agent_db.update_blocklist_entry(entry_id, **fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Blocklist entry not found")
    return updated


@router.delete("/agents/blocklist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blocklist_endpoint(
    entry_id: int,
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> None:
    _ = current_account
    if not agent_db.delete_blocklist_entry(entry_id):
        raise HTTPException(status_code=404, detail="Blocklist entry not found")


# ---------------------------------------------------------------------------
# Admin policy management
# ---------------------------------------------------------------------------


@router.get("/agents/policy")
async def get_policy_endpoint(
    current_account: Annotated[dict, Depends(_admin_or_analyst_dep)],
) -> dict[str, Any]:
    _ = current_account
    return agent_db.get_agent_policy()


@router.patch("/agents/policy")
async def update_policy_endpoint(
    payload: AgentPolicyUpdate,
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    _ = current_account
    return agent_db.update_agent_policy(
        sampling_rate=payload.sampling_rate,
        enabled_collectors=payload.enabled_collectors,
    )


# ---------------------------------------------------------------------------
# Admin agent CRUD (dynamic {agent_id} routes come AFTER all static /agents/*
# sub-paths to avoid the path parameter capturing "blocklist" or "policy").
# ---------------------------------------------------------------------------


@router.get("/agents/{agent_id}", response_model=AgentRead)
async def get_agent_endpoint(
    agent_id: str,
    current_account: Annotated[dict, Depends(_admin_or_analyst_dep)],
) -> dict[str, Any]:
    _ = current_account
    agent = agent_db.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.patch("/agents/{agent_id}", response_model=AgentRead)
async def update_agent_endpoint(
    agent_id: str,
    payload: AgentUpdate,
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    _ = current_account
    updated = agent_db.update_agent(
        agent_id,
        status=payload.status,
        device_id=payload.device_id,
        assigned_user_id=payload.assigned_user_id,
        policy_version=payload.policy_version,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Agent not found")
    return updated


@router.delete("/agents/{agent_id}", response_model=AgentRead)
async def revoke_agent_endpoint(
    agent_id: str,
    current_account: Annotated[dict, Depends(_admin_dep)],
) -> dict[str, Any]:
    _ = current_account
    revoked = agent_db.revoke_agent(agent_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="Agent not found")
    return revoked


# ---------------------------------------------------------------------------
# Admin maintenance
# ---------------------------------------------------------------------------


@router.post("/admin/agents/mark-stale")
async def mark_stale_agents_endpoint(
    current_account: Annotated[dict, Depends(_admin_dep)],
    timeout_minutes: int | None = None,
) -> dict[str, Any]:
    _ = current_account
    flipped = agent_db.mark_stale_agents_offline(timeout_minutes)
    return {"flipped_to_offline": flipped}
