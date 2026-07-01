from __future__ import annotations

import re
from difflib import SequenceMatcher
from statistics import mean

from app.models import OCRSideResult, OCRTextBlock

ENGINE_WEIGHTS = {
    "paddleocr": 1.0,
    "rapidocr": 0.92,
    "ensemble": 1.0,
}

VARIANT_WEIGHTS = {
    "original_normalized": 1.0,
    "contrast_enhanced": 0.98,
    "grayscale_upscaled": 0.95,
    "adaptive_threshold": 0.88,
}


def normalize_text(text: str) -> str:
    value = text.lower().strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[|:;,_-]+$", "", value).strip()
    return value


def _similar(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _pattern_boost(text: str) -> float:
    boost = 0.0
    if re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.I):
        boost += 0.2
    if re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", text):
        boost += 0.18
    if re.search(r"\b(?:https?://)?(?:www\.)?[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", text, re.I):
        boost += 0.16
    if any(word in text.lower() for word in ["road", "street", "floor", "area", "india", "uae", "dubai"]):
        boost += 0.1
    return boost


def _line_score(block: OCRTextBlock, agreement_count: int) -> float:
    engine_weight = ENGINE_WEIGHTS.get(block.engine or "", 0.75)
    variant_weight = VARIANT_WEIGHTS.get(block.variant or "", 0.9)
    agreement_boost = {1: 0.0, 2: 0.08, 3: 0.14}.get(min(agreement_count, 3), 0.18)
    return engine_weight * block.confidence * variant_weight + agreement_boost + _pattern_boost(block.text)


def merge_ocr_results(results: list[OCRSideResult], side: str) -> OCRSideResult:
    grouped: list[list[OCRTextBlock]] = []
    for result in results:
        if result.status != "ok":
            continue
        for block in result.blocks:
            block.normalized_text = normalize_text(block.text)
            target = None
            for group in grouped:
                if _similar(block.normalized_text, group[0].normalized_text or "") >= 0.88:
                    target = group
                    break
            if target is None:
                grouped.append([block])
            else:
                target.append(block)

    chosen: list[OCRTextBlock] = []
    for group in grouped:
        group.sort(key=lambda item: _line_score(item, len(group)), reverse=True)
        chosen.append(group[0])

    chosen.sort(key=lambda item: item.line_index)
    for index, block in enumerate(chosen):
        block.line_index = index

    return OCRSideResult(
        side=side,  # type: ignore[arg-type]
        raw_text="\n".join(block.text for block in chosen),
        average_confidence=mean(block.confidence for block in chosen) if chosen else 0.0,
        blocks=chosen,
        engine="ensemble",
        variant="merged",
        runtime_ms=sum(result.runtime_ms or 0 for result in results),
        status="ok",
    )

