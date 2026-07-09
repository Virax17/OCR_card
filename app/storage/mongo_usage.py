"""Persistent, restart-surviving usage counters backed by MongoDB.

Render's filesystem is ephemeral, so the per-event SQLite ``llm_usage`` tables
reset on every restart and cannot enforce a real monthly/daily budget. This
module keeps the authoritative counters in MongoDB instead:

* Google Vision  -> one document per calendar month  (period "2026-07")
* Gemini         -> one document per day              (period "2026-07-09")

Each document is a bucket ``{provider, period, count}``. Counts are bumped with
an atomic ``$inc`` upsert, so concurrent workers never lose increments. A TTL
index on ``expire_at`` lets MongoDB auto-delete old buckets, which is what makes
the counters "auto reset with the time" without any scheduled job.

Every function fails open: if MongoDB is unreachable or disabled, limit checks
return "allowed" and increments become no-ops, so a Mongo outage degrades to the
previous SQLite-only behaviour rather than breaking scanning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.config import (
    MONGO_GEMINI_DAILY_LIMIT,
    MONGO_USAGE_ENABLED,
    MONGO_USAGE_TTL_DAYS,
    MONGO_VISION_MONTHLY_LIMIT,
    MONGODB_DB_NAME,
    MONGODB_URI,
)

logger = logging.getLogger(__name__)

COLLECTION_NAME = "usage_counters"

# provider -> ("month" | "day", limit)
_PROVIDER_PERIODS = {
    "google_vision": ("month", MONGO_VISION_MONTHLY_LIMIT),
    "gemini": ("day", MONGO_GEMINI_DAILY_LIMIT),
}

_client = None
_index_ready = False


@dataclass(frozen=True)
class MongoUsage:
    """Snapshot of one provider's current-period usage from MongoDB."""

    provider: str
    period_kind: str  # "month" or "day"
    period: str  # e.g. "2026-07" or "2026-07-09"
    used: int
    limit: int

    @property
    def hit_limit(self) -> bool:
        return self.limit > 0 and self.used >= self.limit

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


def is_enabled() -> bool:
    return bool(MONGO_USAGE_ENABLED and MONGODB_URI)


def period_key(kind: str, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if kind == "month":
        return now.strftime("%Y-%m")
    return now.strftime("%Y-%m-%d")


def _get_collection():
    """Return the usage collection, or None if Mongo is unavailable/disabled."""
    global _client, _index_ready
    if not is_enabled():
        return None
    try:
        if _client is None:
            # Import here so the app still starts if pymongo isn't installed.
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
            # Unique bucket per (provider, period); TTL sweeps old buckets.
            collection.create_index([("provider", 1), ("period", 1)], unique=True)
            collection.create_index("expire_at", expireAfterSeconds=0)
            _index_ready = True
        return collection
    except Exception as exc:  # noqa: BLE001 — fail open on any Mongo/driver error
        logger.warning("Mongo usage unavailable (fail-open): %s", exc)
        return None


def get_usage(provider: str, now: datetime | None = None) -> MongoUsage | None:
    """Current-period usage for a provider, or None if tracking is unavailable."""
    spec = _PROVIDER_PERIODS.get(provider)
    if spec is None:
        return None
    kind, limit = spec
    period = period_key(kind, now)
    collection = _get_collection()
    if collection is None:
        return None
    try:
        doc = collection.find_one({"provider": provider, "period": period})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mongo get_usage failed (fail-open): %s", exc)
        return None
    used = int(doc.get("count", 0)) if doc else 0
    return MongoUsage(provider=provider, period_kind=kind, period=period, used=used, limit=limit)


def check_limits(now: datetime | None = None) -> tuple[bool, str | None]:
    """Return (allowed, reason). Fails open to (True, None) when Mongo is down."""
    for provider in _PROVIDER_PERIODS:
        usage = get_usage(provider, now)
        if usage is None:
            continue  # tracking unavailable for this provider -> don't block
        if usage.hit_limit:
            label = "monthly" if usage.period_kind == "month" else "daily"
            return False, (
                f"{provider} {label} limit reached "
                f"({usage.used}/{usage.limit} for {usage.period}). "
                "Processing is paused until the counter resets."
            )
    return True, None


def increment(provider: str, amount: int = 1, now: datetime | None = None) -> None:
    """Atomically add ``amount`` to a provider's current-period bucket (no-op on failure)."""
    if amount <= 0:
        return
    spec = _PROVIDER_PERIODS.get(provider)
    if spec is None:
        return
    kind, _ = spec
    collection = _get_collection()
    if collection is None:
        return
    now = now or datetime.now(UTC)
    period = period_key(kind, now)
    expire_at = now + timedelta(days=MONGO_USAGE_TTL_DAYS)
    try:
        collection.update_one(
            {"provider": provider, "period": period},
            {
                "$inc": {"count": amount},
                "$setOnInsert": {
                    "provider": provider,
                    "period": period,
                    "period_kind": kind,
                    "expire_at": expire_at,
                    "created_at": now,
                },
                "$set": {"updated_at": now},
            },
            upsert=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Mongo increment failed (fail-open): %s", exc)


def usage_report(now: datetime | None = None) -> dict:
    """Serializable snapshot of all tracked providers for the /llm-usage payload."""
    if not is_enabled():
        return {"enabled": False}
    report: dict = {"enabled": True}
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
        }
    report["available"] = any_available
    return report
