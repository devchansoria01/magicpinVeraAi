"""POST /v1/tick — compose proactive actions from active triggers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter

from src.engine.composer import compose
from src.schemas import TickAction, TickRequest, TickResponse
from src.store import store

router = APIRouter()

MAX_ACTIONS = 20


def _parse_now(raw: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _expired(trigger: dict[str, Any], now: Optional[datetime]) -> bool:
    exp = trigger.get("expires_at")
    if not exp or now is None:
        return False
    try:
        exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        n = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        return n > exp_dt
    except Exception:
        return False


def _resolve_merchant_id(trigger: dict[str, Any]) -> Optional[str]:
    return trigger.get("merchant_id") or (trigger.get("payload") or {}).get("merchant_id")


def _resolve_customer_id(trigger: dict[str, Any]) -> Optional[str]:
    cid = trigger.get("customer_id") or (trigger.get("payload") or {}).get("customer_id")
    return cid


@router.post("/v1/tick", response_model=TickResponse)
async def tick(body: TickRequest) -> TickResponse:
    now = _parse_now(body.now)
    candidates: list[tuple[int, str, dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]] = []

    for trg_id in body.available_triggers:
        trigger = store.get("trigger", trg_id)
        if not trigger:
            continue
        if _expired(trigger, now):
            continue
        sk = str(trigger.get("suppression_key") or "")
        if store.is_suppressed(sk):
            continue
        mid = _resolve_merchant_id(trigger)
        if not mid:
            continue
        merchant = store.get("merchant", mid)
        if not merchant:
            continue
        slug = merchant.get("category_slug") or (trigger.get("payload") or {}).get("category")
        category = store.get("category", slug) if slug else None
        cid = _resolve_customer_id(trigger)
        customer = store.get("customer", cid) if cid else None
        urgency = int(trigger.get("urgency") or 0)
        candidates.append((urgency, trg_id, trigger, merchant, category, customer))

    # Highest urgency first; one action per merchant per tick.
    candidates.sort(key=lambda x: (-x[0], x[1]))
    seen_merchants: set[str] = set()
    actions: list[TickAction] = []

    for urgency, trg_id, trigger, merchant, category, customer in candidates:
        mid = merchant.get("merchant_id") or _resolve_merchant_id(trigger)
        if mid in seen_merchants:
            continue
        composed = compose(category, merchant, trigger, customer)
        conv_id = f"conv_{mid}_{trg_id}"
        cid = _resolve_customer_id(trigger)
        action = TickAction(
            conversation_id=conv_id,
            merchant_id=mid,
            customer_id=cid,
            send_as=composed["send_as"],
            trigger_id=trg_id,
            template_name=composed.get("template_name") or "vera_grounded_v1",
            template_params=composed.get("template_params") or [],
            body=composed["body"],
            cta=composed["cta"],
            suppression_key=composed["suppression_key"],
            rationale=composed["rationale"],
        )
        store.mark_suppression(action.suppression_key)
        store.put_conversation(
            conv_id,
            {
                "merchant_id": mid,
                "customer_id": cid,
                "trigger_id": trg_id,
                "turns": [],
                "sent_bodies": [action.body],
                "inbound": [],
                "auto_reply_streak": 0,
                "mode": "pitch",
            },
        )
        actions.append(action)
        seen_merchants.add(mid)
        if len(actions) >= MAX_ACTIONS:
            break

    return TickResponse(actions=actions)
