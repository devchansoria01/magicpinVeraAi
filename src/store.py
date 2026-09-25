"""Versioned in-memory context store with idempotent upserts."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Optional


VALID_SCOPES = frozenset({"category", "merchant", "customer", "trigger"})


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ContextStore:
    """Keyed by (scope, context_id). Same version is a no-op; lower version is stale."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: dict[tuple[str, str], dict[str, Any]] = {}
        self._used_suppression: set[str] = set()
        self._conversations: dict[str, dict[str, Any]] = {}
        self._merchant_auto: dict[str, int] = {}
        self._started_at = datetime.now(timezone.utc)

    def upsert(
        self,
        scope: str,
        context_id: str,
        version: int,
        payload: dict[str, Any],
        delivered_at: Optional[str] = None,
    ) -> dict[str, Any]:
        key = (scope, context_id)
        with self._lock:
            current = self._data.get(key)
            stored_at = utc_now_iso()
            if current is not None:
                cur_ver = int(current["version"])
                if version < cur_ver:
                    return {
                        "accepted": False,
                        "reason": "stale_version",
                        "current_version": cur_ver,
                    }
                if version == cur_ver:
                    return {
                        "accepted": True,
                        "ack_id": f"ack_{context_id}_v{version}",
                        "stored_at": current.get("stored_at", stored_at),
                        "noop": True,
                    }
            record = {
                "version": version,
                "payload": payload,
                "delivered_at": delivered_at,
                "stored_at": stored_at,
            }
            self._data[key] = record
            return {
                "accepted": True,
                "ack_id": f"ack_{context_id}_v{version}",
                "stored_at": stored_at,
            }

    def get(self, scope: str, context_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            rec = self._data.get((scope, context_id))
            if rec is None:
                return None
            return rec["payload"]

    def get_record(self, scope: str, context_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._data.get((scope, context_id))

    def counts(self) -> dict[str, int]:
        with self._lock:
            out = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
            for (scope, _), _ in self._data.items():
                if scope in out:
                    out[scope] += 1
            return out

    def uptime_seconds(self) -> int:
        return int((datetime.now(timezone.utc) - self._started_at).total_seconds())

    def mark_suppression(self, key: str) -> None:
        if not key:
            return
        with self._lock:
            self._used_suppression.add(key)

    def is_suppressed(self, key: str) -> bool:
        if not key:
            return False
        with self._lock:
            return key in self._used_suppression

    def put_conversation(self, conversation_id: str, state: dict[str, Any]) -> None:
        with self._lock:
            self._conversations[conversation_id] = state

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        with self._lock:
            return self._conversations.setdefault(
                conversation_id,
                {
                    "turns": [],
                    "sent_bodies": [],
                    "inbound": [],
                    "auto_reply_streak": 0,
                    "mode": "pitch",
                },
            )

    def bump_merchant_auto(self, merchant_id: str) -> int:
        with self._lock:
            self._merchant_auto[merchant_id] = self._merchant_auto.get(merchant_id, 0) + 1
            return self._merchant_auto[merchant_id]

    def reset_merchant_auto(self, merchant_id: str) -> None:
        with self._lock:
            self._merchant_auto[merchant_id] = 0

    def merchant_auto_count(self, merchant_id: str) -> int:
        with self._lock:
            return self._merchant_auto.get(merchant_id, 0)

    def teardown(self) -> None:
        with self._lock:
            self._data.clear()
            self._used_suppression.clear()
            self._conversations.clear()
            self._merchant_auto.clear()
            self._started_at = datetime.now(timezone.utc)


store = ContextStore()
