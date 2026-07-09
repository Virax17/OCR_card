# UI Fable — Mobile-First "PDA" Redesign Plan

**Status:** Approved design plan — ready for implementation
**Date:** 2026-07-08
**Decisions locked:** Dashboard-first home · Full PWA (installable + offline queue) · Vanilla HTML/CSS/JS (no framework, no build step)
**Backend:** Existing FastAPI app (`app/main.py`) stays as-is except for 3 small additions listed in §9.

---

## 0. How to use this document (instructions for the implementing model)

- Implement in the **phase order of §11**. Do not skip ahead; each phase leaves the app working.
- Every screen spec in §5 lists: layout, exact element IDs, behavior, API calls, and edge cases. Use the IDs verbatim — some existing JS in `upload.js` is reused and keyed to IDs.
- Never invent new backend endpoints beyond the ones listed in §9. Everything else already exists in `app/main.py`.
- All CSS goes through the design tokens in §4. No hard-coded colors, spacing, or font sizes.
- After each phase, verify against the acceptance checklist for that phase (§11) before moving on.
- Test at 375×667 (small phone), 390×844 (modern phone), 768×1024 (tablet), and ≥1200 (desktop).

---

## 1. Current state audit

### What exists
- `static/index.html` (190 lines): single page, two-column layout — left "Add Cards" panel (Single / Bulk / Camera tabs), right "Event Records" table with 11 columns. Three `<dialog>` modals: edit record, create event, image preview.
- `static/upload.js` (662 lines): tab switching, file inputs, bulk queue, camera via `getUserMedia`, progress tickets, records table render, usage quota render, edit/save, Excel download.
- `static/styles.css` (782 lines): light theme, tokens in `:root`, **one** media query at 920px that stacks the columns.

### Why it fails on mobile
1. The 11-column records table is unusable on a phone — requires horizontal scrolling with tiny cells.
2. All controls (tabs, browse buttons, event select) are sized for mouse; touch targets are under 40px.
3. The top bar wraps into 3 rows on narrow screens (brand + select + two buttons).
4. Camera pane is a small box inside a panel instead of a full-screen viewfinder.
5. Edit dialog is a long vertical form in a small centered dialog — painful to scroll and type in on a phone.
6. No offline behavior: at a trade-show with bad Wi-Fi, every scan fails immediately.
7. No installability: user must open a browser and type a URL at a booth.

### What to keep
- The existing color palette and "scanner utility" personality (ink navy, teal, amber).
- All backend contracts: endpoints, field names, `BusinessCardRecord` shape.
- The existing single/bulk/camera capture concepts — re-housed, not redesigned functionally.

---

## 2. Design goals and principles

1. **PDA feel:** the phone experience should feel like a purpose-built handheld scanner device — full-screen, thumb-driven, no browser chrome once installed.
2. **One-thumb operation:** every frequent action reachable in the bottom 60% of the screen. Primary actions live in a bottom navigation bar and a floating scan button.
3. **Dashboard-first:** app opens to an event overview (counts, recent captures, quota health) with scanning one tap away.
4. **Cards, not tables (on mobile):** records render as stacked contact cards; the full table only appears at desktop widths.
5. **Never lose a capture:** offline queue means a photo taken with zero signal is stored and processed later.
6. **Progressive enhancement:** the same HTML works on desktop; layout upgrades via CSS at breakpoints. One codebase, no user-agent sniffing.
7. **Zero build step:** plain ES modules, plain CSS. A lower-capability model must be able to edit any file independently.

---

## 3. Information architecture

### 3.1 Navigation model (mobile, < 768px)

Persistent **bottom navigation bar** (`#bottomNav`), 4 destinations + center FAB:

| Position | ID | Icon (inline SVG) | Label | Screen |
|---|---|---|---|---|
| 1 | `#navHome` | house | Home | Dashboard (§5.2) |
| 2 | `#navRecords` | list | Records | Records list (§5.4) |
| center | `#navScanFab` | camera, raised circular FAB | Scan | Scan screen (§5.3) |
| 3 | `#navEvents` | calendar | Events | Event switcher sheet (§5.5) |
| 4 | `#navMore` | dots | More | Settings/usage (§5.6) |

- Bar height 64px + `env(safe-area-inset-bottom)` padding.
- FAB is 64px diameter, teal, elevated 8px above the bar, always visible except while the camera viewfinder is open.
- Active destination: teal icon + label; inactive: `--text-dim`.

### 3.2 Screen inventory

| # | Screen | Route (hash) | Mobile presentation | Desktop presentation |
|---|---|---|---|---|
| S1 | Dashboard | `#/home` | Full screen | Left column of 2-pane |
| S2 | Scan | `#/scan` | Full-screen viewfinder overlay | Modal panel |
| S3 | Records | `#/records` | Full-screen card list | Right column table |
| S4 | Record detail/edit | `#/records/{card_id}` | Bottom sheet | Right-side drawer |
| S5 | Event switcher / create | (sheet, no route) | Bottom sheet | Dropdown + dialog |
| S6 | More / usage / export | `#/more` | Full screen | Merged into dashboard |

Routing: a tiny hash router in `app-shell.js` — listen to `hashchange`, toggle `hidden` on `<section class="screen">` elements, update nav active state. No history libraries.

### 3.3 State object (extend the existing `state` in JS)

```
state = {
  eventId, events[],            // existing
  records[],                    // existing
  route,                        // "#/home" etc.
  online: navigator.onLine,     // updated by online/offline events
  pendingQueue: [],             // metadata of offline captures (mirror of IndexedDB)
  filters: { search: "", duplicatesOnly: false, category: null },
}
```

---

## 4. Design system

### 4.1 Tokens (extend `:root` in a new `static/css/tokens.css`)

Keep every existing token (`--ink`, `--teal`, `--amber`, etc.). Add:

```
--radius-lg: 16px;         /* cards, sheets */
--radius-full: 999px;      /* pills, FAB */
--space-1: 4px;  --space-2: 8px;  --space-3: 12px;
--space-4: 16px; --space-5: 24px; --space-6: 32px;
--touch-min: 48px;         /* minimum hit target */
--nav-height: 64px;
--shadow-1: 0 1px 3px rgba(20,33,61,.12);
--shadow-2: 0 4px 16px rgba(20,33,61,.16);
--shadow-fab: 0 6px 20px rgba(15,118,110,.35);
--font-sm: 13px; --font-base: 15px; --font-lg: 17px;
--font-xl: 22px; --font-xxl: 28px;
--duration: 180ms;         /* all transitions */
```

### 4.2 Typography
- Font stack unchanged: `"IBM Plex Sans", "Segoe UI", Arial, sans-serif`; mono for numbers/IDs.
- Base body size **15px** on mobile (was ~14). Inputs must be **≥16px** font-size to prevent iOS auto-zoom on focus.
- Screen titles: `--font-xl` weight 700. Section labels: `--font-sm` uppercase, letter-spacing .04em, `--text-dim`.

### 4.3 Touch and ergonomics rules (apply globally)
- Every tappable element: min 48×48px hit area (visual size may be smaller; pad with transparent padding).
- Vertical gap between adjacent tap targets: ≥ 8px.
- `touch-action: manipulation` on buttons to kill 300ms delay; `-webkit-tap-highlight-color: transparent` + custom `:active` state (scale .97 + darker bg).
- Respect safe areas: `padding: env(safe-area-inset-*)` on app bar, bottom nav, and full-screen overlays. Add `viewport-fit=cover` to the viewport meta tag.
- No hover-only affordances. Anything revealed on hover must also be visible or reachable by tap.

### 4.4 Breakpoints

| Name | Range | Layout |
|---|---|---|
| phone | < 600px | Single column, bottom nav, sheets |
| tablet | 600–1023px | Single column, wider cards (max-width 640px centered), bottom nav |
| desktop | ≥ 1024px | Two-pane: 380px left rail (dashboard/capture) + fluid records table. Bottom nav hidden; top bar shows nav links |

### 4.5 Motion
- Sheets slide up 240ms ease-out; overlay fades. Screens cross-fade 120ms. FAB press: scale .92.
- Wrap all animation in `@media (prefers-reduced-motion: no-preference)`.

---

## 5. Screen specifications

### 5.1 App shell (all screens)

**Top app bar** (`#appBar`, height 56px + safe-area top, background `--ink`, sticky):
- Left: brand mark "CS" (existing gradient tile, 32px) + current **event name** (`#appBarEvent`, tap opens event sheet §5.5, shows chevron-down).
- Right: connectivity pill `#netStatus` — hidden when online; shows "Offline · N queued" (amber pill) when offline or queue non-empty; tap navigates to `#/more` queue section.
- The old header controls (event select, new event, download) move into §5.2 and §5.5/§5.6. **Delete them from the header.**

**Toast/snackbar** (`#toast`): fixed above bottom nav, one at a time, auto-dismiss 3.5s, roles `status`/`alert`. Replaces the current inline `#message` div. Variants: success (green), error (red, persists until dismissed), info (ink).

**Skeletons:** every screen shows gray shimmer placeholders while its first fetch is in flight (records list: 5 card skeletons; dashboard stats: 3 stat skeletons).

### 5.2 S1 — Dashboard (home, default route)

Vertical scroll, `--space-4` page padding, sections top to bottom:

1. **Event hero card** (`#heroCard`): white card, radius `--radius-lg`, shadow-1.
   - Event name (`--font-xl` bold), date + location line (`--text-dim`).
   - Row of 3 stats (from `GET /events/{id}/cards` length + computed): **Cards** (total), **Today** (records with today's date), **Duplicates** (duplicate flag count). Numbers `--font-xxl` mono, labels `--font-sm`.
   - "Switch event" ghost button → event sheet.
2. **Primary action row**: full-width teal button `#dashScanBtn` "Scan a card" (56px tall, camera icon) → `#/scan`. Below it two half-width outline buttons: `#dashUploadBtn` "Upload photos" (opens the file picker directly, multiple; behaves as bulk §5.3.4) and `#dashExportBtn` "Export Excel" (existing `downloadExcel()`).
3. **Pending queue banner** (`#queueBanner`, only when `pendingQueue.length > 0`): amber card, "N scans waiting for network — will process automatically", button "Process now" (manual flush, §8.4).
4. **Recent captures** (`#recentList`): last 5 records as compact contact cards (§6.3 mini variant: thumbnail 44px, name, company, confidence dot). Header row with "View all →" linking `#/records`.
5. **API usage** (`#usageCard`): reuse existing `loadUsage()` data. Render as 2 horizontal meter bars (requests/day, tokens/day) with % and color state (teal < 70%, amber 70–90%, red > 90%). Collapse detail per-key info behind a `<details>` "Per-key detail".

Empty states: no event → hero shows "Create your first event" with create button; no records → recent section shows illustration-free empty card "No cards scanned yet — tap Scan to start".

Refresh: pull-down is NOT implemented (unreliable in plain JS); instead auto-refresh records/usage on route entry and after every successful processing.

### 5.3 S2 — Scan screen (full-screen viewfinder)

Opens as a **full-screen overlay** (`#scanScreen`, `position: fixed; inset: 0`, black background, z-index above nav). Bottom nav hidden while open.

**Layout, top to bottom:**
1. Top bar (translucent black): close ✕ (`#scanCloseBtn`, left, returns to previous route), title "Scan card", flash-less spacer right.
2. **Viewfinder**: `<video id="scanVideo">` fills the screen (`object-fit: cover`). Overlaid **card-aspect guide frame** — a 85.6:54 rounded rectangle, centered, ~88% of viewport width, drawn with a dimmed mask outside it (CSS `box-shadow: 0 0 0 100vmax rgba(0,0,0,.5)` on the guide div). Caption under frame: "Align card inside the frame".
3. **Side toggle** (`#sideToggle`): segmented control "Front / Back". Default Front. After a front capture, auto-advances to a **review step** (below) which offers "Add back side".
4. Bottom control bar (safe-area padded):
   - Left: gallery button (`#scanGalleryBtn`, 48px, opens `<input type="file" accept="image/*" multiple capture>`-less picker) for importing existing photos.
   - Center: **shutter** (`#shutterBtn`, 76px white ring, existing capture logic: draw video to canvas → `canvas.toBlob(jpeg, 0.9)`).
   - Right: **batch-mode toggle** (`#batchToggle`, stack icon + count badge).

**Capture flows:**

- **Single mode (default):** shutter → freeze frame → **review sheet** slides up over the frozen image with three buttons: `Retake` (ghost), `Add back side` (outline — returns to viewfinder with side toggle on Back), `Use photo` (primary teal). "Use photo" → enqueue for processing (§8.3) → toast "Processing…" → viewfinder resets for the next card. Processing is **non-blocking**: user keeps scanning while uploads run.
- **Batch mode:** every shutter press captures immediately (no review), thumbnail flies to the batch tray (`#batchTray`, horizontal thumbnail strip above the control bar, each thumb 56px with ✕ remove). A "Done (N)" button replaces the gallery button; tapping it enqueues all as front-only cards and closes the tray.
- **Gallery import:** selected files go through the same enqueue path as batch (front-only, one card per image) — this replaces the old "Bulk Upload" tab.

**Processing feedback:** a slim **status strip** (`#scanStatusStrip`) pinned above the control bar shows the live queue: "⏳ 2 processing · ✓ 5 done · ⚠ 1 failed". Tapping it opens the queue sheet (same component as §5.6 queue list). Failures never block the camera.

**Edge cases:**
- `getUserMedia` denied/unavailable → show fallback panel inside the scan screen: explanation + "Choose from gallery" button. (Note: camera requires HTTPS or localhost — record this in README deployment notes.)
- Back-side flow sends both blobs to the existing `POST /events/{id}/cards` (front + back form fields).
- On leaving the screen, stop all video tracks (`track.stop()`).

### 5.4 S3 — Records

**Header row:** title "Records", count badge, search input `#recordSearch` (full-width, 48px, debounced 250ms, client-side filter on name/company/email/phone), filter chips row: `All · Duplicates · Low confidence` (`confidence < 0.7`).

**Mobile list (`#recordsList`):** one **contact card** (§6.3) per record, ordered newest first:
- Left: 56px card thumbnail (tap → full-screen image viewer, existing `#imageDialog` restyled full-bleed with pinch-zoom via `touch-action: pinch-zoom` on the img).
- Middle: Name (bold, `--font-lg`), designation · company (one line, ellipsized), primary phone + email (one line, `--text-dim`, mono).
- Right column: confidence dot (green ≥ .85, amber ≥ .7, red below) and duplicate badge "DUP" (amber pill) when flagged.
- Tap anywhere on card → record detail sheet (S4).

**Desktop (≥1024px):** keep a table, but reduce to 7 columns: Card, Name, Company, Category, Phone, Email, Confidence — plus row-click for the detail drawer. Delete the old Contact2/Contact3/Duplicate columns from the table (data still visible in detail view).

**List virtualization:** not needed below ~500 records; render plainly. If `records.length > 500`, render in chunks of 100 on scroll (IntersectionObserver sentinel).

**Bulk header actions:** overflow menu (`#recordsMenu`, kebab icon): "Refresh", "Export Excel", "Reset event data…" (moves the dangerous reset out of primary UI; confirm dialog requires typing the event name).

### 5.5 S4 — Record detail + edit (bottom sheet)

Bottom sheet (`#recordSheet`, §6.2), 92% max height, drag-handle bar, scrollable body:

1. **Header:** card image (16:10, full sheet width, tap to zoom), name `--font-xl`, designation + company subtitle, duplicate warning banner if flagged.
2. **Quick actions row** — this is the PDA payoff; 4 circular 52px buttons:
   - `Call` → `href="tel:{phone_primary}"` (hidden if no phone)
   - `Email` → `mailto:{email1}` (hidden if none)
   - `Website` → opens `website` in new tab, prefix `https://` if missing
   - `Save contact` → generate a **vCard 3.0** blob client-side (N, ORG, TITLE, TEL, EMAIL, URL, ADR, NOTE) and trigger download `{name}.vcf`. Pure JS, no backend.
3. **Field list, view mode:** grouped rows (label small/dim above value): Identity (name, designation, company, business, category) · Contact (phones ×3, emails ×2, fax) · Location (address, city, state, country, zip) · Web (website, social) · Notes. Empty fields hidden in view mode.
4. **Edit mode:** "Edit" button in sheet header toggles all rows to inputs (all fields shown, including empty). Field IDs keep the existing `editName`, `editCompany`, etc. so `saveEdit()` logic ports directly. `inputmode="tel"` on phones, `type="email"` on emails, `autocapitalize="words"` on name. Sticky footer inside sheet: Cancel / Save (Save → existing `PATCH /events/{id}/cards/{card_id}`, optimistic UI update, toast on success/fail).

### 5.6 S5 — Event switcher & create (bottom sheet)

Sheet `#eventSheet` opened from app bar title, dashboard, or nav:
- List of events (`GET /events`), each row 56px: name bold, date · location dim, checkmark on current. Tap → switch (`state.eventId`, reload records/usage, toast "Switched to {name}").
- Sticky bottom: "＋ New event" → expands an inline form inside the same sheet (Name required, Date required default today, Location optional). Submit → existing `POST /events` → switch to it. Keep IDs `eventName`, `eventDate`, `eventLocation`.

### 5.7 S6 — More screen

Plain list sections:
1. **Offline queue:** list of pending captures (thumbnail, event, captured time, status chip: waiting / uploading / failed+Retry). "Process all now" button. Empty state "Queue is empty".
2. **API usage:** same component as dashboard, always expanded.
3. **Data:** Export Excel (current event) · Reset event data (danger, typed confirmation).
4. **System:** health status from `GET /health` (Gemini configured, Vision configured, mode), app version string, "Install app" button (captures `beforeinstallprompt`, hidden if installed or unsupported).

---

## 6. Component library (build once in `static/css/components.css`)

### 6.1 Buttons
- `.btn` base: 48px min height, radius `--radius-full` for primary/FAB and `--radius` for others, `--font-base` weight 600.
- Variants (keep existing class names so old JS keeps working): `.primary` teal solid, `.outline`, `.ghost`, `.danger`. Full-width modifier `.block`.
- Disabled: 40% opacity + `pointer-events: none`.

### 6.2 Bottom sheet (`.sheet`)
- Implemented with `<dialog>` (already used) restyled: on mobile, `margin: auto auto 0`, full width, `border-radius: var(--radius-lg) var(--radius-lg) 0 0`, slide-up animation, `max-height: 92dvh`, internal scroll. Drag-handle: 36×4px gray bar, centered (visual only — closing is via ✕ button and backdrop tap; do not implement drag-to-dismiss).
- On desktop (≥1024px): same dialogs render as centered modals (max-width 560px) or right drawer for the record sheet (`.sheet--drawer`: fixed right, width 420px, full height).
- Backdrop: `::backdrop` rgba(20,33,61,.45).

### 6.3 Contact card (`.contact-card`)
White, radius `--radius-lg`, shadow-1, padding `--space-4`, flex row, 12px gap. Mini variant `.contact-card--mini` (dashboard): 44px thumb, single-line meta. Skeleton variant `.contact-card--skeleton`.

### 6.4 Chips (`.chip`)
32px pill, outline default, teal-filled when active. Used for record filters and status labels.

### 6.5 Meter bar (`.meter`)
Track 8px gray, fill teal/amber/red by threshold, label row above (name left, "used / limit · %" right, mono).

### 6.6 Toast (`#toast`) — see §5.1.

### 6.7 Icons
Inline SVG only (24px viewBox, `stroke="currentColor"`, stroke-width 2). Define once as `<symbol>`s in a hidden SVG sprite at the top of `index.html`; reference with `<svg><use href="#icon-camera"/></svg>`. Needed set: house, list, camera, calendar, dots, close, chevron-down, search, phone, mail, globe, download, contact, edit, trash, refresh, wifi-off, image, stack, check, warning.

---

## 7. Desktop adaptation (≥1024px)

- Bottom nav hidden. App bar gains inline nav links (Home / Records / More) and the Scan button.
- Grid: `240px→380px` left rail (event hero, action buttons, queue banner, usage) + main area (records table). Scan opens as a centered modal with the same viewfinder component.
- Record detail uses the drawer variant. Everything else identical — same DOM, CSS-only changes.

---

## 8. PWA specification

### 8.1 Manifest — new file `static/manifest.webmanifest`
```
name: "CardScan", short_name: "CardScan",
start_url: "/", scope: "/", display: "standalone",
orientation: "portrait", theme_color: "#14213d", background_color: "#f7f8fa",
icons: 192px + 512px PNG (+ maskable variants)
```
Icons: generate simple "CS" gradient-tile PNGs (teal→amber on ink) with a small script or canvas export; store in `static/icons/`. Link manifest + `theme-color` meta + apple-touch-icon in `index.html`.

### 8.2 Service worker — new file `static/sw.js`, served at root scope
- **Precache** (cache-first, versioned cache name `cardscan-v1`): `/`, all `/static/css/*`, `/static/js/*`, manifest, icons.
- **Runtime:**
  - `GET /events`, `/events/{id}/cards`, `/llm-usage`, `/health` → **network-first, fall back to cache** (stale data beats no data at a venue).
  - `GET /events/{id}/images/*` → cache-first (immutable).
  - **Never cache** POST/PATCH/DELETE or `/download`.
- On activate: delete old cache versions. Bump the version string on every deploy.
- Registration in `app-shell.js`: `navigator.serviceWorker.register('/sw.js')`.

### 8.3 Offline capture queue (the core PDA feature)
- **Storage:** IndexedDB, db `cardscan`, store `captureQueue` keyed by autoincrement id. Record: `{ eventId, frontBlob, backBlob|null, capturedAt, attempts, status: "pending"|"uploading"|"failed" }`. Blobs stored directly (IndexedDB supports Blob).
- **Enqueue path (always used, even online):** every capture → write to IndexedDB first → then attempt upload. On success delete the row. This makes online/offline one code path and survives tab kills mid-upload.
- **Upload worker (in-page, `queue.js`):** processes queue serially (one card at a time — the backend pipeline is rate-limited by Gemini quotas). Triggers: app start, `online` event, after each enqueue, "Process now" buttons. Exponential backoff on failure (10s → 30s → 2m, max 5 attempts, then status `failed` with manual Retry).
- **UI hooks:** queue count feeds `#netStatus`, `#queueBanner`, scan status strip, More-screen list. Update via a tiny pub/sub (`queueChanged` CustomEvent on `window`).
- **Do not** use Background Sync API as the primary mechanism (poor iOS support); the in-page worker is primary, Background Sync optional enhancement later.

### 8.4 Connectivity UX rules
- `online`/`offline` listeners update `state.online` + `#netStatus` pill.
- When offline: scan keeps working fully (that's the point); records/dashboard show cached data with a dim "Showing offline data" line; Export and Reset buttons disabled with tooltip/toast "Requires connection".

---

## 9. Backend changes (the ONLY ones allowed)

| # | Change | Detail |
|---|---|---|
| 1 | `GET /manifest.webmanifest` | `FileResponse("static/manifest.webmanifest", media_type="application/manifest+json")` |
| 2 | `GET /sw.js` | `FileResponse("static/sw.js", media_type="application/javascript")`. Must be served from root path so the SW scope covers `/`. (Alternative: keep at `/static/sw.js` + `Service-Worker-Allowed: /` header — root route is simpler; use it.) |
| 3 | `GET /static/icons/*` | Covered by existing static mount — just add the files. |

Everything else (`/events`, `/events/{id}/cards` POST/GET/PATCH/DELETE, `/download`, `/llm-usage`, `/health`, `/events/{id}/images/{filename}`) is used as-is. **No schema, model, or pipeline changes.**

Deployment note for README: camera + service worker require **HTTPS** (or localhost). If the team accesses the app over LAN IP, terminate TLS (e.g., caddy/nginx self-signed or tailscale) — flag this, don't solve it in this project.

---

## 10. File plan

```
static/
  index.html            REWRITE — app shell + all screens/sheets (single file, ~450 lines)
  manifest.webmanifest  NEW
  sw.js                 NEW
  icons/                NEW (icon-192.png, icon-512.png, maskable variants)
  css/
    tokens.css          NEW  — §4.1 variables + resets + typography
    components.css      NEW  — §6 components
    screens.css         NEW  — per-screen layout + breakpoints
  js/  (ES modules, loaded via <script type="module" src="/static/js/app-shell.js">)
    app-shell.js        NEW  — router, nav, toast, online status, SW registration, boot
    api.js              NEW  — fetchJson + all endpoint wrappers (extract from upload.js)
    scan.js             NEW  — viewfinder, capture, batch tray, review sheet
    queue.js            NEW  — IndexedDB queue + upload worker (§8.3)
    records.js          NEW  — list render, search/filter, detail sheet, edit, vCard
    dashboard.js        NEW  — hero stats, recent list, usage meters
    events.js           NEW  — event sheet, switch, create
  styles.css            DELETE after migration (port needed rules into css/*)
  upload.js             DELETE after migration (logic redistributed above)
```

Migration rule for the implementing model: move logic function-by-function from `upload.js` into the new modules; do not rewrite working logic (e.g., `formatPhoneForDisplay`, `escapeHtml`, quota math) — copy it.

---

## 11. Implementation phases with acceptance criteria

### Phase 1 — Shell & navigation (no feature changes)
Build tokens.css/components.css, new index.html shell with app bar + bottom nav + 4 screen sections + hash router + toast. Old panels temporarily mounted inside Home/Records screens so nothing breaks.
**Accept:** app loads; nav switches screens on phone; desktop shows 2-pane; all old flows (upload, records, edit, export) still function; every tap target ≥48px; no horizontal scroll at 375px.

### Phase 2 — Records experience
Contact-card list, search + filter chips, record detail sheet with quick actions + vCard, edit-in-sheet, restyled image viewer, kebab menu with reset confirmation.
**Accept:** on a phone, a record can be found via search, called via tel: link, saved as .vcf, and edited — all without pinch-zoom; desktop table reduced to 7 columns; reset requires typed confirmation.

### Phase 3 — Scan experience
Full-screen viewfinder with guide frame, single flow with review sheet + back-side step, batch mode with tray, gallery import, non-blocking status strip. Remove old tabs UI.
**Accept:** 10 cards can be captured in batch mode in under 60 seconds of user interaction; front+back single flow produces one record; camera denial shows gallery fallback; leaving scan stops the camera LED.

### Phase 4 — Dashboard
Hero stats, action row, recent captures, usage meters, empty states, auto-refresh on route entry.
**Accept:** counts match records endpoint; quota meters change color at 70%/90%; fresh install with zero events shows the create-event empty state.

### Phase 5 — PWA & offline queue
Manifest, icons, SW routes in main.py, precache + runtime caching, IndexedDB queue, upload worker, connectivity UX, install button.
**Accept:** Lighthouse PWA installable check passes; with DevTools offline: capturing 3 cards queues them and UI shows "Offline · 3 queued"; going online auto-processes all 3 and records appear; app cold-starts offline and shows cached records; hard-refresh after deploy with bumped cache version fetches new assets.

### Phase 6 — Polish & QA
Reduced-motion support, focus states, aria labels on icon buttons, skeletons, 500-record chunked render, real-device pass (Android Chrome + iOS Safari).
**Accept:** full checklist §12 green.

### Suggested verification harness (for the implementing model)
After each phase, run the FastAPI app and use browser tooling to: screenshot at 375/390/768/1280 widths, exercise the phase's flows, and check console for errors. Screenshot review is mandatory — CSS regressions are invisible in code review.

---

## 12. Final QA checklist

- [ ] No horizontal scrolling at 320px width, any screen
- [ ] All interactive elements ≥48px hit area; inputs ≥16px font
- [ ] Bottom nav + FAB reachable and functional on iOS Safari (safe-area respected)
- [ ] Camera: request → capture → review → process on Android Chrome and iOS Safari (HTTPS)
- [ ] Offline: capture, queue, banner, auto-flush on reconnect
- [ ] Install: A2HS works, standalone display, correct icon/theme color
- [ ] tel:/mailto:/vCard actions work from record detail
- [ ] Excel export unchanged; edit round-trips every field
- [ ] Old `styles.css`/`upload.js` deleted; no dead code
- [ ] Keyboard focus visible on desktop; icon-only buttons have `aria-label`
- [ ] Lighthouse: PWA installable, a11y ≥90, no console errors

## 13. Out of scope (do not build)
Dark mode, drag-to-dismiss sheets, Background Sync API, push notifications, multi-user auth, on-device OCR, framework migration, backend pipeline changes, i18n.
