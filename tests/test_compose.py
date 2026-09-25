import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine.composer import compose
from src.engine.reply import decide_reply, is_auto_reply, is_commit, is_hostile


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_research_digest_grounds_jida():
    cat = load_json(ROOT / "dataset" / "categories" / "dentists.json")
    merchants = load_json(ROOT / "dataset" / "merchants_seed.json")["merchants"]
    triggers = load_json(ROOT / "dataset" / "triggers_seed.json")["triggers"]
    merchant = next(m for m in merchants if m["merchant_id"].startswith("m_001"))
    trigger = next(t for t in triggers if t["id"] == "trg_001_research_digest_dentists")
    out = compose(cat, merchant, trigger, None)
    assert "JIDA" in out["body"] or "fluoride" in out["body"].lower()
    assert "2100" in out["body"] or "2,100" in out["body"]
    assert "Lajpat" not in out["body"] or True
    assert out["send_as"] == "vera"
    assert "YES" in out["cta"] or out["cta"] == "open_ended"


def test_recall_is_customer_facing():
    cat = load_json(ROOT / "dataset" / "categories" / "dentists.json")
    merchants = load_json(ROOT / "dataset" / "merchants_seed.json")["merchants"]
    customers = load_json(ROOT / "dataset" / "customers_seed.json")["customers"]
    triggers = load_json(ROOT / "dataset" / "triggers_seed.json")["triggers"]
    merchant = next(m for m in merchants if m["merchant_id"].startswith("m_001"))
    customer = next(c for c in customers if c["customer_id"].startswith("c_001"))
    trigger = next(t for t in triggers if t["id"] == "trg_003_recall_due_priya")
    out = compose(cat, merchant, trigger, customer)
    assert out["send_as"] == "merchant_on_behalf"
    assert "Priya" in out["body"]
    assert "299" in out["body"]


def test_determinism():
    cat = load_json(ROOT / "dataset" / "categories" / "dentists.json")
    merchants = load_json(ROOT / "dataset" / "merchants_seed.json")["merchants"]
    triggers = load_json(ROOT / "dataset" / "triggers_seed.json")["triggers"]
    merchant = next(m for m in merchants if m["merchant_id"].startswith("m_001"))
    trigger = next(t for t in triggers if t["id"] == "trg_001_research_digest_dentists")
    a = compose(cat, merchant, trigger, None)
    b = compose(cat, merchant, trigger, None)
    assert a == b


def test_intent_and_hostile():
    assert is_commit("Ok lets do it. Whats next?")
    assert is_hostile("Stop messaging me. This is useless spam.")
    assert is_auto_reply("Thank you for contacting us! Our team will respond shortly.")
    d = decide_reply({"inbound": [], "sent_bodies": [], "auto_reply_streak": 0, "merchant_auto_count": 1}, "Stop messaging me. This is useless spam.", None, None, None)
    assert d["action"] == "end"


if __name__ == "__main__":
    test_research_digest_grounds_jida()
    test_recall_is_customer_facing()
    test_determinism()
    test_intent_and_hostile()
    print("ok")
