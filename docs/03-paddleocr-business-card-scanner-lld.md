# PaddleOCR Business Card Scanner LLD

Status: Review draft  
Last updated: 2026-07-01  
Related: [[01-paddleocr-business-card-scanner-hld]], [[02-llm-minimized-extraction-design]]

## Backend Modules

Recommended Python package layout:

```text
app/
  main.py
  config.py
  models.py
  api/
    events.py
    cards.py
    exports.py
  events/
    event_manager.py
  imaging/
    preprocess.py
    quality.py
  ocr/
    paddle_engine.py
    result_normalizer.py
  extraction/
    candidate_extractors.py
    field_resolver.py
    front_back_merger.py
    confidence.py
  llm/
    fallback_structurer.py
    prompt_templates.py
  validation/
    validators.py
  duplicates/
    duplicate_check.py
  storage/
    db.py
    repositories.py
    json_store.py
    excel_writer.py
```

## API Design

### `GET /health`

Returns service health and installed OCR backend state.

Response:

```json
{
  "status": "ok",
  "paddleocr_available": true,
  "llm_configured": true,
  "storage_root": "events",
  "database": "sqlite"
}
```

### `POST /events`

Creates an event folder.

Request:

```json
{
  "name": "Trade Expo 2026",
  "date": "2026-07-01",
  "location": "Mumbai",
  "booth": "A12",
  "notes": "Optional"
}
```

### `GET /events`

Lists all events.

### `POST /events/{event_id}/cards`

Uploads one card with front and optional back.

Multipart fields:

```text
front: file
back: file optional
mode: fast_local | balanced | accuracy
```

### `POST /events/{event_id}/cards/batch`

Uploads many card pairs.

Recommended request shape:

```text
cards[0].front
cards[0].back
cards[1].front
cards[1].back
```

If browser support is awkward, accept all files and a JSON `manifest`:

```json
{
  "cards": [
    {
      "client_card_id": "1",
      "front_filename": "card1_front.jpg",
      "back_filename": "card1_back.jpg"
    }
  ]
}
```

### `PATCH /events/{event_id}/cards/{card_id}`

Saves reviewed user edits.

### `GET /events/{event_id}/download`

Downloads Excel export.

### `GET /events/{event_id}/cards`

Lists stored cards for review.

### `GET /events/{event_id}/cards/{card_id}`

Returns one stored card with front/back OCR audit details.

## Data Models

### `CardSide`

```python
class CardSide(BaseModel):
    side: Literal["front", "back"]
    filename: str
    content_type: str | None
    width: int | None
    height: int | None
    quality_score: str
```

### `OCRTextBlock`

```python
class OCRTextBlock(BaseModel):
    text: str
    confidence: float
    bbox: list[list[float]]
    side: Literal["front", "back"]
    line_index: int
```

### `OCRSideResult`

```python
class OCRSideResult(BaseModel):
    side: Literal["front", "back"]
    raw_text: str
    average_confidence: float
    blocks: list[OCRTextBlock]
```

### `FieldCandidate`

```python
class FieldCandidate(BaseModel):
    field: str
    value: str
    confidence: float
    source: Literal["front", "back", "merged", "llm"]
    evidence: str | None = None
```

### `BusinessCardRecord`

```python
class BusinessCardRecord(BaseModel):
    card_id: str
    event_id: str
    date: str
    time: str
    event_name: str
    name: str | None = None
    designation: str | None = None
    company: str | None = None
    phone_primary: str | None = None
    phone_number: str | None = None
    phone_extra: str | None = None
    country_code: str | None = None
    email: str | None = None
    website: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    zip_code: str | None = None
    category: str | None = None
    confidence_score: Literal["High", "Medium", "Low"]
    low_confidence_fields: list[str]
    duplicate_flag: str = "No"
    front_image_filename: str
    back_image_filename: str | None = None
    raw_ocr_front: str | None = None
    raw_ocr_back: str | None = None
    reviewed_by_user: bool = False
```

## Database LLD

Recommended first database: SQLite.

Database location:

```text
events/{event_id}/app.db
```

Why event-local SQLite:

- Easy backup by copying one event folder.
- No database server needed.
- Works well for a local web app.
- Keeps each event portable.
- Excel can be regenerated from reviewed rows.

Details: [[06-database-plan]]

Core tables:

```text
events
cards
card_sides
ocr_results
ocr_blocks
field_candidates
card_records
duplicate_links
exports
```

Repository modules:

```text
EventRepository
CardRepository
OCRRepository
RecordRepository
ExportRepository
```

Database should be the source of truth. Excel is generated from reviewed `card_records`.

## PaddleOCR Engine

### Initialization

Recommended first implementation:

```python
PaddleOCR(
    use_angle_cls=True,
    lang="en"
)
```

Later options:

- Select language per event.
- Use PP-OCRv6 models when the installed PaddleOCR version supports them.
- Add GPU configuration when deployment hardware supports it.

### Engine Contract

```python
class OCREngine:
    def extract(self, image_bytes: bytes, side: str) -> OCRSideResult:
        ...
```

The rest of the app should depend on the engine contract, not PaddleOCR directly. This keeps fallback engines or upgrades easy.

## Image Preprocessing

Pipeline:

```text
decode image
  -> EXIF orientation fix
  -> optional resize/upscale
  -> perspective crop
  -> deskew
  -> contrast enhancement
  -> sharpness check
  -> encode normalized JPG
```

Quality checks:

- blur score
- brightness score
- resolution score
- text area coverage

Quality should not block processing. It should warn and lower confidence.

## Field Extraction Logic

### Email

Regex-based candidate extraction:

```text
[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}
```

Validate with email validation library.

### Phone

Use phone regex candidates, then normalize with phone number parsing.

Country hint priority:

1. Event country if configured.
2. Parsed address country.
3. Default country setting.

The database stores phone information in separate fields:

```text
country_code
phone_number
phone_primary
```

`phone_primary` is the normalized international number. `phone_number` is the national number without the country code. Address text is used to infer `country_code` when the card prints a local phone number.

### Website

Detect:

- `https://...`
- `http://...`
- `www...`
- bare domains like `company.com`

Normalize to `https://...`.

### Name

Candidate heuristics:

- High-position text on front side.
- Human-name-looking lines.
- Not email, phone, website, address, or designation.
- Larger or prominent text if bounding boxes are available.

### Company

Candidate heuristics:

- Prominent non-person line.
- Near logo/top or below name.
- Contains business suffix terms:
  - Pvt Ltd
  - Ltd
  - LLC
  - Inc
  - LLP
  - Industries
  - Solutions
  - Technologies

### Designation

Candidate heuristics:

- Contains title keywords:
  - Founder
  - CEO
  - Director
  - Manager
  - Sales
  - Engineer
  - Consultant
  - Partner
  - Head
  - VP

### Address

Candidate heuristics:

- Lines containing street, city, state, zip, country, floor, road, industrial area.
- Lines near phone/email section.
- Back side often has address-only text.

## Front/Back Merge Logic

Merge rules:

1. Combine all candidates from both sides.
2. Prefer deterministic high-confidence fields over LLM fields.
3. Prefer front side for name, company, designation.
4. Prefer either side for email, phone, website based on validation success.
5. Prefer back side for address when front has no full address.
6. Store source side per field in audit JSON.
7. Flag conflicts for manual review.

## Confidence Scoring

Recommended scoring inputs:

```text
ocr confidence
field validation result
candidate source
front/back agreement
field type importance
image quality score
llm fallback used
```

Card-level confidence:

```text
High:
  email or phone valid
  name found
  company found
  OCR confidence acceptable

Medium:
  contact field valid
  at least name or company found

Low:
  no valid email/phone
  name and company missing
  OCR very low
```

## Duplicate Detection

Exact duplicate keys:

- email
- normalized phone

Fuzzy duplicate keys:

- name + company
- phone suffix + company
- email domain + name

Duplicate states:

```text
No
Exact
Possible
```

## Excel Writer

Workbook:

- Sheet 1: `Contacts`
- Sheet 2: `OCR Audit` optional

Formatting:

- Red fill for low confidence.
- Yellow fill for possible duplicates.
- Gray fill for missing required fields.
- Freeze header row.
- Auto filter enabled.

Excel export source:

- Read reviewed card rows from SQLite.
- Generate a fresh workbook on demand.
- Keep export history in the `exports` table.

## UI LLD

### Views

1. Scanner
2. Review
3. Records

### Scanner View

Controls:

- Event selector.
- Upload mode:
  - single card
  - batch pairs
- Front file input.
- Back file input.
- Process button.

### Review View

Table columns:

```text
Preview
Name
Designation
Company
Phone
Email
Website
Confidence
Duplicate
Actions
```

Actions:

- edit row
- view front/back image
- reprocess with LLM fallback
- mark reviewed

### Records View

- Event summary.
- Export download.
- Count of total, clean, low confidence, duplicates.

## Test Plan

Unit tests:

- email extraction
- phone extraction
- website extraction
- field merge
- confidence score
- duplicate detection
- Excel writer

Integration tests:

- single front-only card upload
- front/back card upload
- low-confidence LLM fallback path mocked
- Excel export

Manual QA:

- dark card
- shiny card
- vertical text
- two-sided address card
- multilingual card
- low-resolution phone image
