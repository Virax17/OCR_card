# Decision Log

Status: Active  
Last updated: 2026-07-01

## Decisions

### 2026-07-01: Use Google Vision OCR Before Gemini Text Sorting

Decision:

Use Google Cloud Vision `DOCUMENT_TEXT_DETECTION` as the image-to-text layer. The app sends the front image and optional back image to Google Vision OCR, stores raw OCR output in SQLite and JSON audit files, extracts deterministic candidates, then sends only OCR text plus candidate hints to Gemini for field sorting.

Reason:

The Gemini-image-only path hallucinated business/company names, websites, emails, and country codes when card designs were stylized or visually busy. A dedicated OCR service gives a concrete transcript first, making the LLM a sorter instead of a visual guesser.

Impact:

- Normal upload mode is now `google_vision_ocr_gemini_text`.
- Google Vision service-account credentials are loaded from `GOOGLE_APPLICATION_CREDENTIALS`.
- Raw OCR is stored under `events/<event_id>/ocr/<card_id>_google_vision_ocr.json`.
- Gemini receives `front_text`, `back_text`, and rule-based candidate hints.
- Unsupported LLM values are still dropped if they are not present in OCR text.
- `/events/{event_id}/ocr-scan` can be used to debug OCR output without storing a card record.

### 2026-07-01: Use One Gemini Vision Call As Main Processing Path

Decision:

Superseded. Earlier runtime used Gemini Vision once per card upload. It sent the front image and optional back image together and stored the structured response.

Reason:

The local OCR engines struggled with stylized business cards, logos, design-heavy layouts, and icon-based labels. One image-model call gives better extraction accuracy and predictable API usage.

Impact:

- Normal UI upload no longer runs PaddleOCR, RapidOCR, or OCR ensemble logic.
- Each processed card consumes one Gemini request.
- SQLite remains the source of truth.
- Excel export still embeds front/back card images for manual verification.
- Local OCR modules may remain as historical reference, but they are not part of the runtime path.
- Superseded by the Google Vision OCR plus Gemini text sorting path above.

### 2026-07-01: Use PaddleOCR As Primary OCR Engine

Decision:

Superseded. Earlier plan was to use PaddleOCR as the primary OCR engine for business card image text extraction.

Reason:

PaddleOCR is actively maintained and supports scene OCR, document parsing, multilingual OCR, structured outputs, and local deployment options.

Impact:

- The backend should wrap PaddleOCR behind an internal OCR engine interface.
- The application should preserve OCR raw output for audit and tuning.
- The first implementation should avoid depending on cloud OCR.

### 2026-07-01: Use LLM Only As Fallback

Decision:

Superseded. Earlier plan was to use deterministic extraction first and call the LLM only for low-confidence or conflicting records.

Reason:

This keeps API cost low while still giving good accuracy on messy layouts.

Impact:

- Add confidence scoring early.
- Add a fallback trigger service.
- Add a UI action to manually improve a row.

### 2026-07-01: Support Two-Sided Cards As One Logical Record

Decision:

A front/back card pair should produce one business card record.

Reason:

Many business cards put addresses, alternate phone numbers, QR codes, or branch details on the back.

Impact:

- Data model needs `front_image_filename` and `back_image_filename`.
- OCR result needs side metadata.
- Merge logic must combine both sides before validation and Excel export.

### 2026-07-01: Use SQLite As V1 Source Of Truth

Decision:

Use event-local SQLite databases for V1. Excel remains the export format, not the primary storage.

Reason:

Review/edit workflows, duplicate detection, front/back pairing, audit data, and re-exporting are much safer with a database than with Excel-only storage.

Impact:

- Each event folder should contain an `app.db`.
- Excel should be generated from reviewed database records.
- OCR audit JSON can still be stored for debugging and tuning.
- A future PostgreSQL migration should keep the same logical schema.

## Pending Decisions

1. Default OCR language configuration.
2. Whether to enable LLM fallback by default.
3. Whether raw OCR appears in Excel or only audit JSON.
4. Exact UI pairing workflow for batch uploads.
