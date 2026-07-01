# PaddleOCR Business Card Scanner

Local web app for scanning one-sided or two-sided business cards, extracting contact data with PaddleOCR, storing records in SQLite, and exporting Excel.

## Run

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\init_sqlite.py
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

If RapidOCR install tries to overwrite OpenCV on Windows, install it this way after the base requirements:

```powershell
.\venv\Scripts\python.exe -m pip install onnxruntime
.\venv\Scripts\python.exe -m pip install rapidocr-onnxruntime --no-deps
```

Open:

```text
http://127.0.0.1:8000
```

## SQLite Console

```powershell
.\scripts\sqlite_console.bat
```

## OCR Modes

```text
Fast Local: PaddleOCR only
Balanced: PaddleOCR first, RapidOCR fallback when confidence/completeness is low
Accuracy: PaddleOCR + RapidOCR variants every time
```
