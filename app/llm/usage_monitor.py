from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import (
    EVENTS_ROOT,
    GEMINI_DAILY_REQUEST_LIMIT,
    GEMINI_DAILY_TOKEN_LIMIT,
    GEMINI_MINUTE_REQUEST_LIMIT,
    GOOGLE_VISION_FREE_UNITS_MONTHLY,
    GOOGLE_VISION_MINUTE_REQUEST_LIMIT,
    GOOGLE_VISION_PRICE_PER_1000,
)
from app.storage import mongo_usage
from app.storage.db import connection, new_id, utc_now
from app.storage.repositories import db_path_for


@dataclass(frozen=True)
class UsageSnapshot:
    daily_requests: int
    minute_requests: int
    daily_tokens: int
    daily_request_limit: int
    minute_request_limit: int
    daily_token_limit: int

    @property
    def allowed(self) -> bool:
        return (
            self.daily_requests < self.daily_request_limit
            and self.minute_requests < self.minute_request_limit
            and self.daily_tokens < self.daily_token_limit
        )


@dataclass(frozen=True)
class ProviderUsageSnapshot:
    provider: str
    daily_requests: int
    minute_requests: int
    monthly_units: int
    daily_tokens: int = 0
    daily_request_limit: int | None = None
    minute_request_limit: int | None = None
    daily_token_limit: int | None = None
    free_units_monthly: int | None = None
    estimated_cost_usd: float = 0.0
    by_key: dict[str, int] | None = None


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _ensure_usage_columns(conn) -> None:
    columns = {row["name"] for row in conn.execute('PRAGMA table_info("llm_usage")').fetchall()}
    if "key_label" not in columns:
        conn.execute('ALTER TABLE "llm_usage" ADD COLUMN "key_label" TEXT')
    if "unit_count" not in columns:
        conn.execute('ALTER TABLE "llm_usage" ADD COLUMN "unit_count" INTEGER NOT NULL DEFAULT 0')
    if "cost_estimate_usd" not in columns:
        conn.execute('ALTER TABLE "llm_usage" ADD COLUMN "cost_estimate_usd" REAL NOT NULL DEFAULT 0')


def _usage_counts_for_db(db_path: Path, provider: str = "gemini") -> tuple[int, int, int, int, float, dict[str, int]]:
    if not db_path.exists():
        return 0, 0, 0, 0, 0.0, {}
    with connection(db_path) as conn:
        _ensure_usage_columns(conn)
        daily = conn.execute(
            """
            SELECT
              COALESCE(SUM(request_count), 0) AS requests,
              COALESCE(SUM(total_tokens), 0) AS tokens,
              COALESCE(SUM(cost_estimate_usd), 0) AS cost
            FROM llm_usage
            WHERE provider = ?
              AND datetime(created_at) >= datetime('now', '-1 day')
            """,
            (provider,),
        ).fetchone()
        minute = conn.execute(
            """
            SELECT COALESCE(SUM(request_count), 0) AS requests
            FROM llm_usage
            WHERE provider = ?
              AND datetime(created_at) >= datetime('now', '-1 minute')
            """,
            (provider,),
        ).fetchone()
        monthly = conn.execute(
            """
            SELECT COALESCE(SUM(unit_count), 0) AS units
            FROM llm_usage
            WHERE provider = ?
              AND datetime(created_at) >= datetime('now', 'start of month')
            """,
            (provider,),
        ).fetchone()
        key_rows = conn.execute(
            """
            SELECT COALESCE(key_label, 'default') AS key_label, COALESCE(SUM(request_count), 0) AS requests
            FROM llm_usage
            WHERE provider = ?
              AND datetime(created_at) >= datetime('now', '-1 day')
            GROUP BY COALESCE(key_label, 'default')
            """,
            (provider,),
        ).fetchall()
    by_key = {row["key_label"]: int(row["requests"]) for row in key_rows}
    return int(daily["requests"]), int(minute["requests"]), int(daily["tokens"]), int(monthly["units"]), float(daily["cost"]), by_key


def usage_snapshot(event_id: str | None = None) -> UsageSnapshot:
    if event_id:
        daily_requests, minute_requests, daily_tokens, _, _, _ = _usage_counts_for_db(db_path_for(event_id), "gemini")
    else:
        daily_requests = 0
        minute_requests = 0
        daily_tokens = 0
        for db_path in Path(EVENTS_ROOT).glob("*/app.db"):
            db_daily, db_minute, db_tokens, _, _, _ = _usage_counts_for_db(db_path, "gemini")
            daily_requests += db_daily
            minute_requests += db_minute
            daily_tokens += db_tokens
    return UsageSnapshot(
        daily_requests=daily_requests,
        minute_requests=minute_requests,
        daily_tokens=daily_tokens,
        daily_request_limit=GEMINI_DAILY_REQUEST_LIMIT,
        minute_request_limit=GEMINI_MINUTE_REQUEST_LIMIT,
        daily_token_limit=GEMINI_DAILY_TOKEN_LIMIT,
    )


def provider_usage_snapshot(provider: str, event_id: str | None = None) -> ProviderUsageSnapshot:
    totals = {
        "daily_requests": 0,
        "minute_requests": 0,
        "daily_tokens": 0,
        "monthly_units": 0,
        "estimated_cost_usd": 0.0,
    }
    by_key: dict[str, int] = {}
    db_paths = [db_path_for(event_id)] if event_id else list(Path(EVENTS_ROOT).glob("*/app.db"))
    for db_path in db_paths:
        db_daily, db_minute, db_tokens, db_units, db_cost, db_by_key = _usage_counts_for_db(db_path, provider)
        totals["daily_requests"] += db_daily
        totals["minute_requests"] += db_minute
        totals["daily_tokens"] += db_tokens
        totals["monthly_units"] += db_units
        totals["estimated_cost_usd"] += db_cost
        for key, count in db_by_key.items():
            by_key[key] = by_key.get(key, 0) + count
    if provider == "gemini":
        return ProviderUsageSnapshot(
            provider=provider,
            daily_request_limit=GEMINI_DAILY_REQUEST_LIMIT,
            minute_request_limit=GEMINI_MINUTE_REQUEST_LIMIT,
            daily_token_limit=GEMINI_DAILY_TOKEN_LIMIT,
            by_key=by_key,
            **totals,
        )
    if provider == "google_vision":
        monthly_billable = max(0, totals["monthly_units"] - GOOGLE_VISION_FREE_UNITS_MONTHLY)
        return ProviderUsageSnapshot(
            provider=provider,
            minute_request_limit=GOOGLE_VISION_MINUTE_REQUEST_LIMIT,
            free_units_monthly=GOOGLE_VISION_FREE_UNITS_MONTHLY,
            estimated_cost_usd=round((monthly_billable / 1000) * GOOGLE_VISION_PRICE_PER_1000, 4),
            by_key=by_key,
            daily_requests=totals["daily_requests"],
            minute_requests=totals["minute_requests"],
            daily_tokens=0,
            monthly_units=totals["monthly_units"],
        )
    return ProviderUsageSnapshot(provider=provider, by_key=by_key, **totals)


def record_usage(
    event_id: str,
    *,
    provider: str = "gemini",
    model: str,
    purpose: str,
    prompt_tokens: int,
    completion_tokens: int = 0,
    request_count: int = 1,
    unit_count: int = 0,
    cost_estimate_usd: float = 0.0,
    key_label: str | None = None,
    status: str = "ok",
    error_message: str | None = None,
) -> None:
    total_tokens = prompt_tokens + completion_tokens
    with connection(db_path_for(event_id)) as conn:
        _ensure_usage_columns(conn)
        conn.execute(
            """
            INSERT INTO llm_usage (
              usage_id, event_id, provider, model, purpose, prompt_tokens, completion_tokens,
              total_tokens, request_count, status, error_message, created_at, key_label, unit_count, cost_estimate_usd
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("usage"),
                event_id,
                provider,
                model,
                purpose,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                request_count,
                status,
                error_message,
                utc_now(),
                key_label,
                unit_count,
                cost_estimate_usd,
            ),
        )
    # Keep the 24/7 MongoDB counters in sync with every real API attempt.
    # Local-limit/config skips do not touch external APIs, so they should not
    # consume the persistent budget.
    if status not in {"blocked_local_limit", "skipped_not_configured"}:
        if provider == "google_vision":
            mongo_usage.increment(provider, amount=unit_count or request_count)
        elif provider == "gemini":
            mongo_usage.increment(provider, amount=request_count, token_count=total_tokens)
