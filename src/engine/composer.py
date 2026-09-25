"""Deterministic compose(category, merchant, trigger, customer?) pipeline."""

from __future__ import annotations

from typing import Any, Optional

from src.engine.category_rules import (
    DETERMINISTIC_SEED,
    greet_name,
    slug_of,
    strip_taboos,
    wants_code_mix,
)
from src.engine.prompt_builder import (
    digest_item,
    fact_pack,
    first_active_offer_title,
    num,
    pct,
    peer,
)

_ = DETERMINISTIC_SEED  # fixed seed contract; composer is heuristic (no RNG)


def _cta_yes(action: str) -> str:
    return f"Reply YES to {action}"


def _cta_open() -> str:
    return "open_ended"


def _send_as(trigger: dict[str, Any], customer: dict[str, Any] | None) -> str:
    if customer and str(trigger.get("scope")) == "customer":
        return "merchant_on_behalf"
    if customer and trigger.get("customer_id"):
        return "merchant_on_behalf"
    return "vera"


def _suppression(trigger: dict[str, Any], merchant: dict[str, Any]) -> str:
    return str(trigger.get("suppression_key") or f"{trigger.get('kind')}:{merchant.get('merchant_id')}")


def _template_params(*parts: Any) -> list[str]:
    out: list[str] = []
    for p in parts:
        if p is None:
            continue
        s = str(p).strip()
        if s:
            out.append(s)
    return out[:5]


def compose(
    category: dict[str, Any] | None,
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slug = slug_of(category, merchant)
    mix = wants_code_mix(merchant, customer)
    who = greet_name(merchant, slug)
    facts = fact_pack(category, merchant, trigger, customer)
    kind = str(trigger.get("kind") or "generic")
    payload = trigger.get("payload") or {}
    body, cta, rationale, template = _dispatch(
        kind, slug, mix, who, facts, category, merchant, trigger, customer, payload
    )
    body = strip_taboos(body, slug)
    send_as = _send_as(trigger, customer)
    return {
        "body": body,
        "cta": cta,
        "send_as": send_as,
        "suppression_key": _suppression(trigger, merchant),
        "rationale": rationale,
        "template_name": template,
        "template_params": _template_params(who, facts.get("place"), facts.get("offer"), kind),
    }


def _dispatch(
    kind: str,
    slug: str,
    mix: bool,
    who: str,
    facts: dict[str, Any],
    category: dict[str, Any] | None,
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: dict[str, Any] | None,
    payload: dict[str, Any],
) -> tuple[str, str, str, str]:
    handlers = {
        "research_digest": _research,
        "regulation_change": _regulation,
        "recall_due": _recall,
        "perf_dip": _perf_dip,
        "renewal_due": _renewal,
        "festival_upcoming": _festival,
        "wedding_package_followup": _bridal,
        "curious_ask_due": _curious,
        "winback_eligible": _winback,
        "ipl_match_today": _ipl,
        "review_theme_emerged": _review_theme,
        "milestone_reached": _milestone,
        "active_planning_intent": _planning,
        "seasonal_perf_dip": _seasonal_dip,
        "customer_lapsed_hard": _lapsed_customer,
        "customer_lapsed_soft": _lapsed_customer,
        "trial_followup": _trial,
        "supply_alert": _supply,
        "chronic_refill_due": _refill,
        "category_seasonal": _cat_seasonal,
        "gbp_unverified": _unverified,
        "cde_opportunity": _cde,
        "competitor_opened": _competitor,
        "perf_spike": _perf_spike,
        "dormant_with_vera": _dormant,
        "appointment_tomorrow": _appt,
    }
    fn = handlers.get(kind, _generic)
    return fn(slug, mix, who, facts, category, merchant, trigger, customer, payload)


def _research(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    item = digest_item(category, payload.get("top_item_id")) or {}
    title = item.get("title") or facts.get("digest_title")
    source = item.get("source") or facts.get("digest_source")
    n = item.get("trial_n") or facts.get("digest_n")
    summary = item.get("summary") or facts.get("digest_summary") or ""
    cohort = ""
    if facts.get("high_risk"):
        cohort = f" Relevant to your {num(facts['high_risk'])} high-risk adult patients."
    n_bit = f" {num(n)}-patient trial." if n else ""
    cite = f" — {source}" if source else ""
    hook = title or "New category digest item landed."
    if mix:
        body = (
            f"{who}, digest drop: {hook}.{n_bit}{cohort} "
            f"{summary[:180] if summary else ''}{cite} "
            "2-min abstract. Want me to pull it + draft a patient WhatsApp you can share?"
        )
    else:
        body = (
            f"{who}, a category digest item landed: {hook}.{n_bit}{cohort} "
            f"{summary[:180] if summary else ''}{cite} "
            "Worth a 2-min look. Want me to pull the abstract and draft a patient-ed note?"
        )
    return body.strip(), _cta_yes("pull the abstract + draft"), "Research digest grounded in category digest + merchant cohort.", "vera_research_digest_v1"


def _regulation(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    item = digest_item(category, payload.get("top_item_id")) or {}
    deadline = payload.get("deadline_iso") or item.get("date")
    title = item.get("title") or "Regulation update in your category"
    source = item.get("source") or ""
    action = item.get("actionable") or "Audit your setup against the circular."
    dl = f" Deadline: {deadline}." if deadline else ""
    body = (
        f"{who}, compliance ping — {title}.{dl} Source: {source}. {action} "
        "Want a 5-line SOP checklist for the clinic?"
        if slug == "dentists"
        else f"{who}, regulation change: {title}.{dl} {action} Want a one-page checklist?"
    )
    return body, _cta_yes("send the SOP checklist"), "Regulation trigger cites digest source and deadline only.", "vera_compliance_v1"


def _recall(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    name = facts.get("customer_name") or "there"
    last = payload.get("last_service_date") or facts.get("last_visit")
    due = payload.get("due_date")
    slots = payload.get("available_slots") or []
    slot_txt = ""
    if slots:
        labels = [s.get("label") for s in slots if s.get("label")]
        slot_txt = " Slots: " + " / ".join(labels[:2]) + "."
    offer = facts.get("offer")
    offer_bit = f" {offer}." if offer else ""
    biz = facts.get("biz") or "the clinic"
    if mix:
        body = (
            f"Hi {name}, {biz} here. Last visit {last}."
            f"{' 6-month recall due ' + due + '.' if due else ' Recall window is open.'}"
            f"{slot_txt}{offer_bit} Reply 1 for the first slot, or tell us a time that works."
        )
        cta = "Reply 1 to book the first slot"
    else:
        body = (
            f"Hi {name}, {biz} here. Last visit {last}."
            f"{' Recall due ' + due + '.' if due else ' Your recall window is open.'}"
            f"{slot_txt}{offer_bit} Reply YES to hold a slot."
        )
        cta = _cta_yes("hold a slot")
    return body, cta, "Customer recall uses last visit, due date, slots, and catalog offer only.", "vera_recall_v1"


def _perf_dip(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    metric = payload.get("metric") or "calls"
    delta = payload.get("delta_pct")
    if delta is None:
        delta = facts.get("calls_pct") if metric == "calls" else facts.get("views_pct")
    window = payload.get("window") or "7d"
    baseline = payload.get("vs_baseline")
    calls = facts.get("calls")
    views = facts.get("views")
    peer_ctr = facts.get("peer_ctr")
    offer = facts.get("offer")
    place = facts.get("place")
    extra = ""
    if metric == "calls" and calls is not None:
        extra = f" 30d calls now {num(calls)}."
    if metric == "views" and views is not None:
        extra = f" 30d views now {num(views)}."
    base = f" vs your baseline {num(baseline)}." if baseline is not None else ""
    peer_bit = ""
    if peer_ctr is not None and facts.get("ctr") is not None:
        peer_bit = f" Your CTR {facts['ctr']} vs peer {peer_ctr}."
    offer_bit = f" Fastest lever: push {offer} on GBP." if offer else " Fastest lever: a service+price post on GBP."
    body = (
        f"{who}, {place}: {metric} {pct(delta)} in {window}.{extra}{base}{peer_bit}"
        f"{offer_bit} Want me to draft the post (you just approve)?"
    )
    return body, _cta_yes("draft the GBP post"), "Perf dip uses trigger delta + merchant snapshot + peer CTR.", "vera_perf_dip_v1"


def _renewal(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    days = payload.get("days_remaining")
    if days is None:
        days = facts.get("days_remaining")
    plan = payload.get("plan") or facts.get("plan")
    amount = payload.get("renewal_amount")
    amt = f" ₹{num(amount)}" if amount else ""
    dip = facts.get("calls_pct")
    dip_bit = f" Calls already {pct(dip)} this week — listing maintenance pauses if Pro lapses." if dip is not None else ""
    body = (
        f"{who}, {plan or 'Pro'} has {days} days left.{amt}.{dip_bit} "
        "I can keep posts + offer live if we renew this week. Want the 1-tap renewal link?"
    )
    return body, _cta_yes("send the renewal link"), "Renewal uses days remaining, plan, amount, and live dip if present.", "vera_renewal_v1"


def _festival(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    fest = payload.get("festival") or "the festival"
    date = payload.get("date")
    days = payload.get("days_until")
    offer = facts.get("offer")
    place = facts.get("locality") or facts.get("city")
    when = f" {date}" if date else ""
    until = f" ({days} days)" if days is not None else ""
    offer_bit = f" Lead with {offer}." if offer else " Lead with a service+price, not a vague % off."
    body = (
        f"{who}, {fest}{when}{until} — {place} usually books out early. {offer_bit} "
        "Want a 3-post GBP pack you can approve in one reply?"
    )
    return body, _cta_yes("draft the 3-post pack"), "Festival uses date/days from trigger and merchant offer.", "vera_festival_v1"


def _bridal(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    name = facts.get("customer_name") or "there"
    wdate = payload.get("wedding_date") or ((customer or {}).get("preferences") or {}).get("wedding_date")
    trial = payload.get("trial_completed")
    days = payload.get("days_to_wedding")
    biz = facts.get("biz")
    nxt = payload.get("next_step_window_open")
    body = (
        f"Hi {name}, {biz} here. Bridal trial {trial}. Wedding {wdate}"
        f"{' — ' + str(days) + ' days out' if days is not None else ''}. "
        f"Next window: {nxt or 'skin/hair prep'}. Reply YES to lock a prep slot."
    )
    return body, _cta_yes("lock a prep slot"), "Bridal follow-up uses wedding date, trial date, and next-step window.", "vera_bridal_v1"


def _curious(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    ask = payload.get("ask_template") or "what_service_in_demand_this_week"
    calls = facts.get("calls")
    views = facts.get("views")
    loc = facts.get("locality")
    stat = ""
    if calls is not None and views is not None:
        stat = f" This month: {num(views)} views, {num(calls)} calls in {loc}."
    body = (
        f"{who}, quick curiosity — not a pitch.{stat} "
        f"What's the one service walking in most this week in {loc}? "
        "I'll map it against your GBP posts."
    )
    return body, _cta_open(), "Curious-ask uses merchant locality + live views/calls; no fake demand number.", "vera_curious_v1"


def _winback(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    days = payload.get("days_since_expiry") or ((merchant.get("subscription") or {}).get("days_since_expiry"))
    dip = payload.get("perf_dip_pct")
    lapsed = payload.get("lapsed_customers_added_since_expiry")
    bits = []
    if days is not None:
        bits.append(f"Pro paused {days} days")
    if dip is not None:
        bits.append(f"calls {pct(dip)}")
    if lapsed is not None:
        bits.append(f"{num(lapsed)} extra lapsed customers since pause")
    proof = "; ".join(bits) if bits else f"{facts.get('biz')} listing is paused"
    body = (
        f"{who}, not nagging — {proof}. Restarting posts is a 2-min tap, not a sales call. "
        "Want a 7-day restart plan with one GBP post?"
    )
    return body, _cta_yes("send the 7-day restart plan"), "Winback uses expiry, dip, and lapsed counts from the trigger.", "vera_winback_v1"


def _ipl(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    match = payload.get("match")
    venue = payload.get("venue")
    time = payload.get("match_time_iso")
    offer = facts.get("offer")
    offer_bit = f" You already have {offer} live." if offer else ""
    body = (
        f"{who}, {match} tonight at {venue} ({time}). Weeknight/weekend mix is in the trigger. "
        f"{offer_bit} Want a match-night WhatsApp + GBP post (food+timing only, no fake crowd claims)?"
    )
    return body, _cta_yes("draft the match-night post"), "IPL uses match, venue, time, and active offer only.", "vera_ipl_v1"


def _review_theme(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    theme = payload.get("theme")
    n = payload.get("occurrences_30d")
    quote = payload.get("common_quote")
    trend = payload.get("trend")
    q = f' Quote: "{quote}".' if quote else ""
    body = (
        f"{who}, review pattern: '{theme}' showed up {num(n)} times in 30d ({trend}).{q} "
        "I can draft a one-line GBP reply + an ops note. Want the draft?"
    )
    return body, _cta_yes("send the reply draft"), "Review theme uses occurrence count and the merchant's own quote.", "vera_review_theme_v1"


def _milestone(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    metric = payload.get("metric")
    now = payload.get("value_now")
    goal = payload.get("milestone_value")
    body = (
        f"{who}, {metric} is at {num(now)} — {num(goal)} is close. "
        "A short 'thank you + one photo' post usually converts the last few reviews. Draft it?"
    )
    return body, _cta_yes("draft the thank-you post"), "Milestone uses value_now and milestone_value from trigger.", "vera_milestone_v1"


def _planning(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    topic = payload.get("intent_topic")
    last = payload.get("merchant_last_message")
    offer = facts.get("offer")
    offer_bit = f" Anchor on {offer}." if offer else ""
    body = (
        f"{who}, you said: \"{last}\". Switching to action on {topic}. "
        f"{offer_bit} I'll send a 1-page package (price, covers, SLA) — you edit numbers, I publish. Ready?"
    )
    return body, _cta_yes("send the 1-page package"), "Planning honors merchant intent and does not re-qualify.", "vera_planning_v1"


def _seasonal_dip(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    delta = payload.get("delta_pct")
    note = payload.get("season_note")
    metric = payload.get("metric") or "views"
    offer = facts.get("offer") or first_active_offer_title(merchant, category)
    offer_bit = f" Counter with {offer} on weekday evenings." if offer else ""
    body = (
        f"{who}, {metric} {pct(delta)} this week — expected seasonal ({note}), not a listing failure. "
        f"{offer_bit} Want a May recovery calendar (4 posts)?"
    )
    return body, _cta_yes("send the May calendar"), "Seasonal dip names the season note and real delta; no panic copy.", "vera_seasonal_dip_v1"


def _lapsed_customer(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    name = facts.get("customer_name") or "there"
    days = payload.get("days_since_last_visit")
    focus = payload.get("previous_focus")
    biz = facts.get("biz")
    offer = facts.get("offer")
    offer_bit = f" {offer} is live if useful." if offer else ""
    body = (
        f"Hi {name}, {biz} here. It's been {num(days)} days"
        f"{' since your ' + focus + ' block' if focus else ''}.{offer_bit} "
        "Reply YES if you want a restart slot this week."
    )
    return body, _cta_yes("hold a restart slot"), "Lapsed customer uses days since visit and prior focus only.", "vera_lapsed_cx_v1"


def _trial(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    name = facts.get("customer_name") or "there"
    trial = payload.get("trial_date")
    opts = payload.get("next_session_options") or []
    label = opts[0].get("label") if opts else None
    biz = facts.get("biz")
    slot = f" Next: {label}." if label else ""
    body = (
        f"Hi {name}, {biz} here. Trial on {trial}.{slot} "
        "Reply YES to book that slot (or send another time)."
    )
    return body, _cta_yes("book the listed slot"), "Trial follow-up uses trial date and listed session option.", "vera_trial_v1"


def _supply(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    mol = payload.get("molecule")
    batches = payload.get("affected_batches") or []
    mfr = payload.get("manufacturer")
    alert = payload.get("alert_id")
    batch_txt = ", ".join(str(b) for b in batches[:4])
    body = (
        f"{who}, supply alert {alert}: {mol} batches {batch_txt} ({mfr}). "
        "Check shelf + stop dispensing those lots. Want a customer SMS template for anyone recently sold these batches?"
    )
    return body, _cta_yes("send the customer SMS template"), "Supply alert quotes molecule, batches, manufacturer from trigger.", "vera_supply_v1"


def _refill(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    name = facts.get("customer_name") or "there"
    mols = payload.get("molecule_list") or []
    last = payload.get("last_refill")
    out = payload.get("stock_runs_out_iso")
    biz = facts.get("biz")
    mol_txt = ", ".join(str(m) for m in mols)
    body = (
        f"Hi {name}, {biz} here. Refill for {mol_txt}. Last refill {last}; stock-out around {out}. "
        "Home delivery is on your saved address if you still want it. Reply YES to dispatch."
    )
    return body, _cta_yes("dispatch the refill"), "Chronic refill uses molecule list, last refill, stock-out timestamp.", "vera_refill_v1"


def _cat_seasonal(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    season = payload.get("season")
    trends = payload.get("trends") or []
    t = "; ".join(str(x) for x in trends[:4])
    body = (
        f"{who}, {season} shelf signal: {t}. "
        "Want a 6-line planogram note (what to front-face this week)?"
    )
    return body, _cta_yes("send the planogram note"), "Seasonal category uses listed trend strings only.", "vera_cat_seasonal_v1"


def _unverified(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    path = payload.get("verification_path")
    uplift = payload.get("estimated_uplift_pct")
    views = facts.get("views")
    view_bit = f" You already get {num(views)} views/30d unverified." if views is not None else ""
    up = f" Similar listings see ~{pct(uplift)} more actions after verify." if uplift is not None else ""
    body = (
        f"{who}, GBP still unverified ({path}).{view_bit}{up} "
        "I can start the postcard/phone flow and tell you exactly what to tap. Shall I?"
    )
    return body, _cta_yes("start verification"), "Unverified GBP uses path, estimated uplift, and merchant views.", "vera_gbp_v1"


def _cde(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    item = digest_item(category, payload.get("digest_item_id")) or {}
    title = item.get("title") or "CDE session"
    date = item.get("date")
    credits = payload.get("credits") or item.get("credits")
    fee = payload.get("fee")
    src = item.get("source") or ""
    body = (
        f"{who}, CDE: {title} on {date}. {num(credits)} credits. Fee: {fee}. {src}. "
        "Want a calendar hold + the registration line?"
    )
    return body, _cta_yes("send the registration line"), "CDE uses digest item title/date/credits from category + trigger.", "vera_cde_v1"


def _competitor(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    name = payload.get("competitor_name")
    km = payload.get("distance_km")
    their = payload.get("their_offer")
    opened = payload.get("opened_date")
    ours = facts.get("offer")
    ours_bit = f" You already run {ours}." if ours else ""
    body = (
        f"{who}, {name} opened {km} km away on {opened} with {their}.{ours_bit} "
        "Not a price war — want a GBP post that states your service+price and wait-time honestly?"
    )
    return body, _cta_yes("draft the comparison-safe post"), "Competitor uses name, distance, offer, date from trigger.", "vera_competitor_v1"


def _perf_spike(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    metric = payload.get("metric") or "calls"
    delta = payload.get("delta_pct")
    driver = payload.get("likely_driver")
    vs = payload.get("vs_baseline")
    body = (
        f"{who}, {metric} {pct(delta)} in {payload.get('window') or '7d'}"
        f"{' vs baseline ' + str(vs) if vs is not None else ''}."
        f"{' Likely driver: ' + str(driver) + '.' if driver else ''} "
        "Want me to double-down with one follow-up post while the spike is warm?"
    )
    return body, _cta_yes("draft the follow-up post"), "Spike uses delta, baseline, and stated driver only.", "vera_perf_spike_v1"


def _dormant(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    days = payload.get("days_since_last_merchant_message")
    topic = payload.get("last_topic")
    loc = facts.get("locality")
    offer = facts.get("offer")
    offer_bit = f" I can also relaunch {offer}." if offer else ""
    body = (
        f"{who}, {num(days)} days quiet after {topic}. Not a guilt trip — one useful thing for {loc}:{offer_bit} "
        "Want a single GBP post draft, then I'll stay out of the way?"
    )
    return body, _cta_yes("send one post draft"), "Dormancy uses days-since and last topic from trigger.", "vera_dormant_v1"


def _appt(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    name = facts.get("customer_name") or "there"
    when = payload.get("slot_label") or payload.get("iso") or payload.get("appointment_iso")
    biz = facts.get("biz")
    body = (
        f"Hi {name}, reminder from {biz}: appointment {when}. Reply YES to confirm or send a new time."
    )
    return body, _cta_yes("confirm the appointment"), "Appointment reminder uses customer name and slot from payload.", "vera_appt_v1"


def _generic(slug, mix, who, facts, category, merchant, trigger, customer, payload):
    """Fallback: quote whatever facts exist; never invent search volumes or prices."""
    kind = trigger.get("kind")
    place = facts.get("place")
    offer = facts.get("offer")
    views = facts.get("views")
    calls = facts.get("calls")
    bits = [f"{who}", f"{place}" if place else "", f"trigger={kind}"]
    payload_bits = []
    for k, v in list(payload.items())[:6]:
        if v is None or v is True and k == "placeholder":
            continue
        if isinstance(v, (dict, list)):
            payload_bits.append(f"{k}={v}")
        else:
            payload_bits.append(f"{k}={v}")
    perf_bit = ""
    if views is not None or calls is not None:
        perf_bit = f" Snapshot: views={num(views)}, calls={num(calls)}."
    offer_bit = f" Active offer: {offer}." if offer else ""
    extra = (" " + "; ".join(str(x) for x in payload_bits[:4]) + ".") if payload_bits else ""
    body = (
        f"{' · '.join([b for b in bits if b])}.{perf_bit}{offer_bit}{extra} "
        "Want me to draft the next action from this signal?"
    )
    return body, _cta_yes("draft the next action"), "Generic path quotes trigger payload + merchant snapshot only.", "vera_generic_v1"
