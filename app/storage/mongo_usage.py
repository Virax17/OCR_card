"""Persistent, restart-surviving API usage counters backed by MongoDB.

Render's filesystem is ephemeral, so the per-event SQLite ``llm_usage`` tables
reset on every restart and cannot enforce a real monthly/daily budget. This
module keeps the authoritative counters in MongoDB instead:

* Google Vision -> one document per calendar month (period "2026-07")
* Gemini        -> one document per day            (period "2026-07-09")

Each document is a bucket with ``provider``, ``period``, ``count`` and optional
``tokens`` fields. Counts are bumped with an atomic ``$inc`` upsert, so
concurrent workers do not lose increments. A TTL index on ``expire_at`` lets
MongoDB auto-delete old buckets after they are no longer needed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import (
    MONGO_GEMINI_DAILY_LIMIT,
    MONGO_USAGE_ENABLED,
    MONGO_USAGE_FAIL_CLOSED,
    MONGO_USAGE_TTL_DAYS,
    MONGO_VISION_MONTHLY_LIMIT,
    MONGODB_DB_NAME,
    MONGODB_URI,
)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "usage_counters"
UNAVAILABLE_MESSAGE = "MongoDB usage tracker is unavailable"

# provider -> ("month" | "day", limit, display label, unit label)
_PROVIDER_PERIODS = {
    "google_vision": ("month", MONGO_VISION_MONTHLY_LIMIT, "Google Vision", "OCR units"),
    "gemini": ("day", MONGO_GEMINI_DAILY_LIMIT, "Gemini", "requests"),
}

_client = None
_index_ready = False
_last_error: str | None = None


@dataclass(frozen=True)
class MongoUsage:
    """Snapshot of one provider's current-period usage from MongoDB."""

    provider: str
    period_kind: str  # "month" or "day"
    period: str  # e.g. "2026-07" or "2026-07-09"
    used: int
    limit: int
    tokens: int = 0

    @property
    def hit_limit(self) -> bool:
        return self.limit > 0 and self.used >= self.limit

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


def is_enabled() -> bool:
    return bool(MONGO_USAGE_ENABLED and MONGODB_URI)


def is_unavailable_reason(reason: str | None) -> bool:
    return bool(reason and reason.startswith(UNAVAILABLE_MESSAGE))


def period_key(kind: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if kind == "month":
        return now.strftime("%Y-%m")
    return now.strftime("%Y-%m-%d")


def _provider_label(provider: str) -> str:
    return _PROVIDER_PERIODS.get(provider, ("", 0, provider, ""))[2]


def _provider_unit(provider: str) -> str:
    return _PROVIDER_PERIODS.get(provider, ("", 0, "", "units"))[3]


def _unavailable_reason() -> str:
    detail = f": {_last_error}" if _last_error else ""
    return f"{UNAVAILABLE_MESSAGE}{detail}. Processing is paused so API limits stay accurate."


def _get_collection():
    """Return the usage collection, or None if Mongo is unavailable/disabled."""
    global _client, _index_ready, _last_error
    if not is_enabled():
        _last_error = None
        return None
    try:
        if _client is None:
            # Import here so the app still starts if pymongo is missing.
            from pymongo import MongoClient
            from pymongo.server_api import ServerApi

            _client = MongoClient(
                MONGODB_URI,
                server_api=ServerApi("1"),
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
            )
        collection = _client[MONGODB_DB_NAME][COLLECTION_NAME]
        if not _index_ready:
            collection.create_index([("provider", 1), ("period", 1)], unique=True)
            collection.create_index("expire_at", expireAfterSeconds=0)
            _index_ready = True
        _last_error = None
        return collection
    except Exception as exc:  # noqa: BLE001
        _last_error = str(exc)
        logger.warning("Mongo usage unavailable: %s", exc)
        return None


def initialize() -> bool:
    """Warm up the Mongo connection and indexes. Returns True when available."""
    return _get_collection() is not None


def get_usage(provider: str, now: datetime | None = None) -> MongoUsage | None:
    """Current-period usage for a provider, or None if tracking is unavailable."""
    spec = _PROVIDER_PERIODS.get(provider)
    if spec is None:
        return None
    kind, limit, _label, _unit = spec
    period = period_key(kind, now)
    collection = _get_collection()
    if collection is None:
        return None
    try:
        doc = collection.find_one({"provider": provider, "period": period})
    except Exception as exc:  # noqa: BLE001
        global _last_error
        _last_error = str(exc)
        logger.warning("Mongo get_usage failed: %s", exc)
        return None
    used = int(doc.get("count", 0)) if doc else 0
    tokens = int(doc.get("tokens", 0)) if doc else 0
    return MongoUsage(provider=provider, period_kind=kind, period=period, used=used, limit=limit, tokens=tokens)


def check_limits(required: dict[str, int] | None = None, now: datetime | None = None) -> tuple[bool, str | None]:
    """Return whether the requested API work may start.

    ``required`` contains the units a new action expects to consume, for example
    ``{"google_vision": 2, "gemini": 1}`` for a two-sided card.
    """
    if not is_enabled():
        return True, None

    if _get_collection() is None:
        if MONGO_USAGE_FAIL_CLOSED:
            return False, _unavailable_reason()
        return True, None

    required = required or {}
    for provider in _PROVIDER_PERIODS:
        usage = get_usage(provider, now)
        if usage is None:
            if MONGO_USAGE_FAIL_CLOSED:
                return False, _unavailable_reason()
            continue
        amount = max(0, int(required.get(provider, 0) or 0))
        projected = usage.used + amount
        if usage.limit > 0 and projected > usage.limit:
            label = "monthly" if usage.period_kind == "month" else "daily"
            needed = f"; this scan needs {amount} {_provider_unit(provider)}" if amount else ""
            return False, (
                f"{_provider_label(provider)} {label} limit reached "
                f"({usage.used}/{usage.limit} used for {usage.period}{needed}). "
                "Processing is paused until the counter resets."
            )
    return True, None


def increment(provider: str, amount: int = 1, token_count: int = 0, now: datetime | None = None) -> None:
    """Atomically add usage to a provider's current-period bucket."""
    if amount <= 0 and token_count <= 0:
        return
    spec = _PROVIDER_PERIODS.get(provider)
    if spec is None:
        return
    kind, _limit, _label, _unit = spec
    collection = _get_collection()
    if collection is None:
        return
    now = now or datetime.now(UTC)
    period = period_key(kind, now)
    expire_at = now + timedelta(days=MONGO_USAGE_TTL_DAYS)
    update: dict[str, Any] = {
        "$inc": {},
        "$setOnInsert": {
            "provider": provider,
            "period": period,
            "period_kind": kind,
            "expire_at": expire_at,
            "created_at": now,
        },
        "$set": {"updated_at": now},
    }
    if amount > 0:
        update["$inc"]["count"] = amount
    if token_count > 0:
        update["$inc"]["tokens"] = token_count
    try:
        collection.update_one({"provider": provider, "period": period}, update, upsert=True)
    except Exception as exc:  # noqa: BLE001
        global _last_error
        _last_error = str(exc)
        logger.warning("Mongo increment failed: %s", exc)


def usage_report(now: datetime | None = None) -> dict:
    """Serializable snapshot of all tracked providers for the /llm-usage payload."""
    report: dict[str, Any] = {
        "enabled": is_enabled(),
        "configured": bool(MONGODB_URI),
        "database": MONGODB_DB_NAME,
        "collection": COLLECTION_NAME,
        "fail_closed": MONGO_USAGE_FAIL_CLOSED,
        "available": False,
    }
    if not is_enabled():
        return report

    any_available = False
    for provider in _PROVIDER_PERIODS:
        usage = get_usage(provider, now)
        if usage is None:
            continue
        any_available = True
        report[provider] = {
            "period_kind": usage.period_kind,
            "period": usage.period,
            "used": usage.used,
            "limit": usage.limit,
            "remaining": usage.remaining,
            "hit_limit": usage.hit_limit,
            "tokens_estimated": usage.tokens,
        }
    report["available"] = any_available
    if not any_available and _last_error:
        report["error"] = _last_error
    return report
