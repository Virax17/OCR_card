# UI Fable — Visual Polish Plan (addendum to `ui_fable.md`)

**Status:** Fix plan for the first implementation pass (screenshots reviewed 2026-07-08).
**Rule for the implementing model:** this document overrides `ui_fable.md` wherever they conflict. Work through §1 (bugs) first, then §2–§5 (visual system). After every change set, take screenshots at 390px and 1280px and compare against the approved mockup (two phone frames: Home + Records).

---

## 1. Bugs — fix before any styling

| # | Problem seen in screenshots | Fix |
|---|---|---|
| B1 | Desktop shows the mobile column pinned to the left with a huge dead area on the right. §7 of ui_fable.md (two-pane desktop) was never implemented. | Implement §3 layout grid below. Content must never hug the left edge. |
| B2 | Records screen renders BOTH the mobile empty-state card AND the desktop table at the same time, and the table has a horizontal scrollbar. | Card list and table are mutually exclusive: `.records-list { display:block } .records-table { display:none }` under 1024px, inverted at ≥1024px. Never render the table when `records.length === 0` — render the empty state only, once. |
| B3 | Queue banner shows "0 scans waiting for network" with a "Process now" button. | Banner element gets `hidden` whenever `pendingQueue.length === 0`. No zero-count states anywhere: hide, don't show "0". |
| B4 | Desktop table needs horizontal scroll. | 7 columns max (Card, Name, Company, Category, Phone, Email, Confidence), `table-layout: fixed`, ellipsize overflow. If it still can't fit, drop Category. |

## 2. Layout grid (the single biggest "ugly" cause)

- **Every screen's content wrapper:** `max-width: 640px; margin-inline: auto; padding: 24px 16px;` on mobile/tablet.
- **Desktop ≥1024px:** `.layout { display: grid; grid-template-columns: 360px minmax(0,1fr); gap: 24px; max-width: 1160px; margin-inline: auto; padding: 32px 24px; }` — left column holds hero + actions + usage, right column holds records. Home and Records merge into this one two-pane view on desktop; the top-nav Records link scrolls/focuses the right pane.
- The top app bar stays full-bleed; its inner content uses the same `max-width: 1160px` wrapper so brand and nav align with the page content.
- Nothing may ever be narrower than its container for no reason: buttons and search inputs are `width: 100%` of the content column.

## 3. Visual hierarchy rules

The screenshots fail because everything is a same-weight white/navy box. Enforce:

1. **One primary button per screen.** Teal filled pill = primary ("Scan a card"). Everything else is quiet: white bg, 1px `--line-strong` border, ink text. **"Switch event" is not a button at all** — it becomes a small teal text link with chevron inside the hero header (see mockup).
2. **Buttons are pills:** `border-radius: 999px`. Primary 52px tall; secondary 40–44px. Secondary buttons sit side-by-side in a row, never stacked full-width under the primary at the same visual weight.
3. **Stat tiles: delete the gray boxes.** Stats are a single row inside the hero card, separated by 1px vertical hairlines: number 22px `IBM Plex Mono` weight 500 (duplicates count in amber when > 0), label 11px `--text-dim` below. No backgrounds.
4. **Cards:** white, `border: 1px solid var(--line)`, `border-radius: 16px`, `box-shadow: 0 1px 2px rgba(20,33,61,.05)` only. No heavier shadows.
5. **Section labels** ("Recent captures"): 11px uppercase, letter-spacing .05em, `--text-dim`, with the "View all" link right-aligned on the same line in teal 12px.
6. **Color budget per screen:** teal = primary action + active nav + links only; amber = warnings/duplicates/offline only; navy = app bar only. Everything else is neutral. If a screen shows teal in more than 3 places, remove some.
7. **Whitespace rhythm:** 24px between sections, 12px between sibling cards, 16px card padding. No two adjacent elements with the same 10px gap everywhere (the current "everything equally spaced" look).

## 4. Typography and assets

- **Self-host fonts** (the current UI is falling back to Segoe UI, which reads as unstyled): download `IBM Plex Sans` 400/500/600 and `IBM Plex Mono` 500 as woff2 into `static/fonts/`, declare `@font-face` in `tokens.css`, add to the service-worker precache list. Do not hotlink Google Fonts (offline PWA requirement).
- Weights: 400 body, 500 emphasis/names, 600 only for screen titles. Never 700.
- Numbers (stats, phones, confidence) always mono.
- **Icons:** the current dotted/emoji-ish glyphs look broken. Use the inline SVG sprite from ui_fable.md §6.7 (24px, stroke 2, `currentColor`) for every icon including nav. No emoji anywhere.

## 5. Per-screen corrections

### Home
- Hero card per mockup: event name 17px/500 + "Switch ▾" teal link on one line, date · location dim line, hairline-separated stat row. Remove the "Switch event" navy block button entirely.
- Action area: primary "Scan a card" pill with camera icon; below it "Upload" and "Export" as two half-width quiet pills with icons.
- Recent captures: bordered rows inside ONE card (not separate floating cards): 34px initials avatar (bg = ramp tint keyed by name hash: teal/amber/purple tints), name 13px/500, company 11px dim, confidence dot 8px right-aligned. Avatar shows card thumbnail once images load; initials are the fallback.
- Usage meters live below recent captures (desktop: left column). Collapse per-key detail into `<details>`.

### Records
- Title row: "Records" + count inline (dim, smaller), kebab right.
- Search: pill-shaped, 42–48px, full width, leading search icon.
- Chips row directly under search (All filled teal when active; others quiet).
- Contact cards exactly per mockup: 44×32 thumbnail (rounded 6px, tinted placeholder with "IMG"/initials), name 14px/500, "designation · company" 11px dim one line ellipsized, phone mono 11px dim, right rail = DUP amber pill above confidence dot.
- Desktop: same header, table per B4 with 48px rows, row hover `--paper`, sticky header, click row → drawer.

### Empty states
One shared component: centered in a single card — 40px icon (dim), 15px/500 title, 13px dim body, optional primary action. Copy: "No cards scanned yet" / "Tap Scan to add your first card" + "Scan a card" button. Never paired with an empty table (B2).

### App bar
- Offline pill only when offline or queue > 0 (amber tint bg `#fef3e2`, text `#854f0b`, "Offline · N").
- Desktop nav links: 14px/500, active link gets a subtle pill (`rgba(255,255,255,.12)` bg), not a boxy tab.

## 6. Process: how to stop shipping ugly UI

1. **Install a design skill.** In Cowork: Settings → Capabilities (or the suggestion cards Claude renders in chat — click "Add"). Recommended: the **design** plugin (`design-critique`, `accessibility-review`) to critique screenshots before/after each phase, and **web-artifacts-builder** for modern frontend patterns. Skills auto-load once installed; no further setup.
2. **Mandatory screenshot loop for the implementing model:** after every visual change set — run the app, screenshot 390px and 1280px, view the screenshots, self-critique against this doc and the approved mockup, fix, re-screenshot. A change is not done until the screenshot matches.
3. **Definition of "done" checklist per screen:** no zero-count UI visible · one primary button · content centered with max-width · fonts render as IBM Plex (check a number is mono) · no horizontal scrollbars · matches mockup spacing within reason.
