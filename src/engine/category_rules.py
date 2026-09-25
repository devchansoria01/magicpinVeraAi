"""Category voice, taboos, and offer-format guardrails."""

from __future__ import annotations

from typing import Any

DETERMINISTIC_SEED = 42

VOICE: dict[str, dict[str, Any]] = {
    "dentists": {
        "tone": "peer_clinical",
        "salute": "Dr.",
        "avoid": ("guaranteed", "miracle", "100% safe", "completely cure", "best in city"),
        "cta_style": "binary_yes",
    },
    "salons": {
        "tone": "warm_practical",
        "salute": "Hi",
        "avoid": ("guaranteed glow", "permanent results", "instant transformation", "miracle", "best in city"),
        "cta_style": "binary_yes",
    },
    "restaurants": {
        "tone": "operator_to_operator",
        "salute": "Hi",
        "avoid": ("best food in city", "guaranteed packed house", "miracle marketing", "viral guarantee"),
        "cta_style": "binary_yes",
    },
    "gyms": {
        "tone": "coach_motivational",
        "salute": "Hi",
        "avoid": ("guaranteed weight loss", "shred in 7 days", "miracle transformation", "fastest results"),
        "cta_style": "binary_yes",
    },
    "pharmacies": {
        "tone": "trustworthy_precise",
        "salute": "Hi",
        "avoid": ("miracle cure", "guaranteed result", "100% safe"),
        "cta_style": "binary_yes",
    },
}


def slug_of(category: dict[str, Any] | None, merchant: dict[str, Any] | None) -> str:
    if merchant and merchant.get("category_slug"):
        return str(merchant["category_slug"])
    if category and category.get("slug"):
        return str(category["slug"])
    return "unknown"


def rules_for(slug: str) -> dict[str, Any]:
    return VOICE.get(slug, VOICE["restaurants"])


def wants_code_mix(merchant: dict[str, Any] | None, customer: dict[str, Any] | None) -> bool:
    if customer:
        pref = str((customer.get("identity") or {}).get("language_pref") or "").lower()
        if "hi" in pref or "mix" in pref or "te" in pref or "kn" in pref or "mr" in pref:
            return True
    langs = (merchant or {}).get("identity", {}).get("languages") or []
    return any(str(x).lower() in {"hi", "te", "kn", "mr", "ta"} for x in langs)


def strip_taboos(text: str, slug: str) -> str:
    out = text
    for bad in rules_for(slug).get("avoid", ()):
        # Never invent replacements — drop the banned phrase if a model/template slipped it in.
        out = out.replace(bad, "")
        out = out.replace(bad.title(), "")
        out = out.replace(bad.upper(), "")
    return " ".join(out.split())


def greet_name(merchant: dict[str, Any], slug: str) -> str:
    ident = merchant.get("identity") or {}
    first = ident.get("owner_first_name") or ""
    biz = ident.get("name") or "there"
    if slug == "dentists" and first:
        if str(first).lower().startswith("dr"):
            return first
        return f"Dr. {first}"
    return first or biz
