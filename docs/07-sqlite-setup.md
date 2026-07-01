# SQLite Setup

Status: Ready  
Last updated: 2026-07-01  
Related: [[06-database-plan]]

## Summary

SQLite is available through Python's standard `sqlite3` module. No separate SQLite installation is required for the first version of this app.

Verified runtime:

```text
SQLite 3.50.4
```

## Files Added

```text
app/storage/db.py
scripts/init_sqlite.py
scripts/sqlite_console.ps1
scripts/sqlite_console.bat
```

## Initialize Default Event Database

Run from the project root:

```powershell
& 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\init_sqlite.py
```

This creates:

```text
events/
  test_uploads/
    app.db
    metadata.json
    images/
    ocr/
    exports/
```

## Initialize A Custom Event

```powershell
& 'C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\init_sqlite.py `
  --event-id expo_2026 `
  --name "Expo 2026" `
  --date 2026-07-01 `
  --location "Mumbai" `
  --booth "A12"
```

## Tables Created

```text
schema_migrations
events
cards
card_sides
ocr_results
ocr_blocks
field_candidates
card_records
duplicate_links
exports
```

## Standalone SQLite CLI

Official download page:

```text
https://www.sqlite.org/download.html
```

The standalone SQLite command-line tools were installed here:

```text
C:\Tools\sqlite
```

Installed CLI:

```text
C:\Tools\sqlite\sqlite3.exe
```

Verified version:

```text
3.53.3
```

`C:\Tools\sqlite` was added to the user PATH, so new terminals should be able to run:

```powershell
sqlite3 --version
```

If an already-open terminal does not recognize `sqlite3`, close it and open a new terminal.

## Open An Interactive SQLite Console

From this project root, open the default OCR database:

```powershell
.\scripts\sqlite_console.bat
```

Or:

```powershell
.\scripts\sqlite_console.ps1
```

Open a specific database:

```powershell
.\scripts\sqlite_console.bat events\test_uploads\app.db
```

From any other project, use:

```powershell
sqlite3 path\to\your\database.db
```

Useful SQLite console commands:

```text
.tables
.schema card_records
.headers on
.mode column
SELECT * FROM events;
.quit
```

## Notes

- The database is event-local: `events/{event_id}/app.db`.
- Excel should be generated from `card_records`.
- Raw OCR should be stored in `ocr_results` and optionally mirrored as JSON files under `events/{event_id}/ocr/`.
- The setup script is safe to rerun. It creates missing tables and updates the event row.
