from __future__ import annotations

from app.imaging.variants import image_variants
from app.models import OCRSideResult
from app.ocr import paddle_engine, rapid_engine
from app.ocr.merge import merge_ocr_results


def _error_result(side: str, engine: str, variant: str, exc: Exception) -> OCRSideResult:
    return OCRSideResult(
        side=side,  # type: ignore[arg-type]
        raw_text="",
        average_confidence=0.0,
        blocks=[],
        engine=engine,
        variant=variant,
        status="error",
        error_message=str(exc)[:500],
    )


def _needs_fallback(result: OCRSideResult, mode: str) -> bool:
    if mode == "fast_local":
        return False
    if mode == "accuracy":
        return True
    if result.average_confidence < 0.78:
        return True
    if len(result.blocks) < 4:
        return True
    raw = result.raw_text.lower()
    return not any(marker in raw for marker in ["www.", "http", "@"]) and not any(char.isdigit() for char in raw)


def run_ocr_ensemble(image_bytes: bytes, side: str, mode: str = "balanced") -> tuple[OCRSideResult, list[OCRSideResult]]:
    variants = image_variants(image_bytes)
    results: list[OCRSideResult] = []

    try:
        primary = paddle_engine.extract_text(variants["original_normalized"], side, "original_normalized")
    except Exception as exc:
        primary = _error_result(side, "paddleocr", "original_normalized", exc)
    results.append(primary)

    if _needs_fallback(primary, mode):
        for variant in ["contrast_enhanced"]:
            try:
                results.append(paddle_engine.extract_text(variants[variant], side, variant))
            except Exception as exc:
                results.append(_error_result(side, "paddleocr", variant, exc))

        if rapid_engine.is_rapid_available():
            for variant in ["contrast_enhanced", "grayscale_upscaled"]:
                try:
                    results.append(rapid_engine.extract_text(variants[variant], side, variant))
                except Exception as exc:
                    results.append(_error_result(side, "rapidocr", variant, exc))
        else:
            results.append(_error_result(side, "rapidocr", "contrast_enhanced", RuntimeError("RapidOCR is not installed.")))

    merged = merge_ocr_results(results, side)
    return merged, results

