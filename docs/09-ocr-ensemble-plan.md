# OCR Ensemble Plan

Status: First pass implemented  
Last updated: 2026-07-01  
Related: [[01-paddleocr-business-card-scanner-hld]], [[03-paddleocr-business-card-scanner-lld]], [[08-gemini-mcp-usage]]

## Goal

Improve extraction accuracy on design-heavy business cards by combining multiple OCR engines and merging their outputs intelligently.

The ensemble should improve recall without making every scan slow or expensive.

## Why Ensemble

Business cards often contain:

- curved or vertical text
- low contrast text over logos
- tiny text
- metallic or glossy backgrounds
- icon-heavy layouts
- multiple columns
- front/back split details

One OCR engine may miss text that another engine can read. PaddleOCR is strong and already integrated, but a second or third OCR pass can recover missed lines.

Official references:

- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- EasyOCR: https://github.com/JaidedAI/EasyOCR
- Tesseract: https://github.com/tesseract-ocr/tesseract
- RapidOCR: https://github.com/RapidAI/RapidOCR

## Engine Roles

### PaddleOCR

Primary engine.

Use for:

- default OCR
- multilingual scene text
- bounding boxes
- confidence scoring

Reason:

PaddleOCR is already installed and integrated. Its official project describes it as a lightweight OCR/document AI toolkit with structured outputs, scene OCR, and broad language support.

### RapidOCR

Fast local fallback.

Use for:

- second pass when Paddle confidence is low
- Windows-friendly ONNX inference
- quick recovery of missed text

Reason:

RapidOCR is designed around ONNXRuntime/OpenVINO-style OCR execution and is usually lighter than full EasyOCR.

### EasyOCR

Heavy fallback.

Use for:

- design-heavy cards
- unusual typography
- multilingual text
- cards where Paddle/Rapid disagree

Reason:

EasyOCR supports many languages and scripts, but can be heavier because of its PyTorch dependency and model downloads.

### Tesseract

High-contrast fallback.

Use for:

- black text on white backgrounds
- binarized/thresholded image variants
- clean printed text

Reason:

Tesseract can perform well on clean text but may struggle with modern graphic design unless preprocessing is good.

### Cloud OCR

Optional final OCR fallback.

Use only when:

- local engines fail
- user enables Accuracy Mode
- batch item is marked low confidence

Options:

- Google Vision OCR
- AWS Textract
- Azure OCR

## Recommended Execution Strategy

Do not run every engine on every card by default.

Use staged escalation:

```text
Stage 1:
  PaddleOCR on normalized image

Stage 2:
  PaddleOCR on preprocessing variants
  RapidOCR on best variant

Stage 3:
  EasyOCR and Tesseract on selected variants

Stage 4:
  Gemini Vision or cloud OCR fallback
```

## Processing Modes

### Fast Local Mode

Use when speed matters.

```text
PaddleOCR only
1 or 2 image variants
no LLM vision
```

### Balanced Mode

Recommended default.

```text
PaddleOCR primary
RapidOCR fallback
Gemini text structuring if low confidence
```

### Accuracy Mode

Use for difficult batches.

```text
PaddleOCR
RapidOCR
EasyOCR
Tesseract
Gemini vision fallback for failed cards
```

## Image Variants

For each side of a card, generate a small set of variants:

```text
original_normalized
contrast_enhanced
grayscale_upscaled
adaptive_threshold
inverted_if_dark
```

Do not blindly run all engines on all variants.

Recommended matrix:

```text
PaddleOCR:
  original_normalized
  contrast_enhanced

RapidOCR:
  contrast_enhanced
  grayscale_upscaled

EasyOCR:
  original_normalized
  grayscale_upscaled

Tesseract:
  adaptive_threshold
  grayscale_upscaled
```

## Normalized OCR Output

Every engine should return the same internal shape:

```python
OCRTextBlock:
    text: str
    confidence: float
    bbox: list
    side: "front" | "back"
    line_index: int
    engine: str
    variant: str

OCRSideResult:
    side: "front" | "back"
    engine: str
    variant: str
    raw_text: str
    average_confidence: float
    blocks: list[OCRTextBlock]
    runtime_ms: int
    status: "ok" | "error" | "skipped"
```

## Database Changes Needed

Current `ocr_results` can store multiple engine outputs, but we should add:

```text
variant
runtime_ms
status
error_message
```

Current `ocr_blocks` can store text and bbox, but we should add:

```text
engine
variant
normalized_text
```

Optional table:

```text
ocr_merge_audit
  merge_id
  card_id
  side
  text
  source_engines
  confidence
  chosen_for_fields
```

## Merge Strategy

### Step 1: Normalize Text

Normalize each OCR line:

```text
lowercase for matching
trim spaces
remove repeated punctuation
normalize common OCR confusions
normalize phone/email/website text
```

Examples:

```text
O -> 0 only inside phone numbers
l -> 1 only inside phone numbers
www, wwvv, wvw -> www when domain-like
```

### Step 2: Deduplicate Lines

Treat two lines as the same if:

```text
normalized text similarity >= 0.88
or exact email/phone/domain match
or bbox overlap is high and text similarity >= 0.75
```

### Step 3: Score Each Line

Line score:

```text
engine_weight
* OCR confidence
* variant_weight
* agreement_boost
* field_pattern_boost
```

Initial engine weights:

```text
PaddleOCR: 1.00
RapidOCR: 0.92
EasyOCR: 0.88
Tesseract: 0.78
Cloud OCR: 1.05
Gemini Vision: 1.00
```

Agreement boost:

```text
same line found by 2 engines: +0.08
same line found by 3 engines: +0.14
same line found by 4 engines: +0.18
```

Pattern boost:

```text
valid email: +0.20
valid phone: +0.18
valid website: +0.16
address-like line: +0.10
company suffix: +0.08
```

### Step 4: Build Merged Text

Sort final merged lines by:

```text
side
y position if available
x position if available
line_index fallback
```

Preserve a source map:

```json
{
  "text": "ABC Engineering Pvt Ltd",
  "sources": ["paddle:contrast", "rapid:upscaled"],
  "score": 0.94
}
```

## Field Extraction After Merge

Run field extraction on the merged text, not on a single engine output.

Fields:

```text
Date
Name
Designation
Business
Address
City
State
Country
Zip Code
Website
Category
```

Internal fields:

```text
country_code
phone_number
phone_primary
email
confidence_score
low_confidence_fields
```

## Confidence Gates

After Stage 1, continue to Stage 2 if:

```text
name missing
business missing
website missing
address missing
phone/email missing
ocr average confidence < 0.78
merged field completeness < 70%
```

After Stage 2, continue to Stage 3 if:

```text
required field completeness < 70%
or there are conflicts between engines
or user selected Accuracy Mode
```

After Stage 3, use Gemini Vision/cloud fallback if:

```text
required field completeness < 60%
or OCR text is very sparse
or image clearly contains text but OCR found little
```

## Efficiency Plan

1. Lazy-load engines only when needed.
2. Cache OCR output by:

```text
image_hash + side + engine + variant + engine_version
```

3. Avoid EasyOCR on every card.
4. Avoid Tesseract unless threshold/upscaled variants are available.
5. Use per-engine timeout.
6. Run front and back independently, then merge.
7. Use process isolation for heavy engines if memory becomes unstable.

Recommended timeouts:

```text
PaddleOCR: 30s
RapidOCR: 20s
EasyOCR: 45s
Tesseract: 15s
Cloud OCR: 20s
Gemini Vision: 30s
```

## Error Handling

Each engine should fail independently.

If one engine fails:

```text
record error in ocr_results
continue with other engines
do not fail the whole card
```

## Implementation Phases

### Phase 1: Internal Interface

Add:

```text
app/ocr/base.py
app/ocr/ensemble.py
app/ocr/merge.py
```

Define:

```python
class OCREngine:
    name: str
    available() -> bool
    extract(image_bytes, side, variant) -> OCRSideResult
```

### Phase 2: Preprocessing Variants

Add:

```text
app/imaging/variants.py
```

Generate and cache:

```text
original_normalized
contrast_enhanced
grayscale_upscaled
adaptive_threshold
```

### Phase 3: RapidOCR Fallback

Add RapidOCR as first fallback because it is likely lighter than EasyOCR.

Install:

```text
rapidocr-onnxruntime
```

### Phase 4: OCR Merge

Add:

```text
text normalization
line dedupe
agreement scoring
merged text output
source audit
```

### Phase 5: Tesseract CLI

Install standalone Tesseract.

Use only on:

```text
adaptive_threshold
grayscale_upscaled
```

### Phase 6: EasyOCR Heavy Fallback

Install EasyOCR only after RapidOCR/Tesseract are working.

Use only in Accuracy Mode or when required fields remain missing.

### Phase 7: Gemini Vision Fallback

Use only when:

```text
all local OCR attempts are weak
or user clicks Improve with Vision
```

Gemini Vision receives the front/back image and returns structured JSON.

### Phase 8: UI Controls

Add:

```text
processing mode selector
OCR audit drawer
engine result badges
retry with Accuracy Mode button
```

## Recommended First Build

Do this first:

```text
1. Add OCR engine interface.
2. Add preprocessing variants.
3. Add RapidOCR fallback.
4. Add merge/dedupe logic.
5. Store per-engine OCR results in SQLite.
6. Add UI indicator showing which engines contributed.
```

Do not install EasyOCR and Tesseract in the first ensemble pass unless RapidOCR is insufficient. This keeps the first upgrade focused and lower-risk.

## Implemented First Pass

Completed:

```text
app/ocr/ensemble.py
app/ocr/merge.py
app/ocr/rapid_engine.py
app/imaging/variants.py
```

Current engine behavior:

```text
Fast Local:
  PaddleOCR original_normalized

Balanced:
  PaddleOCR original_normalized
  if confidence/completeness is weak:
    PaddleOCR contrast_enhanced
    RapidOCR contrast_enhanced
    RapidOCR grayscale_upscaled

Accuracy:
  PaddleOCR original_normalized
  PaddleOCR contrast_enhanced
  RapidOCR contrast_enhanced
  RapidOCR grayscale_upscaled
```

The app stores each individual OCR result plus a final `ensemble / merged` OCR result in SQLite.

## Acceptance Criteria

1. A card can be processed with PaddleOCR only.
2. A low-confidence card automatically triggers RapidOCR.
3. OCR outputs from multiple engines are stored separately.
4. Merged OCR text is stored and used for field extraction.
5. The UI shows low-confidence fields and OCR engine sources.
6. Tests cover line dedupe, scoring, merge order, and field extraction.
7. No single engine failure breaks the card processing flow.

## Labeled Contact Number Handling

Business cards often print multiple numbers with short labels. The extractor treats these as different fields:

```text
T / Tel / Phone / Office / Landline -> phone_number
M / Mob / Mobile / Cell             -> mobile_number
F / Fax                             -> fax_number
```

`phone_primary` remains the normalized contact number used for duplicate matching and prefers `mobile_number` when available. `country_code` is inferred from the address/country text when a number is local. Indonesia/Jakarta cards map to `+62`.

The UI and Excel export now include:

```text
country_code
phone_number
mobile_number
fax_number
```

Excel export embeds the front and back card images into `Front Image` and `Back Image` columns so extracted values can be verified row by row.
