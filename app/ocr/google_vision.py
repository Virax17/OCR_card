from __future__ import annotations

import base64
import binascii
import json
import time
from pathlib import Path
from typing import Any

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from app.config import (
    GOOGLE_APPLICATION_CREDENTIALS,
    GOOGLE_CREDENTIALS_JSON,
    GOOGLE_VISION_MODEL,
    GOOGLE_VISION_TIMEOUT_SECONDS,
)
from app.llm.usage_monitor import record_usage
from app.models import OCRSideResult, OCRTextBlock

VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
VISION_SCOPES = ["https://www.googleapis.com/auth/cloud-vision"]


def is_google_vision_configured() -> bool:
    if GOOGLE_CREDENTIALS_JSON:
        return True
    return bool(GOOGLE_APPLICATION_CREDENTIALS) and Path(GOOGLE_APPLICATION_CREDENTIALS).exists()


def _parse_credentials_json(raw: str) -> dict[str, Any]:
    """Accept the service-account JSON either as raw JSON or base64-encoded JSON."""
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        decoded = base64.b64decode(text).decode("utf-8")
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON is not valid JSON or base64-encoded JSON") from exc
    return json.loads(decoded)


def _load_credentials() -> service_account.Credentials:
    if GOOGLE_CREDENTIALS_JSON:
        info = _parse_credentials_json(GOOGLE_CREDENTIALS_JSON)
        return service_account.Credentials.from_service_account_info(info, scopes=VISION_SCOPES)
    return service_account.Credentials.from_service_account_file(
        GOOGLE_APPLICATION_CREDENTIALS,
        scopes=VISION_SCOPES,
    )


def _access_token() -> str:
    credentials = _load_credentials()
    credentials.refresh(Request())
    return credentials.token


def _bbox(vertices: list[dict[str, Any]] | None) -> list[dict[str, int]]:
    return [
        {"x": int(vertex.get("x", 0)), "y": int(vertex.get("y", 0))}
        for vertex in vertices or []
    ]


def _average_confidence(annotation: dict[str, Any]) -> float:
    values: list[float] = []
    for page in annotation.get("pages", []):
        if "confidence" in page:
            values.append(float(page["confidence"]))
        for block in page.get("blocks", []):
            if "confidence" in block:
                values.append(float(block["confidence"]))
            for paragraph in block.get("paragraphs", []):
                if "confidence" in paragraph:
                    values.append(float(paragraph["confidence"]))
                for word in paragraph.get("words", []):
                    if "confidence" in word:
                        values.append(float(word["confidence"]))
    return round(sum(values) / len(values), 4) if values else 0.0


def _line_blocks(annotation: dict[str, Any], raw_text: str, side: str, average_confidence: float) -> list[OCRTextBlock]:
    blocks: list[OCRTextBlock] = []
    line_index = 0
    for line in raw_text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        blocks.append(
            OCRTextBlock(
                text=clean,
                confidence=average_confidence,
                side=side,
                line_index=line_index,
                engine="google_vision",
                variant="document_text_detection",
                normalized_text=" ".join(clean.lower().split()),
            )
        )
        line_index += 1
    if blocks:
        return blocks

    for page in annotation.get("pages", []):
        for block in page.get("blocks", []):
            for paragraph in block.get("paragraphs", []):
                words = []
                confidences = []
                bbox = []
                for word in paragraph.get("words", []):
                    text = "".join(symbol.get("text", "") for symbol in word.get("symbols", []))
                    if text:
                        words.append(text)
                    if "confidence" in word:
                        confidences.append(float(word["confidence"]))
                    if not bbox:
                        bbox = _bbox((word.get("boundingBox") or {}).get("vertices"))
                line = " ".join(words).strip()
                if not line:
                    continue
                confidence = round(sum(confidences) / len(confidences), 4) if confidences else average_confidence
                blocks.append(
                    OCRTextBlock(
                        text=line,
                        confidence=confidence,
                        bbox=bbox,
                        side=side,
                        line_index=line_index,
                        engine="google_vision",
                        variant="document_text_detection",
                        normalized_text=" ".join(line.lower().split()),
                    )
                )
                line_index += 1
    return blocks


def extract_text(image_bytes: bytes, side: str, event_id: str | None = None) -> OCRSideResult:
    started = time.perf_counter()
    try:
        token = _access_token()
        payload = {
            "requests": [
                {
                    "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                    "features": [
                        {
                            "type": "DOCUMENT_TEXT_DETECTION",
                            "model": GOOGLE_VISION_MODEL,
                        }
                    ],
                }
            ]
        }
        response = requests.post(
            VISION_ENDPOINT,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=GOOGLE_VISION_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        item = (body.get("responses") or [{}])[0]
        if item.get("error"):
            message = item["error"].get("message", "Google Vision OCR error")
            raise RuntimeError(message)

        annotation = item.get("fullTextAnnotation") or {}
        raw_text = (annotation.get("text") or "").strip()
        average_confidence = _average_confidence(annotation)
        result = OCRSideResult(
            side=side,
            raw_text=raw_text,
            average_confidence=average_confidence,
            blocks=_line_blocks(annotation, raw_text, side, average_confidence),
            engine="google_vision",
            engine_version="v1",
            variant="document_text_detection",
            runtime_ms=int((time.perf_counter() - started) * 1000),
            status="ok" if raw_text else "skipped",
            error_message=None if raw_text else "No text detected",
        )
        if event_id:
            record_usage(
                event_id,
                provider="google_vision",
                model=GOOGLE_VISION_MODEL,
                purpose=f"document_text_detection_{side}",
                prompt_tokens=0,
                unit_count=1,
                status=result.status,
                error_message=result.error_message,
            )
        return result
    except Exception as exc:
        result = OCRSideResult(
            side=side,
            raw_text="",
            average_confidence=0.0,
            blocks=[],
            engine="google_vision",
            engine_version="v1",
            variant="document_text_detection",
            runtime_ms=int((time.perf_counter() - started) * 1000),
            status="error",
            error_message=str(exc)[:500],
        )
        if event_id:
            record_usage(
                event_id,
                provider="google_vision",
                model=GOOGLE_VISION_MODEL,
                purpose=f"document_text_detection_{side}",
                prompt_tokens=0,
                unit_count=1,
                status="error",
                error_message=result.error_message,
            )
        return result
