"""POST /v1/context — versioned, idempotent context upsert."""

from __future__ import annotations

from fastapi import APIRouter

from src.schemas import ContextAccepted, ContextRejected, ContextRequest
from src.store import VALID_SCOPES, store

router = APIRouter()


@router.post("/v1/context", response_model=None)
async def push_context(body: ContextRequest):
    if body.scope not in VALID_SCOPES:
        return ContextRejected(reason="invalid_scope", details=f"scope must be one of {sorted(VALID_SCOPES)}")
    result = store.upsert(body.scope, body.context_id, body.version, body.payload, body.delivered_at)
    if not result.get("accepted"):
        return ContextRejected(
            reason=result.get("reason", "rejected"),
            current_version=result.get("current_version"),
        )
    return ContextAccepted(ack_id=result["ack_id"], stored_at=result["stored_at"])
