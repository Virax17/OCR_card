from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import EVENTS_ROOT, GEMINI_DAILY_REQUEST_LIMIT, GEMINI_DAILY_TOKEN_LIMIT, GEMINI_MINUTE_REQUEST_LIMIT
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


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _usage_counts_for_db(db_path: Path) -> tuple[int, int, int]:
    if not db_path.exists():
        return 0, 0, 0
    with connection(db_path) as conn:
        daily = conn.execute(
            """
            SELECT
              COALESCE(SUM(request_count), 0) AS requests,
              COALESCE(SUM(total_tokens), 0) AS tokens
            FROM llm_usage
            WHERE provider = 'gemini'
              AND datetime(created_at) >= datetime('now', '-1 day')
            """
        ).fetchone()
        minute = conn.execute(
            """
            SELECT COALESCE(SUM(request_count), 0) AS requests
            FROM llm_usage
            WHERE provider = 'gemini'
              AND datetime(created_at) >= datetime('now', '-1 minute')
            """
        ).fetchone()
    return int(daily["requests"]), int(minute["requests"]), int(daily["tokens"])


def usage_snapshot(event_id: str | None = None) -> UsageSnapshot:
    if event_id:
        daily_requests, minute_requests, daily_tokens = _usage_counts_for_db(db_path_for(event_id))
    else:
        daily_requests = 0
        minute_requests = 0
        daily_tokens = 0
        for db_path in Path(EVENTS_ROOT).glob("*/app.db"):
            db_daily, db_minute, db_tokens = _usage_counts_for_db(db_path)
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


def record_usage(
    event_id: str,
    *,
    model: str,
    purpose: str,
    prompt_tokens: int,
    completion_tokens: int = 0,
    status: str = "ok",
    error_message: str | None = None,
) -> None:
    with connection(db_path_for(event_id)) as conn:
        conn.execute(
            """
            INSERT INTO llm_usage (
              usage_id, event_id, provider, model, purpose, prompt_tokens, completion_tokens,
              total_tokens, request_count, status, error_message, created_at
            )
            VALUES (?, ?, 'gemini', ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                new_id("usage"),
                event_id,
                model,
                purpose,
                prompt_tokens,
                completion_tokens,
                prompt_tokens + completion_tokens,
                status,
                error_message,
                utc_now(),
            ),
        )
