# LLM-Minimized Extraction Design

Status: Review draft  
Last updated: 2026-07-01  
Related: [[01-paddleocr-business-card-scanner-hld]], [[03-paddleocr-business-card-scanner-lld]]

## Goal

Use PaddleOCR for image-to-text extraction and use an LLM only as a low-frequency fallback for structuring ambiguous OCR text.

The system should avoid sending card images to an LLM by default. It should send only OCR text and field candidates.

## Why This Design

Business cards are short, but the layout can be messy. OCR extracts text, but deciding which line is the name, company, or designation can be ambiguous.

The cheapest reliable approach is:

```text
PaddleOCR image text
  -> deterministic extraction
  -> confidence scoring
  -> LLM fallback only for ambiguous cards
```

## LLM Call Triggers

Call the LLM only when one or more of these conditions is true:

1. No name candidate found.
2. No company candidate found.
3. No email and no phone found.
4. OCR average confidence is below threshold.
5. Required fields conflict between front and back.
6. Address extraction is uncertain.
7. More than one likely person name exists.
8. User clicks "Improve extraction" in the UI.

Recommended first thresholds:

```text
ocr_average_confidence < 0.78
required_fields_found < 3
name_confidence == low
company_confidence == low
front_back_conflict == true
```

## LLM Input

The LLM should receive:

```json
{
  "front_text": "...",
  "back_text": "...",
  "candidate_fields": {
    "emails": [],
    "phones": [],
    "websites": [],
    "possible_names": [],
    "possible_companies": [],
    "possible_businesses": [],
    "possible_designations": [],
    "possible_addresses": []
  },
  "rules": {
    "return_json_only": true,
    "do_not_invent_missing_values": true,
    "prefer_values_present_in_ocr": true
  }
}
```

## LLM Output Schema

```json
{
  "name": null,
  "designation": null,
  "company": null,
  "business": null,
  "phone_primary": null,
  "phone_extra": null,
  "email": null,
  "website": null,
  "address": null,
  "city": null,
  "state": null,
  "country": null,
  "zip_code": null,
  "category": null,
  "notes": null,
  "field_sources": {
    "name": "front",
    "email": "back"
  },
  "uncertain_fields": []
}
```

## Prompt Draft

```text
You are extracting contact details from OCR text from a business card.

Return only valid JSON matching the provided schema.
Use only values that appear in the OCR text or candidate fields.
Do not invent missing values.
If a field is not present, return null.
If front and back conflict, choose the more likely contact detail and list the field in uncertain_fields.
For category, choose exactly one of:
Engineering, Industrial Services, Certification, Supply Chain Management, Marine Contractors, Oil & Gas, Manufacturing, Construction, Logistics, Trading, Other.

OCR front:
{front_text}

OCR back:
{back_text}

Candidate fields:
{candidate_fields_json}
```

## Cost Control

1. Do not call LLM for cards where deterministic confidence is high.
2. Batch multiple low-confidence cards in one call only if response mapping is reliable.
3. Cache by hash of normalized OCR text.
4. Store LLM request/response metadata for debugging.
5. Add a per-event max LLM fallback count.
6. Add a UI option:
   - "Fast local mode"
   - "Balanced mode"
   - "Accuracy mode"

## Privacy Control

1. Prefer local OCR.
2. Send OCR text only, not images.
3. Allow disabling LLM fallback entirely.
4. Avoid logging API keys or full responses in normal application logs.
5. Store audit JSON locally under the event folder.

## Failure Behavior

If the LLM fails:

1. Keep deterministic extraction result.
2. Mark confidence as low or medium.
3. Show row in review table.
4. Do not block Excel export.
