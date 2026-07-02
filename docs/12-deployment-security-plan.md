# Deployment And Security Plan

Status: Draft for staged implementation  
Last updated: 2026-07-02  
Goal: Improve deployment readiness without changing the current scanner workflow.

## Non-Breaking Rule

The working scanner flow must remain:

```text
Upload card -> Google Vision OCR -> Gemini text sorting -> SQLite -> review table -> Excel export
```

Security and deployment features should wrap this flow, not replace it.

## Phase 1: Access Control

Current implementation:

```text
No application login is enabled.
```

Production upgrade options:

- Add login before public deployment.
- Protect UI, API routes, card image routes, and Excel download routes.
- Store credentials in deployment secrets, not in source control.
- Use HTTPS so credentials are encrypted in transit.

## Phase 2: Secret Management

Keep these out of git:

```text
.env
Google service-account JSON
Gemini keys
events/
data/
logs/
exports/
uploaded images
SQLite databases
```

Deployment target should inject secrets as environment variables.

## Phase 3: Storage And Backup

Current local storage:

```text
events/<event_id>/app.db
events/<event_id>/images/
events/<event_id>/ocr/
events/<event_id>/exports/
```

Deployment upgrade options:

- Small deployment: persistent server volume plus daily backups.
- Larger deployment: object storage for images/exports and managed database.

Backup minimum:

- SQLite event DBs
- uploaded images
- OCR audit JSON
- Excel exports

## Phase 4: Quota-Safe Bulk Processing

Current behavior:

- Single upload works immediately.
- Bulk upload processes cards sequentially through the same working endpoint.
- If Gemini quota is exhausted, a card can fail.

Production upgrade:

```text
Create job row -> process card -> if Gemini quota hit, mark quota_wait -> retry after midnight Pacific
```

This avoids losing a bulk batch when Gemini daily quota is reached.

## Phase 5: Monitoring

Add an admin/debug view for:

- failed OCR calls
- failed Gemini calls
- quota errors
- Excel export failures
- missing critical fields
- API usage counters

The current `/llm-usage` endpoint is local app-side monitoring only.

## Phase 6: Production Server

Recommended production shape:

```text
HTTPS reverse proxy -> FastAPI app -> persistent event storage
```

Use a process manager or Docker so the app restarts automatically after crashes or server reboot.

## Phase 7: Operational Checklist

Before real deployment:

- Enable HTTPS.
- Change the test password.
- Configure billing alerts in Google Cloud.
- Confirm Gemini project limits in AI Studio.
- Confirm Google Vision billing/quotas in Google Cloud Console.
- Test Excel export with JPG, PNG, JPEG, and WEBP uploads.
- Test a bulk batch near Gemini quota.
- Confirm backups restore correctly.
