# Google Vision OCR Runtime

Status: Active  
Last updated: 2026-07-01

## Current Runtime Path

The app now processes uploaded business cards as:

```text
front/back image
  -> Google Vision DOCUMENT_TEXT_DETECTION
  -> store OCR text and blocks
  -> rule-based candidate extraction
  -> Gemini text-only field sorting
  -> transcript validation
  -> SQLite and Excel export
```

This keeps the LLM away from direct visual guessing during normal uploads. Gemini receives OCR text and candidate hints, then maps them into the Grid AI Excel fields.

## Configuration

Environment variables:

```text
GOOGLE_APPLICATION_CREDENTIALS=D:\tritorc\caramel-medley-500511-f3-b43018325a04.json
GOOGLE_VISION_MODEL=builtin/weekly
GOOGLE_VISION_TIMEOUT_SECONDS=60
GOOGLE_VISION_MINUTE_REQUEST_LIMIT=1800
GOOGLE_VISION_FREE_UNITS_MONTHLY=1000
GOOGLE_VISION_PRICE_PER_1000=1.50
```

The service-account JSON is not committed. Keep it outside git and rotate it if it is ever shared publicly.

## Google API Used

The app calls:

```text
POST https://vision.googleapis.com/v1/images:annotate
```

Feature:

```json
{
  "type": "DOCUMENT_TEXT_DETECTION",
  "model": "builtin/weekly"
}
```

`DOCUMENT_TEXT_DETECTION` is preferred over `TEXT_DETECTION` because business cards behave more like compact documents with many small text regions.

## Stored Audit Files

For each processed card:

```text
events/<event_id>/ocr/<card_id>_google_vision_ocr.json
events/<event_id>/ocr/<card_id>_llm_transcript.txt
```

The OCR JSON contains side-level raw text, confidence, runtime, and line blocks. The LLM transcript contains the final OCR text Gemini saw, field evidence, and uncertain fields.

## Debug Endpoint

OCR-only diagnostic:

```text
POST /events/{event_id}/ocr-scan
```

Upload `front` and optional `back` images. This returns Google Vision OCR output without creating a card record.

## Accuracy Rules

- OCR text is the source of truth.
- Gemini must cite exact OCR lines in `field_evidence`.
- Unsupported values are removed during post-processing.
- Email, website, and phone/contact fields are extracted again from the transcript by deterministic regex.
- If Vision OCR misses a stylized logo/company name, the app should leave `Business` blank rather than hallucinate.

## Usage Monitoring

The app records one Google Vision OCR unit per uploaded image side. A front/back card normally consumes two Vision OCR units.

`GET /llm-usage` includes:

- daily Vision OCR requests
- requests in the last minute
- current-month OCR units recorded by this app
- configured free monthly allowance
- estimated OCR cost after the free allowance

Current default app estimate:

```text
first 1000 OCR units/month = free
after free units = USD 1.50 per 1000 OCR units
```

This is local app-side usage only. Authoritative Google Cloud quota, billing, credits, and invoices must be checked in Google Cloud Console.
