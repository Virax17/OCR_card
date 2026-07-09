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
GEMINI_API_KEY_4=...
GEMINI_API_KEY_5=...
GEMINI_API_KEY_6=...
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

## Mobile PWA / Deployment Note

The UI is a mobile-first installable PWA (bottom nav, full-screen scan viewfinder, offline capture queue). Camera access (`getUserMedia`) and the service worker only work over **HTTPS or `localhost`**. If the team accesses the app over a LAN IP at a trade show, terminate TLS in front of it (e.g. a Caddy/nginx reverse proxy with a self-signed cert, or a Tailscale HTTPS certificate) — plain `http://<lan-ip>:port` will not allow camera capture or installation on phones.

## Deploy Free on Render

The app deploys to [Render](https://render.com)'s free tier with no database server and no persistent disk. It ships a `render.yaml` blueprint and a `runtime.txt` (Python 3.12).

**Steps**

1. Push this repo to GitHub. `.env`, `events/`, `venv/`, `.cache/`, and `data/` are gitignored, so no secrets or local data are committed.
2. On Render: **New → Web Service** (or **New → Blueprint** to use `render.yaml`), and connect the GitHub repo. Render auto-detects Python and uses:
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. In the service's **Environment** settings, add the secrets (all marked `sync: false` in the blueprint, so you enter them in the dashboard):
   - `GEMINI_API_KEY` (plus `GEMINI_API_KEY_2` … `_6` for extra daily quota).
   - `GOOGLE_CREDENTIALS_JSON` — paste the **entire** service-account JSON as a single value (raw JSON or base64). This replaces the on-disk key file; no file needs to be uploaded. Leave `GOOGLE_APPLICATION_CREDENTIALS` unset on Render.
   - `EVENTS_ROOT` is set to `/tmp/events` by the blueprint (ephemeral scratch dir).
4. Deploy. The public URL is `https://<name>.onrender.com` — HTTPS is automatic, so camera capture and PWA install work out of the box.

**Free-tier tradeoffs (by design here)**

- **Ephemeral storage:** scanned images, the per-event SQLite databases, and Excel exports are stored on the instance's temp disk and **reset on every restart/redeploy and after ~15 minutes of inactivity**. There is no external database. **Download the Excel export before you leave** — treat each sitting as one session.
- **Cold starts:** the free service spins down after ~15 min idle; the next request takes ~1 minute to wake it.

If you later need data to survive restarts, that requires a paid tier with a persistent disk or an external store — out of scope for the free setup.

### Portable / other hosts

The same start command works on any container or Python host (Koyeb, Fly, a VPS, etc.). Set the same env vars. For Docker-based hosts, add a small `Dockerfile` that installs `requirements.txt` and runs the uvicorn start command on `$PORT`.

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

Gemini limits are project-level. If the six configured Gemini keys belong to six separate Google AI Studio projects and each project has the active free-tier limit of `20 RPD`, the local app-side estimate is:

```text
120 Gemini-sorted cards per Pacific-day reset window
30 requests per minute
1.5M input tokens per minute
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
