from app.models import OCRSideResult, OCRTextBlock
from app.ocr.merge import merge_ocr_results


def result(engine: str, variant: str, lines: list[tuple[str, float]]) -> OCRSideResult:
    blocks = [
        OCRTextBlock(
            text=text,
            confidence=confidence,
            side="front",
            line_index=index,
            engine=engine,
            variant=variant,
        )
        for index, (text, confidence) in enumerate(lines)
    ]
    return OCRSideResult(
        side="front",
        raw_text="\n".join(text for text, _ in lines),
        average_confidence=sum(conf for _, conf in lines) / len(lines),
        blocks=blocks,
        engine=engine,
        variant=variant,
    )


def test_merge_deduplicates_similar_lines() -> None:
    merged = merge_ocr_results(
        [
            result("paddleocr", "original_normalized", [("ABC Engineering Pvt Ltd", 0.91)]),
            result("rapidocr", "contrast_enhanced", [("ABC Engineering Pvt. Ltd", 0.86)]),
        ],
        "front",
    )
    assert merged.engine == "ensemble"
    assert merged.variant == "merged"
    assert len(merged.blocks) == 1
    assert "ABC Engineering" in merged.raw_text


def test_merge_keeps_unique_lines_from_fallback_engine() -> None:
    merged = merge_ocr_results(
        [
            result("paddleocr", "original_normalized", [("ABC Engineering Pvt Ltd", 0.91)]),
            result("rapidocr", "grayscale_upscaled", [("www.abceng.com", 0.9)]),
        ],
        "front",
    )
    assert "ABC Engineering Pvt Ltd" in merged.raw_text
    assert "www.abceng.com" in merged.raw_text

