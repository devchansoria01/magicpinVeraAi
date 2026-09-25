"""Grounded fact extraction — never invents numbers, prices, or citations."""

from __future__ import annotations

from typing import Any, Optional


def identity(merchant: dict[str, Any]) -> dict[str, Any]:
    return merchant.get("identity") or {}


def perf(merchant: dict[str, Any]) -> dict[str, Any]:
    return merchant.get("performance") or {}


def pct(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if abs(n) <= 1.5:
        n = n * 100
    sign = "+" if n > 0 else ""
    if float(n).is_integer():
        return f"{sign}{int(n)}%"
    return f"{sign}{n:.0f}%"


def num(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    if float(n).is_integer():
        return f"{int(n):,}".replace(",", ",")
    return str(n)


def active_offers(merchant: dict[str, Any]) -> list[dict[str, Any]]:
    offers = merchant.get("offers") or []
    return [o for o in offers if str(o.get("status", "active")).lower() == "active"]


def first_active_offer_title(merchant: dict[str, Any], category: dict[str, Any] | None) -> Optional[str]:
    for o in active_offers(merchant):
        title = o.get("title")
        if title:
            return str(title)
    catalog = (category or {}).get("offer_catalog") or []
    for item in catalog:
        if item.get("type") == "service_at_price" and item.get("title"):
            return str(item["title"])
    if catalog and catalog[0].get("title"):
        return str(catalog[0]["title"])
    return None


def digest_item(category: dict[str, Any] | None, item_id: Optional[str]) -> dict[str, Any]:
    if not category or not item_id:
        return {}
    for item in category.get("digest") or []:
        if item.get("id") == item_id:
            return item
    return {}


def digest_first(category: dict[str, Any] | None) -> dict[str, Any]:
    items = (category or {}).get("digest") or []
    return items[0] if items else {}


def peer(category: dict[str, Any] | None) -> dict[str, Any]:
    return (category or {}).get("peer_stats") or {}


def locality_line(merchant: dict[str, Any]) -> str:
    ident = identity(merchant)
    loc = ident.get("locality") or ""
    city = ident.get("city") or ""
    if loc and city:
        return f"{loc}, {city}"
    return loc or city or ""


def fact_pack(
    category: dict[str, Any] | None,
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None,
) -> dict[str, Any]:
    """Structured facts the composer may quote. Missing keys stay None — never filled with fakes."""
    ident = identity(merchant)
    p = perf(merchant)
    delta = p.get("delta_7d") or {}
    payload = trigger.get("payload") or {}
    agg = merchant.get("customer_aggregate") or {}
    sub = merchant.get("subscription") or {}
    signals = merchant.get("signals") or []
    offer = first_active_offer_title(merchant, category)
    item = digest_item(category, payload.get("top_item_id") or payload.get("digest_item_id") or payload.get("alert_id"))
    if not item:
        item = digest_first(category)
    cust_ident = (customer or {}).get("identity") or {}
    rel = (customer or {}).get("relationship") or {}
    return {
        "biz": ident.get("name"),
        "owner": ident.get("owner_first_name"),
        "locality": ident.get("locality"),
        "city": ident.get("city"),
        "place": locality_line(merchant),
        "verified": ident.get("verified"),
        "views": p.get("views"),
        "calls": p.get("calls"),
        "directions": p.get("directions"),
        "ctr": p.get("ctr"),
        "leads": p.get("leads"),
        "views_pct": delta.get("views_pct"),
        "calls_pct": delta.get("calls_pct"),
        "ctr_pct": delta.get("ctr_pct"),
        "offer": offer,
        "signals": signals,
        "lapsed": agg.get("lapsed_180d_plus") or agg.get("lapsed_90d_plus"),
        "ytd": agg.get("total_unique_ytd"),
        "retention": agg.get("retention_6mo_pct") or agg.get("retention_3mo_pct"),
        "high_risk": agg.get("high_risk_adult_count"),
        "plan": sub.get("plan"),
        "days_remaining": sub.get("days_remaining"),
        "sub_status": sub.get("status"),
        "peer_ctr": peer(category).get("avg_ctr"),
        "peer_calls": peer(category).get("avg_calls_30d"),
        "digest_title": item.get("title"),
        "digest_source": item.get("source"),
        "digest_n": item.get("trial_n"),
        "digest_summary": item.get("summary"),
        "digest_actionable": item.get("actionable"),
        "payload": payload,
        "kind": trigger.get("kind"),
        "urgency": trigger.get("urgency"),
        "customer_name": cust_ident.get("name"),
        "last_visit": rel.get("last_visit"),
        "visits_total": rel.get("visits_total"),
        "services": rel.get("services_received") or [],
        "customer_state": (customer or {}).get("state"),
        "lang_pref": cust_ident.get("language_pref"),
        "fav": rel.get("favourite_dish"),
    }


def grounded_prompt(
    category: dict[str, Any] | None,
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None,
) -> str:
    """Optional LLM prompt — facts only, temperature 0. Not required for the heuristic engine."""
    facts = fact_pack(category, merchant, trigger, customer)
    voice = (category or {}).get("voice") or {}
    return (
        "Compose one WhatsApp message. Use ONLY facts below. Do not invent numbers, "
        "citations, competitor names, or offers.\n"
        f"Voice tone: {voice.get('tone')}\n"
        f"Taboos: {voice.get('vocab_taboo')}\n"
        f"Facts: {facts}\n"
        "Return body + one CTA. Single action. Peer tone, not promo hype."
    )
