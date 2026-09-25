# Vera Message Engine

Stateful FastAPI service for the magicpin AI Challenge. It stores versioned category/merchant/customer/trigger context and composes deterministic WhatsApp-style messages via `compose(category, merchant, trigger, customer?)`.

## Approach

- **No invented facts.** Numbers, prices, dates, localities, digest citations, and offers are copied from pushed JSON. If a field is missing, the line is omitted rather than filled with a fake search volume.
- **Trigger-kind dispatch.** Each `trigger.kind` has a grounded template (research digest, recall, dip, IPL, supply alert, …) plus a payload-quoting fallback.
- **Category voice.** Dentists stay clinical/peer; salons warm; restaurants operator-to-operator; gyms coaching; pharmacies precise. Taboo phrases are stripped.
- **Single CTA.** One YES / slot / STOP action per payload.
- **Multi-turn.** `/v1/reply` detects canned auto-replies (including across new `conversation_id`s for the same merchant), commitment (“let’s do it”), hostility, and wait requests.

The official judge scores the tick field `body` and expects `{ "actions": [...] }` / `{ "action": "send|wait|end" }` — that is the contract this server implements (`challenge-testing-brief.md`).

## Setup

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python dataset/generate_dataset.py --seed-dir dataset --out expanded
```

## Run

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

Port **8080** matches `judge_simulator.py` (`BOT_URL`). Use 8000 only if you change the judge config.

## Judge

1. Put an LLM API key in `judge_simulator.py` (needed for scoring, not for the bot).
2. Keep `BOT_URL = "http://localhost:8080"`.
3. `python judge_simulator.py`

Warmup + reply scenarios do not require the judge LLM if you only need connectivity; the script currently always tests the LLM connection first.

## Endpoints

| Method | Path | Role |
| --- | --- | --- |
| GET | `/v1/healthz` | Liveness + context counts |
| GET | `/v1/metadata` | Team / model identity |
| POST | `/v1/context` | Idempotent versioned upsert |
| POST | `/v1/tick` | Compose actions for active triggers |
| POST | `/v1/reply` | Next send / wait / end |
| POST | `/v1/teardown` | Wipe in-memory state |

Edit `team_name` / `contact_email` in `src/main.py` before submitting a public URL.
