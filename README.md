# Business Card OCR Scanner

Local FastAPI web app for scanning one-sided or two-sided business cards, reviewing extracted records, and exporting event-wise Excel files with card images for verification.

## Current Flow

```text
front/back card image
  -> Google Vision DOCUMENT_TEXT_DETECTION OCR
  -> deterministic email, phone, website, address, country hints
  -> Gemini text-only field sorting
  -> SQLite event database
  -> Excel export in the requested contacts format
```

The normal upload path uses Google Vision for OCR and one Gemini sorting call per card. Gemini does not receive the image in the normal flow, which keeps the LLM focused on classifying OCR text into fields instead of guessing from design elements.

## Excel Columns

Exports use this contact format:

```text
Date, Name, Designation, Business, Address, City, State, Country, Zip Code,
Website, Category, Social Media, Notes, Email1, Email2, Contact1, Contact2,
Contact3, Card
```

The `Card` column includes the card image for manual verification.

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and add your local keys and service-account path:

```text
GEMINI_API_KEY=...
GEMINI_API_KEY_2=...
GEMINI_API_KEY_3=...
GOOGLE_APPLICATION_CREDENTIALS=D:\path\to\service-account.json
```

Never commit `.env`, service-account JSON files, event databases, or card images.

## Run

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8022
```

Open:

```text
http://127.0.0.1:8022
```

## Events And Exports

- Create an event from the UI.
- Upload front image and optional back image for each card.
- Review and edit fields in the table when needed.
- Download the selected event Excel file from the UI.
- Use **Start New File** to clear the selected event's previous records and artifacts.

## API Usage Monitoring

The UI shows separate local counters for:

- Gemini requests, minute usage, estimated tokens, configured key/project count.
- Google Vision OCR requests, monthly OCR units, and estimated cost after the configured free allowance.

Gemini limits are project-level. If the three configured Gemini keys belong to three separate Google AI Studio projects and each project has the active free-tier limit of `20 RPD`, the local app-side estimate is:

```text
60 Gemini-sorted cards per Pacific-day reset window
15 requests per minute
750K input tokens per minute
```

Google Vision is counted per image side:

```text
1-sided card = 1 OCR unit
2-sided card = 2 OCR units
```

## SQLite Console

```powershell
.\scripts\sqlite_console.bat
```

## Useful Endpoints

```text
GET  /health
GET  /llm-usage
GET  /events
POST /events
POST /events/{event_id}/cards
POST /events/{event_id}/ocr-scan
GET  /events/{event_id}/download
```

See `docs/` for the HLD, LLD, implementation notes, Gemini usage notes, and Google Vision runtime notes.
