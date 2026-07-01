# Decision Log

Status: Active  
Last updated: 2026-07-01

## Decisions

### 2026-07-01: Use PaddleOCR As Primary OCR Engine

Decision:

Use PaddleOCR as the primary OCR engine for business card image text extraction.

Reason:

PaddleOCR is actively maintained and supports scene OCR, document parsing, multilingual OCR, structured outputs, and local deployment options.

Impact:

- The backend should wrap PaddleOCR behind an internal OCR engine interface.
- The application should preserve OCR raw output for audit and tuning.
- The first implementation should avoid depending on cloud OCR.

### 2026-07-01: Use LLM Only As Fallback

Decision:

Do not send every card to an LLM. Use deterministic extraction first and call the LLM only for low-confidence or conflicting records.

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
