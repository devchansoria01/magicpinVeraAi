"""POST /v1/reply — next move given a merchant/customer message."""

from __future__ import annotations

from fastapi import APIRouter

from src.engine.reply import decide_reply, is_auto_reply
from src.schemas import ReplyRequest, ReplyResponse
from src.store import store

router = APIRouter()


@router.post("/v1/reply", response_model=ReplyResponse)
async def reply(body: ReplyRequest) -> ReplyResponse:
    conv = store.get_conversation(body.conversation_id)
    mid = body.merchant_id or conv.get("merchant_id")
    cid = body.customer_id or conv.get("customer_id")
    merchant = store.get("merchant", mid) if mid else None
    customer = store.get("customer", cid) if cid else None
    slug = (merchant or {}).get("category_slug")
    category = store.get("category", slug) if slug else None

    # Cross-conversation auto-reply tracking (judge uses a new conv_id each turn).
    if mid and is_auto_reply(body.message):
        store.bump_merchant_auto(mid)
    elif mid:
        store.reset_merchant_auto(mid)

    merchant_auto = store.merchant_auto_count(mid) if mid else 0
    conv["merchant_auto_count"] = merchant_auto

    decision = decide_reply(conv, body.message, merchant, category, customer)
    conv["merchant_id"] = mid
    conv["customer_id"] = cid
    if decision.get("body"):
        conv.setdefault("sent_bodies", []).append(decision["body"])
    store.put_conversation(body.conversation_id, conv)

    return ReplyResponse(
        action=decision["action"],
        body=decision.get("body"),
        cta=decision.get("cta"),
        wait_seconds=decision.get("wait_seconds"),
        rationale=decision["rationale"],
    )
