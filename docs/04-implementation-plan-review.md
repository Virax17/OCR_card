# Implementation Plan For Review

Status: Implementation started  
Last updated: 2026-07-01  
Related: [[01-paddleocr-business-card-scanner-hld]], [[03-paddleocr-business-card-scanner-lld]]

## Important

This is a review plan only. No code implementation should begin until this plan is approved.

## Proposed Build Strategy

Build the system in small, testable phases:

1. Establish the PaddleOCR-first backend foundation.
2. Add two-sided card support.
3. Add deterministic extraction and confidence scoring.
4. Add minimal LLM fallback.
5. Add SQLite source-of-truth storage.
6. Add a clean basic UI.
7. Add Excel export and review flow.
8. Run real-card accuracy testing and tune.

## Phase 0: Confirm Workspace And Dependencies

Status: Done

Tasks:

- Confirm current workspace files and expected app structure.
- Confirm Python version.
- Confirm whether PaddleOCR and PaddlePaddle install cleanly on the target machine.
- Confirm whether CPU-only processing is acceptable for first build.
- Decide default event country for phone parsing.
- Decide whether LLM fallback should be enabled by default.

Acceptance:

- We know the exact runtime setup.
- PaddleOCR can be imported and initialized.
- A sample image can be processed locally.

Risk:

- PaddleOCR installation can be heavy on Windows depending on PaddlePaddle version.

## Phase 1: Project Structure

Status: Done

Tasks:

- Create or update FastAPI app structure.
- Add config module.
- Add Pydantic models.
- Add event storage folders.
- Add SQLite database module.
- Add health endpoint.

Acceptance:

- `GET /health` returns OCR and LLM configuration state.
- Event folders can be created.
- Event database can be initialized.

## Phase 2: PaddleOCR Engine

Status: Done

Tasks:

- Add `app/ocr/paddle_engine.py`.
- Initialize PaddleOCR once as a singleton.
- Return normalized OCR result:
  - raw text
  - line blocks
  - confidence
  - bounding boxes
  - side
- Add error handling for missing PaddleOCR install.

Acceptance:

- One sample business card image produces OCR text.
- OCR output is stored as JSON for audit.

## Phase 3: Image Preprocessing And Quality

Status: First pass done

Tasks:

- Add image decode support for JPG, PNG, HEIC.
- Add EXIF orientation fix.
- Add perspective crop.
- Add deskew.
- Add contrast enhancement.
- Add blur/brightness quality score.

Acceptance:

- Poor-quality images are processed, not rejected.
- Quality warnings are attached to card result.

## Phase 4: Two-Sided Card Model

Status: First pass done

Tasks:

- Add `card_id`.
- Add front image and optional back image fields.
- Add upload endpoint for one card:
  - `front`
  - `back optional`
- Add batch upload manifest design.
- Save images as:
  - `{card_id}_front.jpg`
  - `{card_id}_back.jpg`

Acceptance:

- Front-only cards process successfully.
- Front/back cards produce one merged record.

## Phase 5: Deterministic Field Extraction

Status: First pass done

Tasks:

- Extract email candidates.
- Extract phone candidates.
- Extract website candidates.
- Detect designation candidates.
- Detect company candidates.
- Detect name candidates.
- Detect address candidates.
- Merge candidates from front/back.

Acceptance:

- Common business cards extract at least email/phone/website without LLM.
- Field candidates include source side and confidence.

## Phase 6: Validation And Confidence

Status: First pass done

Tasks:

- Normalize email.
- Normalize phone using country hints.
- Normalize website.
- Compute field-level confidence.
- Compute card-level confidence.
- Mark low-confidence fields.

Acceptance:

- Valid email/phone/website fields become high confidence.
- Missing or conflicting fields are visible in the output.

## Phase 7: Minimal LLM Fallback

Status: Not started

Tasks:

- Add fallback trigger logic.
- Add prompt template.
- Add strict JSON parser.
- Add retry and timeout.
- Add cache by normalized OCR text hash.
- Add setting to disable LLM fallback.

Acceptance:

- LLM is not called for high-confidence deterministic cards.
- LLM is called for low-confidence cards only.
- If LLM fails, deterministic result still returns.

## Phase 8: SQLite Database Storage

Status: First pass done

Tasks:

- Add SQLite schema.
- Add repository layer.
- Persist events, cards, card sides, OCR results, candidates, final records, and duplicate links.
- Add migration/init logic.
- Store reviewed records as the source of truth.

Acceptance:

- A processed card can be reloaded after server restart.
- User edits persist.
- Duplicate detection can query previous cards.
- Excel can be regenerated from database rows.

## Phase 9: Excel Export

Status: First pass done

Tasks:

- Add Excel writer.
- Add final columns from HLD.
- Add formatting:
  - low confidence
  - duplicate
  - missing required fields
- Add audit sheet or JSON audit files.

Acceptance:

- Excel downloads successfully.
- Rows match reviewed records.
- Front/back filenames are included.

## Phase 10: Basic Good-Looking UI

Status: First pass done

Tasks:

- Build simple static UI or lightweight frontend.
- Add event selector.
- Add single card front/back upload.
- Add batch pair upload.
- Add results table.
- Add edit row modal or inline edit.
- Add front/back image preview.
- Add download Excel button.

Acceptance:

- User can scan one front-only card.
- User can scan one front/back card.
- User can edit results before export.
- UI is clean and responsive.

## Phase 11: Testing

Status: Not started

Tasks:

- Unit tests for extraction, validation, merging, confidence, duplicates, and Excel writer.
- Integration test for front-only upload.
- Integration test for front/back upload.
- Mock LLM fallback test.
- Manual test on real business card images.

Acceptance:

- Automated tests pass.
- At least 20 real sample cards are manually reviewed.
- Accuracy issues are captured in notes before tuning.

## Phase 12: Accuracy Tuning

Status: Not started

Tasks:

- Review failed OCR cases.
- Tune preprocessing.
- Tune extraction heuristics.
- Tune LLM fallback trigger thresholds.
- Add special handling for common Indian business card formats if needed.

Acceptance:

- Most normal cards extract contact fields correctly.
- Low-confidence cards are clearly marked for review.

## Open Questions For Review

1. Should the first version support only English cards, or English plus Hindi/regional languages?
2. Should LLM fallback be enabled by default or manually triggered?
3. Should Excel export include raw OCR text columns, or keep raw OCR only in JSON audit files?
4. Should batch upload assume file order as front/back pairs, or require user pairing in the UI?
5. Should we store records in event-local SQLite from the start, or keep only Excel/JSON?
6. What is the maximum expected batch size per event?

## Recommended Decisions

1. Start with English OCR using PaddleOCR.
2. Enable LLM fallback in balanced mode only.
3. Store raw OCR in JSON audit files and include optional Excel audit columns.
4. Build manual front/back pairing first because it avoids wrong records.
5. Use event-local SQLite from the start. Keep Excel as export and JSON for OCR audit.
6. Design for 500 images per event, but test first with 20 to 50 cards.

## Approval Checklist

- [ ] HLD reviewed.
- [ ] LLD reviewed.
- [ ] LLM fallback approach approved.
- [ ] UI flow approved.
- [ ] Excel columns approved.
- [ ] SQLite database approach approved.
- [ ] First implementation phase approved.
