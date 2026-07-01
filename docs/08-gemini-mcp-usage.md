# Gemini API Key And Usage Monitoring

Status: First pass done  
Last updated: 2026-07-01  
Related: [[02-llm-minimized-extraction-design]]

## What Was Set Up

- `.env` stores the Gemini API key locally.
- `.env.example` documents required Gemini settings without secrets.
- `.agents/mcp_gemini_config.json` is an MCP-style config reference that points tools/agents to environment variables.
- `app/llm/gemini_client.py` wraps Gemini calls.
- `app/llm/usage_monitor.py` records local Gemini usage into SQLite.
- SQLite table `llm_usage` stores requests, estimated tokens, status, and errors.

## Important

The local monitor tracks usage made by this app only. Google says Gemini API rate limits are project-level and can vary by model/tier, so authoritative usage and active limits must still be checked in Google AI Studio.

Official docs:

- Rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Pricing: https://ai.google.dev/gemini-api/docs/pricing

## Local Limits

Configured in `.env`:

```text
GEMINI_DAILY_REQUEST_LIMIT=50
GEMINI_MINUTE_REQUEST_LIMIT=10
GEMINI_DAILY_TOKEN_LIMIT=100000
```

These are soft app-side guardrails, not Google-enforced quotas.

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
GET /events/{event_id}/llm-usage
GET /llm-usage
POST /events/{event_id}/vision-scan
```

Returns local Gemini usage counters. Because one Gemini API key is shared by the whole app, `/llm-usage` is the standard global usage endpoint and aggregates usage across event databases. The event-scoped URL is kept for compatibility but returns the same global counters.

`POST /events/{event_id}/vision-scan` accepts `front` and optional `back` image files. It sends images directly to Gemini Vision and returns structured JSON without storing a new card record.

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

The normal upload flow still minimizes API use:

```text
Fast Local / Balanced:
  local OCR ensemble first
  Gemini text fallback only when confidence is not High

Accuracy:
  local OCR ensemble first
  Gemini text fallback when confidence is not High
  Gemini Vision fallback only if key fields are still missing
```

Use `Accuracy` mode when a card has heavy design elements, unusual fonts, vertical text, glossy photos, or a busy background.
