# Gemini API Key And Usage Monitoring

Status: First pass done  
Last updated: 2026-07-01  
Related: [[02-llm-minimized-extraction-design]]

## What Was Set Up

- `.env` stores Gemini API keys locally.
- `.env.example` documents required Gemini settings without secrets.
- `.agents/mcp_gemini_config.json` is an MCP-style config reference that points tools/agents to environment variables.
- `app/llm/gemini_client.py` wraps Gemini calls.
- `app/llm/usage_monitor.py` records local Gemini usage into SQLite.
- SQLite table `llm_usage` stores requests, estimated tokens, provider, key label, OCR units, local cost estimate, status, and errors.

## Important

The local monitor tracks usage made by this app only. Google says Gemini API rate limits are project-level and can vary by model/tier, so authoritative usage and active limits must still be checked in Google AI Studio.

Multiple Gemini API keys can be configured, but Gemini API rate limits are project-level, not API-key-level. If two keys belong to the same Google AI project, the second key does not increase true quota. The app can rotate to another key when a key/project returns a quota error, and it records requests by non-secret key label.

Official docs:

- Rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Pricing: https://ai.google.dev/gemini-api/docs/pricing

Reset timing:

- Gemini RPD resets at midnight Pacific time.
- Google documents RPM, TPM, and RPD as project-level limits.
- Active limits must be checked in Google AI Studio because model/tier limits can change.

## Local Limits

Configured in `.env`:

```text
GEMINI_API_KEY=...
GEMINI_API_KEY_2=...
GEMINI_API_KEY_3=...
GEMINI_PROJECT_COUNT=3
GEMINI_DAILY_REQUEST_LIMIT_PER_PROJECT=20
GEMINI_MINUTE_REQUEST_LIMIT_PER_PROJECT=5
GEMINI_DAILY_TOKEN_LIMIT_PER_PROJECT=250000
```

These are soft app-side guardrails, not Google-enforced quotas.

For three separate Google AI Studio projects with the active Gemini 2.5 Flash limits shown in AI Studio:

```text
Per project: 20 RPD, 5 RPM, 250K TPM
Combined local estimate: 60 Gemini-sorted cards/day, 15 requests/minute, 750K tokens/minute
```

The normal upload path uses one Gemini text-sorting request per card after Google Vision OCR. Therefore the practical Gemini-limited estimate is about 60 cards per Pacific-day reset window if each of the three projects has 20 RPD available. Google Vision has its own OCR quota and is tracked separately.

## Business Category Taxonomy

Gemini fallback must classify `Category` as exactly one of:

```text
Engineering
Industrial Services
Certification
Supply Chain Management
Marine Contractors
Oil & Gas
Manufacturing
Construction
Logistics
Trading
Other
```

## API Endpoints

```text
GET /events
POST /events
GET /events/{event_id}/llm-usage
GET /llm-usage
GET /events/{event_id}/download
POST /events/{event_id}/vision-scan
```

Returns local Gemini and Google Vision usage counters. `/llm-usage` is the standard global usage endpoint and aggregates usage across event databases. The event-scoped URL is kept for compatibility but returns the same global counters.

The usage response includes:

```text
gemini.daily_requests
gemini.minute_requests
gemini.daily_tokens_estimated
gemini.project_count
gemini.daily_request_limit_per_project
gemini.by_key
google_vision.daily_requests
google_vision.monthly_units
google_vision.estimated_cost_usd
```

`POST /events/{event_id}/vision-scan` accepts `front` and optional `back` image files. It sends images directly to Gemini Vision and returns structured JSON without storing a new card record.

`POST /events` creates a new event folder and SQLite database if needed. `GET /events/{event_id}/download` exports only the records from that selected event into the Grid AI `contacts` workbook format.

## Direct Image Scan Test

For cards where design elements break OCR, use Gemini Vision as a diagnostic or fallback path:

```powershell
.\venv\Scripts\python.exe scripts\gemini_vision_scan.py "data\front.jpeg" --back "data\back.jpeg" --event-id test_uploads
```

The script sends the front image, and optionally the back image, directly to Gemini and prints JSON using the same business-card fields as the app. Phone fields are label-aware:

The same test can be run through the local API:

```powershell
curl.exe -s -X POST http://127.0.0.1:8001/events/test_uploads/vision-scan -F "front=@data\front.jpeg" -F "back=@data\back.jpeg"
```

```text
phone_number  = office/telephone/landline labels such as T or Tel
mobile_number = mobile labels such as M, Mob, Mobile, or Cell
fax_number    = fax labels such as F or Fax
```

Tested on the Petrosea two-side sample. Gemini Vision identified the contact as Ahmad Sofryan Ajitama, separated `T +62 21 2977 0999`, `M +62 812 3667 8953`, and `F +62 21 2977 0988`, and inferred Indonesia / `+62`.

Prompt rules now explicitly tell Gemini that the company/business name is usually the top-most stylized brand/logo text on the front side of the card. Post-processing also cleans common LLM mistakes:

```text
email        -> must contain @ and a valid domain
website      -> normalized as a website/domain, not guessed from email unless separately printed
country_code -> inferred from address/country and printed phone prefixes, with phone prefix winning
phone fields -> stored without country code because country_code is a separate column
phone_primary -> normalized international number for duplicate matching
```

## App Fallback Behavior

The normal upload flow is now OCR-first:

```text
Upload card:
  send front image and optional back image to Google Vision OCR
  store OCR text
  extract deterministic field candidates
  call Gemini text sorter when quota allows
  fall back to OCR-only extraction if Gemini is unavailable or quota-limited
```

This avoids blank Excel rows when Gemini is quota-limited. New rows still get OCR-derived email, phone, country, website, and best-effort name/business/address fields.
