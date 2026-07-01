# LLM Business Card Scanner

Local web app for scanning one-sided or two-sided business cards with one Gemini Vision call per card, storing records in SQLite, and exporting Excel with card images for verification.

## Run

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\init_sqlite.py
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000
```

## SQLite Console

```powershell
.\scripts\sqlite_console.bat
```

## Processing

```text
Upload front image and optional back image.
The app sends both images together to Gemini Vision once.
No local PaddleOCR/RapidOCR processing is used in the normal upload flow.
```
