"""One-off migration: copy legacy per-event SQLite data + local images into MongoDB.

The app now stores everything in MongoDB (see app/storage/mongo.py); this script
is a safety net for any data still sitting in the old ``EVENTS_ROOT/<event>/app.db``
files and ``images/`` folders (e.g. from local development). On Render the disk is
ephemeral so there is usually nothing to carry over — running this is harmless
either way and is idempotent (events/records are upserted by id).

Usage (from the repo root, with the same env as the app so MONGODB_URI is set):

    python -m deploy.migrate_sqlite_to_mongo             # migrate EVENTS_ROOT
    python -m deploy.migrate_sqlite_to_mongo /path/root  # migrate a specific root
"""

from __future__ import annotations

import sqlite3
import sys
from io import BytesIO
from pathlib import Path

from app.config import EVENTS_ROOT
from app.imaging.preprocess import compress_for_storage
from app.storage import mongo
from app.storage.repositories import (
    CARD_RECORDS,
    CARDS,
    DUPLICATE_LINKS,
    EVENTS,
    FIELD_CANDIDATES,
    OCR_RESULTS,
    ensure_indexes,
)


def _rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    try:
        return [dict(r) for r in conn.execute(f"SELECT * FROM {table}").fetchall()]
    except sqlite3.Error:
        return []


def _upload_images(event_dir: Path, event_id: str) -> int:
    bucket = mongo.get_gridfs()
    db = mongo.get_database()
    if bucket is None or db is None:
        return 0
    images_dir = event_dir / "images"
    if not images_dir.exists():
        return 0
    count = 0
    for image_path in images_dir.glob("*"):
        if not image_path.is_file():
            continue
        filename = f"{image_path.stem}.jpg"
        if db["fs.files"].find_one({"filename": filename}):
            continue  # already migrated
        stored = compress_for_storage(image_path.read_bytes())
        bucket.upload_from_stream(
            filename,
            BytesIO(stored),
            metadata={"event_id": event_id, "content_type": "image/jpeg", "migrated": True},
        )
        count += 1
    return count


def migrate_db(db_path: Path) -> dict[str, int]:
    db = mongo.get_database()
    if db is None:
        raise SystemExit("MongoDB is unavailable — set MONGODB_URI and try again.")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    counts: dict[str, int] = {}
    try:
        for event in _rows(conn, "events"):
            event["_id"] = event["event_id"]
            db[EVENTS].update_one({"_id": event["_id"]}, {"$set": event}, upsert=True)
        for card in _rows(conn, "cards"):
            card["_id"] = card["card_id"]
            card.setdefault("sides", [])
            db[CARDS].update_one({"_id": card["_id"]}, {"$set": card}, upsert=True)
        for rec in _rows(conn, "card_records"):
            rec["_id"] = rec.get("record_id") or rec["card_id"]
            low = rec.get("low_confidence_fields")
            if isinstance(low, str):
                rec["low_confidence_fields"] = [p.strip() for p in low.split(",") if p.strip()]
            rec["reviewed_by_user"] = bool(rec.get("reviewed_by_user"))
            db[CARD_RECORDS].update_one({"card_id": rec["card_id"]}, {"$set": rec}, upsert=True)
        for coll, table in ((OCR_RESULTS, "ocr_results"), (FIELD_CANDIDATES, "field_candidates"),
                            (DUPLICATE_LINKS, "duplicate_links")):
            docs = _rows(conn, table)
            if docs:
                for doc in docs:
                    key = next((doc[k] for k in ("ocr_result_id", "candidate_id", "duplicate_id") if k in doc), None)
                    if key is not None:
                        doc["_id"] = key
                    db[coll].update_one({"_id": doc.get("_id", key)}, {"$set": doc}, upsert=True)
            counts[table] = len(docs)
        counts["events"] = len(_rows(conn, "events"))
        counts["cards"] = len(_rows(conn, "cards"))
        counts["card_records"] = len(_rows(conn, "card_records"))
    finally:
        conn.close()

    event_id = db_path.parent.name
    counts["images"] = _upload_images(db_path.parent, event_id)
    return counts


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(EVENTS_ROOT)
    if not root.exists():
        print(f"No events root at {root} — nothing to migrate.")
        return
    ensure_indexes()
    total: dict[str, int] = {}
    for db_path in sorted(root.glob("*/app.db")):
        print(f"Migrating {db_path} ...")
        counts = migrate_db(db_path)
        for key, value in counts.items():
            total[key] = total.get(key, 0) + value
        print(f"  {counts}")
    print(f"Done. Totals: {total or 'nothing found'}")


if __name__ == "__main__":
    main()
