"""Multi-turn reply policy: auto-reply, hostility, intent handoff, wait."""

from __future__ import annotations

import re
from typing import Any

from src.engine.category_rules import greet_name, slug_of, wants_code_mix
from src.engine.prompt_builder import first_active_offer_title, identity

AUTO_PATTERNS = [
    r"thank you for contacting",
    r"our team will respond",
    r"we will get back",
    r"automated assistant",
    r"this is an auto",
    r"out of office",
    r"aapki jaankari ke liye",
    r"hamari team tak pahuncha",
    r"main ek automated",
]

HOSTILE_PATTERNS = [
    r"\bstop\b",
    r"unsubscribe",
    r"don't (text|message|spam)",
    r"do not (text|message)",
    r"useless spam",
    r"this is spam",
    r"leave me alone",
    r" bakwas",
    r"band kar",
]

COMMIT_PATTERNS = [
    r"\blet'?s do it\b",
    r"\bgo ahead\b",
    r"\bproceed\b",
    r"\bwhats? next\b",
    r"what's next",
    r"\bok lets\b",
    r"\bok,?\s*let",
    r"\bi want to join\b",
    r"mujhe .{0,20}jud",
    r"\byes,?\s*send\b",
    r"\bsend me\b",
    r"\bdo it\b",
    r"\bconfirm\b",
    r"\bgo for it\b",
    r"\bstart\b",
]

WAIT_PATTERNS = [
    r"\blater\b",
    r"\bbusy\b",
    r"\btomorrow\b",
    r"\bnot now\b",
    r"\bafter (an? )?(hour|meeting)\b",
    r"kal baat",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_auto_reply(text: str) -> bool:
    n = _norm(text)
    return any(re.search(p, n) for p in AUTO_PATTERNS)


def is_hostile(text: str) -> bool:
    n = _norm(text)
    return any(re.search(p, n) for p in HOSTILE_PATTERNS)


def is_commit(text: str) -> bool:
    n = _norm(text)
    if n in {"yes", "y", "ok", "okay", "haan", "ha", "sure"}:
        return True
    return any(re.search(p, n) for p in COMMIT_PATTERNS)


def is_wait(text: str) -> bool:
    n = _norm(text)
    return any(re.search(p, n) for p in WAIT_PATTERNS)


def decide_reply(
    conv: dict[str, Any],
    message: str,
    merchant: dict[str, Any] | None,
    category: dict[str, Any] | None,
    customer: dict[str, Any] | None,
) -> dict[str, Any]:
    inbound = conv.setdefault("inbound", [])
    sent = conv.setdefault("sent_bodies", [])
    n = _norm(message)

    if inbound and _norm(inbound[-1]) == n and n:
        conv["auto_reply_streak"] = conv.get("auto_reply_streak", 0) + 1
    elif is_auto_reply(message):
        conv["auto_reply_streak"] = conv.get("auto_reply_streak", 0) + 1
    else:
        conv["auto_reply_streak"] = 0

    inbound.append(message)
    slug = slug_of(category, merchant or {})
    who = greet_name(merchant or {"identity": {}}, slug) if merchant else "there"
    mix = wants_code_mix(merchant, customer)
    offer = first_active_offer_title(merchant or {}, category) if merchant else None
    ident = identity(merchant or {})
    biz = ident.get("name") or "your listing"

    if is_hostile(message):
        conv["mode"] = "end"
        body = (
            f"Samajh gayi, {who}. I won't message again. Best of luck with {biz}."
            if mix
            else f"Understood, {who}. I will stop messaging. Wishing {biz} well."
        )
        return {"action": "end", "body": body, "rationale": "Hostile / opt-out — graceful exit."}

    streak = max(conv.get("auto_reply_streak", 0), int(conv.get("merchant_auto_count") or 0))
    if is_auto_reply(message) or (streak >= 1 and inbound.count(message) >= 2):
        if streak >= 2:
            conv["mode"] = "end"
            return {
                "action": "end",
                "rationale": "Repeated WhatsApp Business auto-reply — stop wasting turns.",
            }
        probe = (
            f"{who}, yeh auto-reply lag raha hai. Agar aap khud ho, reply YES — warna main owner ko later ping karungi."
            if mix
            else f"{who}, this looks like a business auto-reply. If this is you, reply YES. Otherwise I'll try the owner later."
        )
        if probe in sent:
            return {"action": "end", "rationale": "Already probed auto-reply once — exit."}
        return {
            "action": "send",
            "body": probe,
            "cta": "Reply YES if this is the owner",
            "rationale": "First auto-reply: one probe, then stop.",
        }

    if is_wait(message) and not is_commit(message):
        return {
            "action": "wait",
            "wait_seconds": 1800,
            "rationale": "Merchant asked for time — back off 30 min.",
        }

    if is_commit(message) or conv.get("mode") == "action":
        conv["mode"] = "action"
        offer_bit = f" Using {offer}." if offer else ""
        body = (
            f"Done — moving to action, not more qualifying.{offer_bit} "
            "Draft is ready: I'll send the GBP post + WhatsApp copy next. Confirm and I publish."
        )
        if body in sent:
            body = (
                f"Publishing next: one GBP post for {biz}.{offer_bit} "
                "No extra questions. Reply STOP only if you want me to halt."
            )
        return {
            "action": "send",
            "body": body,
            "cta": "Reply YES to publish",
            "rationale": "Explicit commitment — action mode, no re-qualification.",
        }

    # Default: advance with one next step, never re-pitch the same body.
    loc = ident.get("locality") or ident.get("city") or ""
    offer_bit = f" {offer}." if offer else ""
    body = (
        f"{who}, got it. Next single step for {loc}:{offer_bit} "
        "I draft, you tap YES. No extra options."
    )
    if body in sent:
        body = (
            f"{who}, still here if useful — one question only: should I proceed with the draft for {biz}?"
        )
    return {
        "action": "send",
        "body": body,
        "cta": "Reply YES to proceed",
        "rationale": "Continue conversation with a single next action.",
    }
