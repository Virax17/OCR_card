from __future__ import annotations

import os
import tempfile
import time
from statistics import mean

from app.models import OCRSideResult, OCRTextBlock

try:
    from rapidocr_onnxruntime import RapidOCR
except Exception:  # pragma: no cover
    RapidOCR = None

_ENGINE = None


def is_rapid_available() -> bool:
    return RapidOCR is not None


def _get_engine():
    global _ENGINE
    if RapidOCR is None:
        raise RuntimeError("RapidOCR is not installed.")
    if _ENGINE is None:
        _ENGINE = RapidOCR()
    return _ENGINE


def extract_text(image_bytes: bytes, side: str, variant: str = "original_normalized") -> OCRSideResult:
    temp_path = None
    started = time.perf_counter()
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp:
            temp.write(image_bytes)
            temp_path = temp.name
        raw_result, _ = _get_engine()(temp_path)
        blocks: list[OCRTextBlock] = []
        for index, item in enumerate(raw_result or []):
            bbox, text, confidence = item
            if hasattr(bbox, "tolist"):
                bbox = bbox.tolist()
            text = str(text or "").strip()
            if not text:
                continue
            blocks.append(
                OCRTextBlock(
                    text=text,
                    confidence=float(confidence or 0.0),
                    bbox=bbox,
                    side=side,  # type: ignore[arg-type]
                    line_index=index,
                    engine="rapidocr",
                    variant=variant,
                )
            )
        return OCRSideResult(
            side=side,  # type: ignore[arg-type]
            raw_text="\n".join(block.text for block in blocks),
            average_confidence=mean(block.confidence for block in blocks) if blocks else 0.0,
            blocks=blocks,
            engine="rapidocr",
            variant=variant,
            runtime_ms=int((time.perf_counter() - started) * 1000),
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

