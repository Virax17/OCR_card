import * as api from "./api.js";
import { escapeHtml, isDuplicate } from "./utils.js";
import { getQueueSnapshot, retryQueueItem, removeQueueItem } from "./queue.js";
import { usagePanelHtml } from "./usage-panel.js";

const $ = (selector) => document.querySelector(selector);

// How long a finished card keeps showing "✓ Done" in the processing panel
// before it drops out of the list.
const DONE_DISPLAY_MS = 4500;

// Recently-completed queue items, kept around just long enough for the user
// to see them finish (the queue itself deletes an item the instant it succeeds).
let recentlyDone = []; // { id, thumbUrl }
// The queue deletes an item's row (and its thumbUrl) from the snapshot BEFORE
// dispatching queueItemProcessed, so by the time the success handler runs the
// thumbnail is already gone. This map is rebuilt on every render (while items
// are still "uploading" and thus present) so the handler can still look it up.
let lastSnapshotById = new Map();

export function renderDashboard() {
  // Static wiring handled in wire functions; kept for symmetry with other screens.
}

export function wireDashboard() {
  $("#dashScanBtn").addEventListener("click", async () => {
    const { openScanScreen } = await import("./scan.js");
    openScanScreen();
  });
  $("#dashUploadBtn").addEventListener("click", () => $("#dashUploadInput").click());
  $("#dashUploadInput").addEventListener("change", async () => {
    const files = Array.from($("#dashUploadInput").files || []);
    if (!files.length) return;
    const { importGalleryFiles } = await import("./scan.js");
    await importGalleryFiles(files);
    $("#dashUploadInput").value = "";
  });
  $("#dashExportBtn").addEventListener("click", async () => {
    const { state, showToast } = await import("./app-shell.js");
    if (!state.eventId) return showToast("Select an event first.", "error");
    if (!state.online) return showToast("Export requires a connection.", "error");
    window.open(api.downloadUrl(state.eventId), "_blank");
  });
  $("#queueBannerBtn").addEventListener("click", async () => {
    window.dispatchEvent(new CustomEvent("attemptQueueFlush"));
  });

  // Registered once here (not inside render) so successful items get a brief
  // "done" entry no matter which screen is active when they finish.
  window.addEventListener("queueItemProcessed", handleQueueItemProcessed);
}

export async function refreshDashboard(state) {
  renderHero(state);
  renderQueueBanner(state);
  renderProcessingPanel(state);
  renderUsage(state);
}

async function handleQueueItemProcessed(event) {
  const { id, success } = event.detail || {};
  if (!success || id == null) return;
  if (recentlyDone.some((entry) => entry.id === id)) return; // already tracked
  const lastKnown = lastSnapshotById.get(id);
  recentlyDone.push({ id, thumbUrl: lastKnown?.thumbUrl || "" });
  window.setTimeout(() => {
    recentlyDone = recentlyDone.filter((entry) => entry.id !== id);
    import("./app-shell.js").then(({ state }) => renderProcessingPanel(state));
  }, DONE_DISPLAY_MS);
  const { state } = await import("./app-shell.js");
  renderProcessingPanel(state);
}

function renderHero(state) {
  const hero = $("#heroCard");
  if (state.loading) {
    hero.innerHTML = `
      <div class="skeleton-line" style="width:60%;height:20px"></div>
      <div class="skeleton-line" style="width:40%;margin-top:8px"></div>
      <div class="hero-stats">
        <div class="skeleton-block" style="height:56px"></div>
        <div class="skeleton-block" style="height:56px"></div>
        <div class="skeleton-block" style="height:56px"></div>
      </div>
    `;
    return;
  }
  const event = state.events.find((item) => item.event_id === state.eventId);
  if (!state.events.length) {
    hero.innerHTML = `
      <div class="hero-card-name">Create your first event</div>
      <div class="hero-card-sub">Set up an event to start scanning cards.</div>
      <button id="heroCreateEventBtn" class="btn primary block" type="button" style="margin-top:var(--space-3)">+ New event</button>
    `;
    $("#heroCreateEventBtn").addEventListener("click", async () => {
      const { openEventSheet } = await import("./events.js");
      openEventSheet();
      $("#eventNewBtn").click();
    });
    return;
  }
  const total = state.records.length;
  const today = new Date().toISOString().slice(0, 10);
  const todayCount = state.records.filter((record) => record.date === today).length;
  const dupCount = state.records.filter(isDuplicate).length;
  hero.innerHTML = `
    <div class="hero-card-top">
      <div class="hero-card-name">${escapeHtml(event?.name || "Event")}</div>
      <button id="heroSwitchEventBtn" class="btn text-link" type="button">Switch <svg class="icon" aria-hidden="true" style="width:14px;height:14px"><use href="#icon-chevron-down"/></svg></button>
    </div>
    <div class="hero-card-sub">${escapeHtml(event?.date || "")}${event?.location ? ` · ${escapeHtml(event.location)}` : ""}</div>
    <div class="hero-stats">
      <div class="hero-stat"><div class="num mono">${total}</div><div class="label">Cards</div></div>
      <div class="hero-stat"><div class="num mono">${todayCount}</div><div class="label">Today</div></div>
      <div class="hero-stat"><div class="num mono ${dupCount > 0 ? "amber" : ""}">${dupCount}</div><div class="label">Duplicates</div></div>
    </div>
  `;
  $("#heroSwitchEventBtn").addEventListener("click", async () => {
    const { openEventSheet } = await import("./events.js");
    openEventSheet();
  });
}

function renderQueueBanner(state) {
  const banner = $("#queueBanner");
  const queue = getQueueSnapshot();
  if (!queue.length) {
    banner.hidden = true;
    return;
  }
  banner.hidden = false;
  $("#queueBannerText").textContent = `${queue.length} scan${queue.length === 1 ? "" : "s"} waiting for network — will process automatically`;
}

function renderProcessingPanel(state) {
  const panel = $("#processingPanel");
  if (!panel) return;
  if (state.loading) {
    panel.innerHTML = Array.from({ length: 2 }, () => `
      <div class="queue-row">
        <div class="skeleton-block" style="width:44px;height:44px;border-radius:8px"></div>
        <div class="queue-row-body">
          <div class="skeleton-line" style="width:50%"></div>
          <div class="skeleton-line" style="width:70%"></div>
        </div>
      </div>
    `).join("");
    return;
  }

  const queue = getQueueSnapshot();
  // Snapshot items are still present while "uploading"; capture their thumb/time
  // here so a completed item's row can still be rendered after it's deleted.
  lastSnapshotById = new Map(queue.map((item) => [item.id, { thumbUrl: item.thumbUrl, capturedAt: item.capturedAt }]));

  const rows = [
    ...queue.map((item) => ({ kind: item.status, item })),
    ...recentlyDone.map((entry) => ({
      kind: "done",
      item: { id: entry.id, thumbUrl: entry.thumbUrl, capturedAt: lastSnapshotById.get(entry.id)?.capturedAt },
    })),
  ];
  // Active work first, then reassuring "done" feedback, then failures that
  // need the user's attention (kept visible until retried or dismissed).
  const order = { uploading: 0, pending: 1, done: 2, failed: 3 };
  rows.sort((a, b) => order[a.kind] - order[b.kind]);

  if (!rows.length) {
    panel.innerHTML = `<div class="empty-card"><strong>All caught up</strong>No cards processing right now.</div>`;
    return;
  }

  panel.innerHTML = rows.map((row) => processingRowHtml(row)).join("");
  panel.querySelectorAll("[data-retry]").forEach((btn) => {
    btn.addEventListener("click", () => retryQueueItem(Number(btn.dataset.retry)));
  });
  panel.querySelectorAll("[data-dismiss]").forEach((btn) => {
    btn.addEventListener("click", () => removeQueueItem(Number(btn.dataset.dismiss)));
  });
}

function processingRowHtml({ kind, item }) {
  const labels = { pending: "Waiting", uploading: "Processing…", done: "✓ Done", failed: "⚠ Failed" };
  const chipClass = kind === "pending" ? "waiting" : kind;
  const thumb = item.thumbUrl
    ? `<img src="${item.thumbUrl}" alt="">`
    : `<div style="width:44px;height:44px;border-radius:8px;background:#eef0f4"></div>`;
  const timeLabel = item.capturedAt ? new Date(item.capturedAt).toLocaleTimeString() : "";
  return `
    <div class="queue-row">
      ${thumb}
      <div class="queue-row-body">
        <div style="font-weight:700;font-size:var(--font-sm)">${escapeHtml(timeLabel || "Card")}</div>
      </div>
      <span class="status-chip ${chipClass}">${labels[kind]}</span>
      ${kind === "failed" ? `
        <button class="btn outline" data-retry="${item.id}" style="min-height:36px;padding:6px 10px;">Retry</button>
        <button class="btn ghost icon-btn" data-dismiss="${item.id}" aria-label="Dismiss" style="min-height:36px;">✕</button>
      ` : ""}
    </div>
  `;
}

function renderUsage(state) {
  const el = $("#usageMeters");
  el.innerHTML = usagePanelHtml(state.usage, state.health);
}
