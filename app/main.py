from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    DEFAULT_EVENT_DATE,
    DEFAULT_EVENT_ID,
    DEFAULT_EVENT_NAME,
    EVENTS_ROOT,
    GEMINI_DAILY_REQUEST_LIMIT_PER_PROJECT,
    GEMINI_DAILY_TOKEN_LIMIT_PER_PROJECT,
    GEMINI_MINUTE_REQUEST_LIMIT_PER_PROJECT,
    GEMINI_PROJECT_COUNT,
    MAX_UPLOAD_BYTES,
)
from app.extraction.candidate_extractors import extract_candidates
from app.imaging.preprocess import preprocess_image
from app.llm.gemini_client import (
    gemini_key_labels,
    is_gemini_configured,
    structure_card_image,
    structure_card_text,
    structure_card_text_deterministic,
)
from app.llm.usage_monitor import provider_usage_snapshot, usage_snapshot
from app.models import BusinessCardRecord, EventIn, EventOut, ProcessingResult, UpdateRecordIn
from app.ocr.google_vision import extract_text as google_vision_extract_text
from app.ocr.google_vision import is_google_vision_configured
from app.storage.db import event_dir, initialize_event_database, new_id, utc_now
from app.storage.excel_writer import export_records
from app.storage.repositories import (
    create_card,
    ensure_event,
    find_duplicate_flag,
    get_event,
    insert_field_candidates,
    insert_ocr_result,
    insert_card_side,
    list_events,
    list_records,
    reset_event_data,
    update_record,
    upsert_card_record,
)

app = FastAPI(title="LLM Business Card Scanner")

STATIC_DIR = Path("static")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
async def startup() -> None:
    EVENTS_ROOT.mkdir(parents=True, exist_ok=True)
    initialize_event_database(
        EVENTS_ROOT,
        event_id=DEFAULT_EVENT_ID,
        name=DEFAULT_EVENT_NAME,
        date=DEFAULT_EVENT_DATE,
        location="Local",
        notes="Default event",
    )


@app.get("/")
async def index() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="UI is not available")
    return FileResponse(index_path)


@app.get("/manifest.webmanifest")
async def manifest() -> FileResponse:
    manifest_path = STATIC_DIR / "manifest.webmanifest"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Manifest is not available")
    return FileResponse(manifest_path, media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker() -> FileResponse:
    sw_path = STATIC_DIR / "sw.js"
    if not sw_path.exists():
        raise HTTPException(status_code=404, detail="Service worker is not available")
    return FileResponse(sw_path, media_type="application/javascript")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "processing_mode": "google_vision_ocr_gemini_text",
        "gemini_configured": is_gemini_configured(),
        "gemini_key_count": len(gemini_key_labels()),
        "google_vision_configured": is_google_vision_configured(),
        "storage_root": str(EVENTS_ROOT),
        "default_event_id": DEFAULT_EVENT_ID,
    }


@app.get("/events", response_model=list[EventOut])
async def api_list_events() -> list[EventOut]:
    return list_events()


def slugify(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
    return "_".join(part for part in slug.split("_") if part)[:48] or f"event_{date.today().isoformat()}"


@app.post("/events", response_model=EventOut)
async def api_create_event(payload: EventIn) -> EventOut:
    event_id = slugify(f"{payload.name}_{payload.date}")
    ensure_event(event_id, payload.name, payload.date, payload.location)
    event = get_event(event_id)
    if not event:
        raise HTTPException(status_code=500, detail="Event was not created")
    return event


async def read_upload(file: UploadFile | None) -> bytes | None:
    if file is None:
        return None
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"{file.filename} is larger than the upload limit")
    return data


def save_side_file(event_id: str, card_id: str, side: str, upload: UploadFile, image_bytes: bytes) -> str:
    suffix = Path(upload.filename or f"{side}.jpg").suffix.lower() or ".jpg"
    filename = f"{card_id}_{side}{suffix}"
    path = event_dir(EVENTS_ROOT, event_id) / "images" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)
    return filename


def save_llm_audit(event_id: str, card_id: str, fields: dict) -> None:
    audit_path = event_dir(EVENTS_ROOT, event_id) / "ocr" / f"{card_id}_llm_transcript.txt"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    evidence = fields.get("field_evidence")
    uncertain = fields.get("uncertain_fields")
    sections = [
        "FRONT TEXT",
        str(fields.get("front_text") or ""),
        "",
        "BACK TEXT",
        str(fields.get("back_text") or ""),
        "",
        "ALL VISIBLE TEXT",
        str(fields.get("all_visible_text") or ""),
        "",
        "FIELD EVIDENCE",
        json_dumps_pretty(evidence),
        "",
        "UNCERTAIN FIELDS",
        json_dumps_pretty(uncertain),
    ]
    audit_path.write_text("\n".join(sections), encoding="utf-8")


def save_ocr_audit(event_id: str, card_id: str, ocr_results: list) -> None:
    audit_path = event_dir(EVENTS_ROOT, event_id) / "ocr" / f"{card_id}_google_vision_ocr.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        result.model_dump() if hasattr(result, "model_dump") else result.dict()
        for result in ocr_results
    ]
    audit_path.write_text(json_dumps_pretty(payload), encoding="utf-8")


def json_dumps_pretty(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2) if value is not None else ""


def clear_event_artifacts(event_id: str) -> dict[str, int]:
    root = event_dir(EVENTS_ROOT, event_id).resolve()
    cleared: dict[str, int] = {}
    for folder_name in ("images", "ocr", "exports"):
        folder = (root / folder_name).resolve()
        if root not in folder.parents:
            raise HTTPException(status_code=400, detail="Invalid event artifact path")
        count = len([path for path in folder.rglob("*") if path.is_file()]) if folder.exists() else 0
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)
        cleared[folder_name] = count
    return cleared


def record_from_llm_fields(
    *,
    event_id: str,
    event_name: str,
    card_id: str,
    front_image_filename: str,
    back_image_filename: str | None,
    fields: dict,
) -> BusinessCardRecord:
    now = utc_now()
    low_confidence_fields = [
        field
        for field in ("name", "business", "phone_primary", "email")
        if not fields.get(field)
    ]
    confidence = "High" if not low_confidence_fields[:2] and (fields.get("email") or fields.get("phone_primary")) else "Medium"
    if len(low_confidence_fields) >= 3:
        confidence = "Low"
    return BusinessCardRecord(
        record_id=new_id("record"),
        card_id=card_id,
        event_id=event_id,
        date=now[:10],
        time=now[11:19],
        event_name=event_name,
        name=fields.get("name"),
        designation=fields.get("designation"),
        company=fields.get("company") or fields.get("business"),
        business=fields.get("business") or fields.get("company"),
        phone_primary=fields.get("phone_primary") or (f"+{fields.get('contact1')}" if fields.get("contact1") else None),
        phone_number=fields.get("phone_number") or fields.get("contact2"),
        mobile_number=fields.get("mobile_number") or fields.get("contact1"),
        phone_extra=fields.get("phone_extra"),
        fax_number=fields.get("fax_number") or fields.get("contact3"),
        country_code=fields.get("country_code"),
        email=fields.get("email") or fields.get("email1"),
        website=fields.get("website"),
        address=fields.get("address"),
        city=fields.get("city"),
        state=fields.get("state"),
        country=fields.get("country"),
        zip_code=fields.get("zip_code"),
        category=fields.get("category"),
        social_media=fields.get("social_media"),
        notes=fields.get("notes"),
        email1=fields.get("email1") or fields.get("email"),
        email2=fields.get("email2"),
        contact1=fields.get("contact1"),
        contact2=fields.get("contact2"),
        contact3=fields.get("contact3"),
        confidence_score=confidence,
        low_confidence_fields=low_confidence_fields,
        front_image_filename=front_image_filename,
        back_image_filename=back_image_filename,
    )


def process_card(event_id: str, front_upload: UploadFile, front_bytes: bytes, back_upload: UploadFile | None, back_bytes: bytes | None) -> ProcessingResult:
    event = get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not is_gemini_configured():
        raise HTTPException(status_code=503, detail="Gemini is not configured")
    if not is_google_vision_configured():
        raise HTTPException(status_code=503, detail="Google Vision OCR is not configured")

    card_id = create_card(event_id, processing_mode="google_vision_ocr_gemini_text")
    front_filename = save_side_file(event_id, card_id, "front", front_upload, front_bytes)
    back_filename = save_side_file(event_id, card_id, "back", back_upload, back_bytes) if back_upload and back_bytes else None

    try:
        sides = [("front", front_upload, front_bytes, front_filename)]
        if back_upload and back_bytes and back_filename:
            sides.append(("back", back_upload, back_bytes, back_filename))

        for side, upload, raw_bytes, filename in sides:
            _, width, height, quality, warnings = preprocess_image(raw_bytes)
            insert_card_side(
                event_id,
                card_id=card_id,
                side=side,
                filename=filename,
                content_type=upload.content_type,
                width=width,
                height=height,
                quality_score=quality,
                quality_warnings=warnings,
            )

        ocr_results = [google_vision_extract_text(front_bytes, "front", event_id=event_id)]
        if back_upload and back_bytes:
            ocr_results.append(google_vision_extract_text(back_bytes, "back", event_id=event_id))
        for result in ocr_results:
            insert_ocr_result(event_id, card_id, result)
        save_ocr_audit(event_id, card_id, ocr_results)

        front_ocr = next((result.raw_text for result in ocr_results if result.side == "front"), "")
        back_ocr = next((result.raw_text for result in ocr_results if result.side == "back"), None)
        if not front_ocr.strip() and not (back_ocr or "").strip():
            errors = "; ".join(result.error_message or "No text detected" for result in ocr_results)
            raise RuntimeError(f"Google Vision OCR did not return text: {errors}")

        candidates = extract_candidates(ocr_results)
        insert_field_candidates(event_id, card_id, candidates)
        candidate_hints = [
            candidate.model_dump() if hasattr(candidate, "model_dump") else candidate.dict()
            for candidate in candidates
        ]
        deterministic_fields = structure_card_text_deterministic(
            front_text=front_ocr,
            back_text=back_ocr,
            candidate_hints=candidate_hints,
        )
        fields = structure_card_text(
            event_id=event_id,
            front_text=front_ocr,
            back_text=back_ocr,
            candidate_hints=candidate_hints,
        )
        if not fields:
            fields = deterministic_fields
        save_llm_audit(event_id, card_id, fields)
        draft = record_from_llm_fields(
            event_id=event_id,
            event_name=event.name,
            card_id=card_id,
            front_image_filename=front_filename,
            back_image_filename=back_filename,
            fields=fields,
        )
        draft.duplicate_flag = find_duplicate_flag(event_id, email=draft.email, phone=draft.phone_primary, card_id=card_id)
        upsert_card_record(draft)
        return ProcessingResult(card=draft, status="needs_review" if draft.confidence_score == "Low" else "processed")
    except Exception as exc:
        fallback = record_from_llm_fields(
            event_id=event_id,
            event_name=event.name,
            card_id=card_id,
            front_image_filename=front_filename,
            back_image_filename=back_filename,
            fields={},
        )
        fallback.low_confidence_fields = ["all"]
        fallback.confidence_score = "Low"
        upsert_card_record(fallback)
        return ProcessingResult(card=fallback, status="error", error_message=str(exc))


@app.post("/events/{event_id}/cards", response_model=ProcessingResult)
async def upload_card(
    event_id: str,
    front: UploadFile = File(...),
    back: UploadFile | None = File(default=None),
) -> ProcessingResult:
    front_bytes = await read_upload(front)
    back_bytes = await read_upload(back)
    if front_bytes is None:
        raise HTTPException(status_code=400, detail="Front image is required")
    return process_card(event_id, front, front_bytes, back, back_bytes)


@app.post("/events/{event_id}/vision-scan")
async def vision_scan(
    event_id: str,
    front: UploadFile = File(...),
    back: UploadFile | None = File(default=None),
) -> dict:
    if not get_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    front_bytes = await read_upload(front)
    back_bytes = await read_upload(back)
    if front_bytes is None:
        raise HTTPException(status_code=400, detail="Front image is required")
    fields = structure_card_image(
        event_id=event_id,
        front_image=front_bytes,
        front_mime_type=front.content_type or "image/jpeg",
        back_image=back_bytes,
        back_mime_type=back.content_type if back else None,
    )
    if not fields:
        raise HTTPException(status_code=502, detail="Gemini Vision did not return structured fields")
    return {"event_id": event_id, "fields": fields}


@app.post("/events/{event_id}/ocr-scan")
async def ocr_scan(
    event_id: str,
    front: UploadFile = File(...),
    back: UploadFile | None = File(default=None),
) -> dict:
    if not get_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    if not is_google_vision_configured():
        raise HTTPException(status_code=503, detail="Google Vision OCR is not configured")
    front_bytes = await read_upload(front)
    back_bytes = await read_upload(back)
    if front_bytes is None:
        raise HTTPException(status_code=400, detail="Front image is required")
    results = [google_vision_extract_text(front_bytes, "front", event_id=event_id)]
    if back_bytes:
        results.append(google_vision_extract_text(back_bytes, "back", event_id=event_id))
    return {
        "event_id": event_id,
        "ocr_engine": "google_vision",
        "results": [
            result.model_dump() if hasattr(result, "model_dump") else result.dict()
            for result in results
        ],
    }


@app.get("/events/{event_id}/cards")
async def records(event_id: str) -> dict:
    return {"event_id": event_id, "records": list_records(event_id)}


@app.delete("/events/{event_id}/cards")
async def reset_cards(event_id: str) -> dict:
    if not get_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    database_counts = reset_event_data(event_id)
    artifact_counts = clear_event_artifacts(event_id)
    return {
        "event_id": event_id,
        "status": "reset",
        "deleted": {
            **database_counts,
            **artifact_counts,
        },
    }


def usage_response() -> dict:
    snapshot = usage_snapshot()
    gemini = provider_usage_snapshot("gemini")
    vision = provider_usage_snapshot("google_vision")
    return {
        "scope": "global",
        "provider": "multi",
        "daily_requests": snapshot.daily_requests,
        "minute_requests": snapshot.minute_requests,
        "daily_tokens_estimated": snapshot.daily_tokens,
        "daily_request_limit": snapshot.daily_request_limit,
        "minute_request_limit": snapshot.minute_request_limit,
        "daily_token_limit": snapshot.daily_token_limit,
        "allowed": snapshot.allowed,
        "gemini": {
            "daily_requests": gemini.daily_requests,
            "minute_requests": gemini.minute_requests,
            "daily_tokens_estimated": gemini.daily_tokens,
            "daily_request_limit": gemini.daily_request_limit,
            "minute_request_limit": gemini.minute_request_limit,
            "daily_token_limit": gemini.daily_token_limit,
            "key_count": len(gemini_key_labels()),
            "project_count": GEMINI_PROJECT_COUNT,
            "daily_request_limit_per_project": GEMINI_DAILY_REQUEST_LIMIT_PER_PROJECT,
            "minute_request_limit_per_project": GEMINI_MINUTE_REQUEST_LIMIT_PER_PROJECT,
            "daily_token_limit_per_project": GEMINI_DAILY_TOKEN_LIMIT_PER_PROJECT,
            "by_key": gemini.by_key or {},
        },
        "google_vision": {
            "daily_requests": vision.daily_requests,
            "minute_requests": vision.minute_requests,
            "monthly_units": vision.monthly_units,
            "minute_request_limit": vision.minute_request_limit,
            "free_units_monthly": vision.free_units_monthly,
            "estimated_cost_usd": vision.estimated_cost_usd,
        },
        "note": "Local app-side monitor only. Gemini active limits/credit are in Google AI Studio; Google Vision quota/billing are in Google Cloud Console.",
    }


@app.get("/llm-usage")
async def global_llm_usage() -> dict:
    return usage_response()


@app.get("/events/{event_id}/llm-usage")
async def llm_usage(event_id: str) -> dict:
    if not get_event(event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    return {**usage_response(), "event_id": event_id}


@app.patch("/events/{event_id}/cards/{card_id}")
async def patch_record(event_id: str, card_id: str, payload: UpdateRecordIn) -> dict:
    values = payload.model_dump(exclude_unset=True) if hasattr(payload, "model_dump") else payload.dict(exclude_unset=True)
    try:
        return {"record": update_record(event_id, card_id, values)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Card not found") from None


@app.get("/events/{event_id}/download")
async def download_excel(event_id: str) -> FileResponse:
    records_for_event = list_records(event_id)
    output = event_dir(EVENTS_ROOT, event_id) / "exports" / "contacts.xlsx"
    export_records(records_for_event, output)
    return FileResponse(output, filename=f"{event_id}_contacts.xlsx")


@app.get("/events/{event_id}/images/{filename}")
async def get_image(event_id: str, filename: str) -> FileResponse:
    path = event_dir(EVENTS_ROOT, event_id) / "images" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)
