from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import EVENTS_ROOT
from app.models import BusinessCardRecord, EventOut, FieldCandidate, OCRSideResult
from app.storage.db import connection, event_db_path, initialize_event_database, new_id, utc_now


def db_path_for(event_id: str) -> Path:
    return event_db_path(EVENTS_ROOT, event_id)


def ensure_event(event_id: str, name: str, date: str, location: str | None = None) -> Path:
    return initialize_event_database(EVENTS_ROOT, event_id=event_id, name=name, date=date, location=location)


def list_events() -> list[EventOut]:
    root = Path(EVENTS_ROOT)
    if not root.exists():
        return []
    events: list[EventOut] = []
    for db_path in sorted(root.glob("*/app.db")):
        with connection(db_path) as conn:
            rows = conn.execute("SELECT event_id, name, date, location, booth, notes FROM events ORDER BY created_at").fetchall()
            for row in rows:
                events.append(EventOut(**dict(row)))
    return events


def get_event(event_id: str) -> EventOut | None:
    path = db_path_for(event_id)
    if not path.exists():
        return None
    with connection(path) as conn:
        row = conn.execute("SELECT event_id, name, date, location, booth, notes FROM events WHERE event_id = ?", (event_id,)).fetchone()
    return EventOut(**dict(row)) if row else None


def create_card(event_id: str, processing_mode: str = "balanced") -> str:
    card_id = new_id("card")
    now = utc_now()
    with connection(db_path_for(event_id)) as conn:
        conn.execute(
            """
            INSERT INTO cards (card_id, event_id, status, processing_mode, created_at, updated_at)
            VALUES (?, ?, 'processing', ?, ?, ?)
            """,
            (card_id, event_id, processing_mode, now, now),
        )
    return card_id


def insert_card_side(
    event_id: str,
    *,
    card_id: str,
    side: str,
    filename: str,
    content_type: str | None,
    width: int | None = None,
    height: int | None = None,
    quality_score: str | None = None,
    quality_warnings: list[str] | None = None,
) -> None:
    with connection(db_path_for(event_id)) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO card_sides
              (side_id, card_id, side, filename, content_type, width, height, quality_score, quality_warnings, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_id("side"),
                card_id,
                side,
                filename,
                content_type,
                width,
                height,
                quality_score,
                json.dumps(quality_warnings or []),
                utc_now(),
            ),
        )


def insert_ocr_result(event_id: str, card_id: str, result: OCRSideResult) -> None:
    ocr_result_id = new_id("ocr")
    with connection(db_path_for(event_id)) as conn:
        conn.execute(
            """
            INSERT INTO ocr_results
              (ocr_result_id, card_id, side, engine, engine_version, variant, runtime_ms, status, error_message, raw_text, average_confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ocr_result_id,
                card_id,
                result.side,
                result.engine,
                result.engine_version,
                result.variant,
                result.runtime_ms,
                result.status,
                result.error_message,
                result.raw_text,
                result.average_confidence,
                utc_now(),
            ),
        )
        for block in result.blocks:
            conn.execute(
                """
                INSERT INTO ocr_blocks (block_id, ocr_result_id, line_index, text, confidence, engine, variant, normalized_text, bbox_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("block"),
                    ocr_result_id,
                    block.line_index,
                    block.text,
                    block.confidence,
                    block.engine or result.engine,
                    block.variant or result.variant,
                    block.normalized_text,
                    json.dumps(block.bbox),
                ),
            )


def insert_field_candidates(event_id: str, card_id: str, candidates: list[FieldCandidate]) -> None:
    with connection(db_path_for(event_id)) as conn:
        for candidate in candidates:
            conn.execute(
                """
                INSERT INTO field_candidates
                  (candidate_id, card_id, field_name, value, confidence, source, evidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id("cand"),
                    card_id,
                    candidate.field,
                    candidate.value,
                    candidate.confidence,
                    candidate.source,
                    candidate.evidence,
                    utc_now(),
                ),
            )


def upsert_card_record(record: BusinessCardRecord) -> None:
    now = utc_now()
    with connection(db_path_for(record.event_id)) as conn:
        conn.execute(
            """
            INSERT INTO card_records (
                record_id, card_id, event_id, name, designation, company, business, phone_primary, phone_number,
                mobile_number, phone_extra, fax_number, country_code, email, website, address, city, state, country,
                zip_code, category, social_media, notes, email1, email2, contact1, contact2, contact3, confidence_score,
                low_confidence_fields, duplicate_flag, front_image_filename, back_image_filename,
                reviewed_by_user, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(card_id) DO UPDATE SET
                name = excluded.name,
                designation = excluded.designation,
                company = excluded.company,
                business = excluded.business,
                phone_primary = excluded.phone_primary,
                phone_number = excluded.phone_number,
                mobile_number = excluded.mobile_number,
                phone_extra = excluded.phone_extra,
                fax_number = excluded.fax_number,
                country_code = excluded.country_code,
                email = excluded.email,
                website = excluded.website,
                address = excluded.address,
                city = excluded.city,
                state = excluded.state,
                country = excluded.country,
                zip_code = excluded.zip_code,
                category = excluded.category,
                social_media = excluded.social_media,
                notes = excluded.notes,
                email1 = excluded.email1,
                email2 = excluded.email2,
                contact1 = excluded.contact1,
                contact2 = excluded.contact2,
                contact3 = excluded.contact3,
                confidence_score = excluded.confidence_score,
                low_confidence_fields = excluded.low_confidence_fields,
                duplicate_flag = excluded.duplicate_flag,
                front_image_filename = excluded.front_image_filename,
                back_image_filename = excluded.back_image_filename,
                reviewed_by_user = excluded.reviewed_by_user,
                updated_at = excluded.updated_at
            """,
            (
                record.record_id,
                record.card_id,
                record.event_id,
                record.name,
                record.designation,
                record.company,
                record.business,
                record.phone_primary,
                record.phone_number,
                record.mobile_number,
                record.phone_extra,
                record.fax_number,
                record.country_code,
                record.email,
                record.website,
                record.address,
                record.city,
                record.state,
                record.country,
                record.zip_code,
                record.category,
                record.social_media,
                record.notes,
                record.email1,
                record.email2,
                record.contact1,
                record.contact2,
                record.contact3,
                record.confidence_score,
                ", ".join(record.low_confidence_fields),
                record.duplicate_flag,
                record.front_image_filename,
                record.back_image_filename,
                1 if record.reviewed_by_user else 0,
                now,
                now,
            ),
        )
        conn.execute(
            "UPDATE cards SET status = ?, confidence_score = ?, duplicate_flag = ?, updated_at = ? WHERE card_id = ?",
            (
                "needs_review" if record.confidence_score == "Low" else "processed",
                record.confidence_score,
                record.duplicate_flag,
                now,
                record.card_id,
            ),
        )


def row_to_record(row: Any) -> BusinessCardRecord:
    data = dict(row)
    data["low_confidence_fields"] = [part.strip() for part in (data.get("low_confidence_fields") or "").split(",") if part.strip()]
    data["reviewed_by_user"] = bool(data.get("reviewed_by_user"))
    data["date"] = data.get("created_at", "")[:10]
    data["time"] = data.get("created_at", "")[11:19]
    data["event_name"] = data.get("event_name") or ""
    fields = getattr(BusinessCardRecord, "model_fields", None) or getattr(BusinessCardRecord, "__fields__", {})
    return BusinessCardRecord(**{k: v for k, v in data.items() if k in fields})


def list_records(event_id: str) -> list[BusinessCardRecord]:
    with connection(db_path_for(event_id)) as conn:
        rows = conn.execute(
            """
            SELECT cr.*, e.name AS event_name
            FROM card_records cr
            JOIN events e ON e.event_id = cr.event_id
            WHERE cr.event_id = ?
            ORDER BY cr.created_at DESC
            """,
            (event_id,),
        ).fetchall()
    return [row_to_record(row) for row in rows]


def update_record(event_id: str, card_id: str, values: dict[str, Any]) -> BusinessCardRecord:
    allowed = {
        "name",
        "designation",
        "company",
        "business",
        "phone_primary",
        "phone_number",
        "mobile_number",
        "phone_extra",
        "fax_number",
        "country_code",
        "email",
        "website",
        "address",
        "city",
        "state",
        "country",
        "zip_code",
        "category",
        "social_media",
        "notes",
        "email1",
        "email2",
        "contact1",
        "contact2",
        "contact3",
    }
    updates = {key: value for key, value in values.items() if key in allowed}
    if not updates:
        records = [record for record in list_records(event_id) if record.card_id == card_id]
        if not records:
            raise KeyError(card_id)
        return records[0]
    assignments = ", ".join(f"{key} = ?" for key in updates)
    params = list(updates.values()) + [utc_now(), card_id]
    with connection(db_path_for(event_id)) as conn:
        conn.execute(
            f"UPDATE card_records SET {assignments}, reviewed_by_user = 1, updated_at = ? WHERE card_id = ?",
            params,
        )
        conn.execute("UPDATE cards SET status = 'reviewed', updated_at = ? WHERE card_id = ?", (utc_now(), card_id))
    records = [record for record in list_records(event_id) if record.card_id == card_id]
    if not records:
        raise KeyError(card_id)
    return records[0]


def reset_event_data(event_id: str) -> dict[str, int]:
    with connection(db_path_for(event_id)) as conn:
        counts = {
            "cards": conn.execute("SELECT COUNT(*) AS count FROM cards WHERE event_id = ?", (event_id,)).fetchone()["count"],
            "records": conn.execute("SELECT COUNT(*) AS count FROM card_records WHERE event_id = ?", (event_id,)).fetchone()["count"],
            "exports": conn.execute("SELECT COUNT(*) AS count FROM exports WHERE event_id = ?", (event_id,)).fetchone()["count"],
        }
        conn.execute("DELETE FROM duplicate_links WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM exports WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM cards WHERE event_id = ?", (event_id,))
    return counts


def find_duplicate_flag(event_id: str, *, email: str | None, phone: str | None, card_id: str) -> str:
    with connection(db_path_for(event_id)) as conn:
        if email:
            row = conn.execute(
                "SELECT card_id FROM card_records WHERE event_id = ? AND email = ? AND card_id != ? LIMIT 1",
                (event_id, email, card_id),
            ).fetchone()
            if row:
                return "Exact"
        if phone:
            row = conn.execute(
                "SELECT card_id FROM card_records WHERE event_id = ? AND phone_primary = ? AND card_id != ? LIMIT 1",
                (event_id, phone, card_id),
            ).fetchone()
            if row:
                return "Exact"
    return "No"
