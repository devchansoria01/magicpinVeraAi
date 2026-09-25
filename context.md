# CONTEXT.md: Vera Message Engine (magicpin AI Challenge)

## 1. Project Overview & Objective

**Vera** is magicpin's AI assistant for merchant growth across 5 primary categories (Dentists, Salons, Restaurants, Gyms, Pharmacies). Vera helps merchants optimize listings, launch high-conversion campaigns, and handle customer engagement.

The goal of this project is to build a high-performance, stateful HTTP service exposing a deterministic composition engine (`compose(category, merchant, trigger, customer?)`) and context store. The engine evaluates incoming triggers, pulls stored merchant/customer context, and outputs contextually grounded, high-conviction growth messages with actionable CTAs.

---

## 2. System Architecture & API Specification

The service must be stateful, fast, and expose five core endpoints under `/v1`.

### 2.1 State Management Rules (`POST /v1/context`)

* **Scope & Versioning:** Context payloads arrive scoped by entity (e.g., `merchant`, `customer`).
* **Atomic Updates:** Re-posting the exact same `version` for a `scope` + `context_id` must be an **idempotent no-op**. A higher `version` number replaces stored state atomically.
* **Storage:** In-memory store or local SQLite with fast key-value querying.

```
POST /v1/context
Request:
{
  "scope": "merchant",
  "context_id": "m_001_drmeera",
  "version": 3,
  "payload": {
    "identity": { ... },
    "performance": { ... },
    "offers": [ ... ]
  },
  "delivered_at": "2026-04-29T10:00:00Z"
}

Response (200 OK):
{
  "accepted": true,
  "ack_id": "ack_abc123",
  "stored_at": "2026-04-29T10:00:00.123Z"
}

```

### 2.2 Execution & Response Specifications

| Endpoint | Method | Purpose | Key Payload / Response |
| --- | --- | --- | --- |
| `/v1/healthz` | `GET` | Health check probe | `{"status": "ok"}` |
| `/v1/metadata` | `GET` | Service capabilities & version | `{"name": "vera-engine", "version": "1.0.0"}` |
| `/v1/tick` | `POST` | Evaluates incoming trigger and generates next action | Input: `trigger_id`, `merchant_id`, `customer_id?`<br><br>Output: Message object (see structure below) |
| `/v1/reply` | `POST` | Processes incoming merchant/customer reply or objection | Input: `thread_id`, `message_text`<br><br>Output: Next reply decision |

#### Standard Response Format (`/v1/tick` and `/v1/reply` output payload):

```json
{
  "message": "190 people in your locality are searching for 'Dental Check Up'. Should I send them a discounted check up at ₹299?",
  "cta": "Reply YES to launch ₹299 Check Up campaign",
  "send_as": "vera_assistant",
  "suppression_key": "campaign_dental_checkup_m_001",
  "rationale": "High local demand signal (190 searches) combined with unutilized ₹299 checkup offer template for Dr. Meera's clinic."
}

```

**Harness note:** The official judge (`judge_simulator.py` + `challenge-testing-brief.md`) scores the tick field `body` (not `message`), expects `/v1/tick` to return `{ "actions": [...] }`, and expects `/v1/reply` to return `{ "action": "send"|"wait"|"end", ... }`. This service implements that contract.

---

## 3. Core Logic: The `compose()` Engine

The message composition pipeline runs via `compose(category, merchant, trigger, customer?)`:

```
┌─────────────────────────────────────────────────────────┐
│ Input Signals: Context Ingestion                        │
│ - Category Rules (Tone, Avoid-lists, Offer patterns)     │
│ - Merchant Context (Metrics, Live offers, History)       │
│ - Trigger Signal (Recall, Spike, Dip, Festival, etc.)   │
│ - Customer Profile (Optional: Relationship, Preference) │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│ Signal Fusion & Grounding Engine                        │
│ 1. Filter out suppressed / invalid offers               │
│ 2. Match trigger type to best performance signal         │
│ 3. Inject explicit numbers, dates, local facts          │
│ 4. Enforce strict single-CTA constraints                │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│ Deterministic Output Generation                         │
│ Output: message, cta, send_as, suppression_key, rationale│
└─────────────────────────────────────────────────────────┘

```

### Input Dimensions & Verticals

1. **Categories (5 Verticals):**
* **Dentists:** Clinical tone, utility-first, trust-focused, non-gimmicky.
* **Salons:** Visual, experiential, trend-driven, seasonal timing.
* **Restaurants:** Timely, urgency-driven (meal slots), visual proof.
* **Gyms:** Goal-oriented, accountability, trial/conversion pushes.
* **Pharmacies:** Strict utility, speed, availability, compliance-safe.


2. **Merchant State:** Identity, conversion signals, traffic dips, existing discount templates.
3. **Triggers:** Local demand spikes, revenue dips, customer recall alerts, festival/seasonal events.
4. **Customer Context:** Opt-in status, past visit history, affinity scores.

---

## 4. Evaluation Rubric & Quality Directives

Outputs are evaluated by `judge_simulator.py` across **5 dimensions (0–10 scale)**:

| Dimension | Target Criteria | Implementation Guardrails |
| --- | --- | --- |
| **Decision Quality** | Optimal signal synthesis | Synthesize Trigger + Merchant State + Category Rules before generating content. Do not ignore active dips or spikes. |
| **Specificity** | Grounded in exact context facts | **MUST** extract and state real numbers, prices, dates, locality names, and active campaign stats directly from input JSON. Zero generic placeholders. |
| **Category Fit** | Precise voice alignment | Strictly enforce tone rules per vertical (e.g., clinical tone for dentists; never use informal salon slangs for dental clinics). |
| **Merchant Fit** | Historical & metrics awareness | Personalize using actual historical merchant performance data, active offer catalogs, and past conversation logs. |
| **Engagement Compulsion** | Actionable prompt | Message must include clear proof, urgency/curiosity, and exactly **one low-effort, single-action CTA** (e.g., simple Yes/No or 1-tap confirmation). |

### Determinism Rule

For identical context states and trigger inputs, the engine **must return deterministic outputs**. Set fixed random seeds (`seed=42`) or use structured heuristic extraction pipelines combined with deterministic LLM temperature (`0.0`).

---

## 5. Repository Structure & Dataset Pipeline

```
magicpin-ai-challenge/
├── context.md                   # AI IDE instruction context
├── README.md                    # System architecture & approach overview
├── requirements.txt             # Python dependencies (FastAPI, uvicorn, pydantic, etc.)
├── judge_simulator.py           # Evaluation test harness (v1.0.0)
├── dataset/
│   ├── categories/              # Verticals: dentists, salons, restaurants, gyms, pharmacies
│   ├── merchants_seed.json      # 10 base seeds
│   ├── customers_seed.json      # 15 base seeds
│   ├── triggers_seed.json       # 25 base seeds
│   └── generate_dataset.py      # Seed expansion script
├── expanded/                    # Generated output from dataset expansion
│   ├── merchants.json           # 50 merchants
│   ├── customers.json           # 200 customers
│   ├── triggers.json            # 100 triggers
│   └── test_pairs.json          # 30 canonical test pairs
└── src/
    ├── main.py                  # FastAPI server entry point
    ├── store.py                 # In-memory / SQLite versioned state manager
    ├── engine/
    │   ├── composer.py          # Deterministic compose() function logic
    │   ├── category_rules.py    # Category tone and constraint rules
    │   └── prompt_builder.py    # Grounded prompt synthesis module
    └── routes/
        ├── context_route.py     # POST /v1/context implementation
        ├── tick_route.py        # POST /v1/tick implementation
        └── reply_route.py       # POST /v1/reply implementation

```

---

## 6. Execution & Setup Commands

### Step 1: Environment Setup & Dataset Generation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Deterministically expand base seeds into 50 merchants, 200 customers, 100 triggers, 30 test pairs
python3 dataset/generate_dataset.py --seed-dir dataset --out expanded

```

### Step 2: Run Local Application Server

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

```

### Step 3: Run Official Judge Simulator

Configure environment keys in `judge_simulator.py` or set environment variables:

```bash
export LLM_PROVIDER="openai"      # or your configured LLM provider
export LLM_API_KEY="your-api-key"
export BOT_URL="http://localhost:8000"

python judge_simulator.py

```

---

## 7. Development Guidelines for AI Assistant

When writing code for this repository:

1. **Never Hallucinate Context:** If a data point (e.g., search volume, price point, locality) is missing from the dataset, fall back to safe context values present in the merchant's active catalog rather than inventing fake claims.
2. **Strict Schema Validation:** Enforce strict Pydantic schemas for all `/v1/` request and response payloads.
3. **Idempotency Execution:** Always check `version` logic in `store.py` when handling `POST /v1/context`.
4. **Single CTA Enforcement:** Validate that generated outputs end with a clear, single choice/action, preventing multiple conflicting calls-to-action in one payload.
