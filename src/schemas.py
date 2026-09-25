"""Pydantic request/response models for /v1 endpoints."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


Scope = Literal["category", "merchant", "customer", "trigger"]


class ContextRequest(BaseModel):
    scope: Scope
    context_id: str
    version: int = Field(..., ge=0)
    payload: dict[str, Any]
    delivered_at: Optional[str] = None


class ContextAccepted(BaseModel):
    accepted: bool = True
    ack_id: str
    stored_at: str


class ContextRejected(BaseModel):
    accepted: bool = False
    reason: str
    current_version: Optional[int] = None
    details: Optional[str] = None


class TickRequest(BaseModel):
    now: str
    available_triggers: list[str] = Field(default_factory=list)


class TickAction(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    send_as: str
    trigger_id: Optional[str] = None
    template_name: str = "vera_grounded_v1"
    template_params: list[str] = Field(default_factory=list)
    body: str
    cta: str
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: list[TickAction]


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: Optional[str] = None
    turn_number: int = 1


class ReplyResponse(BaseModel):
    action: Literal["send", "wait", "end"]
    body: Optional[str] = None
    cta: Optional[str] = None
    wait_seconds: Optional[int] = None
    rationale: str
