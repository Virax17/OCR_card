from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from statistics import mean

from app.models import OCRSideResult, OCRTextBlock

_CACHE_DIR = Path(os.getenv("PADDLE_PDX_CACHE_HOME", ".cache/paddlex")).resolve()
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(_CACHE_DIR))
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")

try:
    from paddleocr import PaddleOCR
except Exception:  # pragma: no cover - depends on local install
    PaddleOCR = None

_ENGINE = None


def is_paddle_available() -> bool:
    return PaddleOCR is not None


def _get_engine():
    global _ENGINE
    if PaddleOCR is None:
        raise RuntimeError("PaddleOCR is not installed. Install paddleocr and paddlepaddle to enable OCR.")
    if _ENGINE is None:
        _ENGINE = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=True,
        )
    return _ENGINE


def _normalize_result(raw_result, side: str, variant: str, runtime_ms: int | None = None) -> OCRSideResult:
    blocks: list[OCRTextBlock] = []
    lines = []
    if raw_result and isinstance(raw_result, list):
        first = raw_result[0]
        if isinstance(first, dict):
            texts = first.get("rec_texts") or first.get("texts") or []
            scores = first.get("rec_scores") or first.get("scores") or []
            boxes = first.get("rec_boxes")
            if boxes is None:
                boxes = first.get("dt_polys")
            if boxes is None:
                boxes = first.get("boxes")
            if boxes is None:
                boxes = []
            lines = [(boxes[index] if index < len(boxes) else [], (text, scores[index] if index < len(scores) else 0.0)) for index, text in enumerate(texts)]
        else:
            lines = first or []
    for index, item in enumerate(lines or []):
        bbox = item[0] if len(item) > 0 else []
        if hasattr(bbox, "tolist"):
            bbox = bbox.tolist()
        text_data = item[1] if len(item) > 1 else ("", 0.0)
        text = str(text_data[0] or "").strip()
        confidence = float(text_data[1] or 0.0)
        if not text:
            continue
        blocks.append(
            OCRTextBlock(
                text=text,
                confidence=confidence,
                bbox=bbox,
                side=side,  # type: ignore[arg-type]
                line_index=index,
                engine="paddleocr",
                variant=variant,
            )
        )
    return OCRSideResult(
        side=side,  # type: ignore[arg-type]
        raw_text="\n".join(block.text for block in blocks),
        average_confidence=mean(block.confidence for block in blocks) if blocks else 0.0,
        blocks=blocks,
        engine="paddleocr",
        engine_version=None,
        variant=variant,
        runtime_ms=runtime_ms,
    )


def extract_text(image_bytes: bytes, side: str, variant: str = "original_normalized") -> OCRSideResult:
    temp_path = None
    started = time.perf_counter()
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp:
            temp.write(image_bytes)
            temp_path = temp.name
        engine = _get_engine()
        raw_result = engine.ocr(temp_path)
        return _normalize_result(raw_result, side, variant, int((time.perf_counter() - started) * 1000))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
