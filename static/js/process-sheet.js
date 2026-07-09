import { enqueueCapture, retryQueueItem } from "./queue.js";
import { escapeHtml } from "./utils.js";

const $ = (selector) => document.querySelector(selector);

// One entry per selected photo: { clientId, blob, name, url, queueId, status }.
// status ∈ "waiting" | "uploading" | "done" | "failed".
let selected = [];
let processing = false; // true once the user confirms and the live view is active
let clientSeq = 0;

export function wireProcessSheet() {
  const sheet = $("#processSheet");
  $("#processCloseBtn").addEventListener("click", () => sheet.close());
  $("#processCancelBtn").addEventListener("click", () => sheet.close());
  $("#processLiveCloseBtn").addEventListener("click", () => sheet.close());
  $("#processDoneBtn").addEventListener("click", () => sheet.close());
  $("#processConfirmBtn").addEventListener("click", startProcessing);
  $("#processRetryAllBtn").addEventListener("click", retryAllFailed);

  // Backdrop click closes (mirrors the other dialog sheets).
  sheet.addEventListener("click", (event) => {
    if (event.target === sheet) sheet.close();
  });

  // Single cleanup path for every close reason (Cancel, Done, Esc, backdrop).
  sheet.addEventListener("close", cleanup);

  // Live view is driven entirely by the existing queue events.
  window.addEventListener("queueItemProcessed", handleQueueItemProcessed);
  window.addEventListener("queueChanged", handleQueueChangedForLive);
  window.addEventListener("online", updateOfflineHint);
  window.addEventListener("offline", updateOfflineHint);
}

// items: [{ blob, name? }]
export async function openProcessSheet(items) {
  const sheet = $("#processSheet");
  if (sheet.open) return; // ignore rapid re-opens
  const list = (items || []).filter((it) => it && it.blob);
  if (!list.length) return;

  selected = list.map((it) => ({
    clientId: `c${clientSeq += 1}`,
    blob: it.blob,
    name: it.name || "Photo",
    url: URL.createObjectURL(it.blob),
    queueId: null,
    status: "waiting",
  }));
  processing = false;

  // Show View A, reset View B.
  $("#processConfirmView").hidden = false;
  $("#processLiveView").hidden = true;
  $("#processLiveFooter").hidden = true;
  $("#processLiveCloseBtn").hidden = true;
  $("#processRetryAllBtn").hidden = true;
  $("#processLiveTitle").textContent = "Processing…";

  renderGrid();
  sheet.showModal();
}

function renderGrid() {
  const grid = $("#processGrid");
  grid.innerHTML = selected.map((it) => `
    <div class="process-thumb" data-client-id="${it.clientId}">
      <img src="${it.url}" alt="">
      <button type="button" aria-label="Remove photo">✕</button>
    </div>
  `).join("");
  grid.querySelectorAll(".process-thumb button").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      const clientId = event.currentTarget.parentElement.dataset.clientId;
      removeSelected(clientId);
    });
  });
  const count = selected.length;
  $("#processConfirmBtn").textContent = `Process ${count} photo${count === 1 ? "" : "s"}`;
}

function removeSelected(clientId) {
  const index = selected.findIndex((it) => it.clientId === clientId);
  if (index === -1) return;
  URL.revokeObjectURL(selected[index].url);
  selected.splice(index, 1);
  if (!selected.length) {
    // Removing the last photo discards and closes (nothing processed).
    $("#processSheet").close();
    return;
  }
  renderGrid();
}

async function startProcessing() {
  if (!selected.length || processing) return;
  const { state, showToast } = await import("./app-shell.js");
  if (!state.eventId) {
    showToast("Create or select an event first.", "error");
    $("#processSheet").close();
    return;
  }

  processing = true;
  $("#processConfirmView").hidden = true;
  $("#processLiveView").hidden = false;
  updateOfflineHint();
  renderLiveList();
  updateMeter();

  // Enqueue sequentially; record the queue id the queue now returns so we can
  // correlate each photo through to completion.
  for (const it of selected) {
    const record = await enqueueCapture(state.eventId, it.blob, null);
    it.queueId = record.id ?? null;
  }
}

function renderLiveList() {
  const list = $("#processLiveList");
  list.innerHTML = selected.map((it) => `
    <div class="queue-row" data-client-id="${it.clientId}">
      <img src="${it.url}" alt="">
      <div class="queue-row-body"><div class="name">${escapeHtml(it.name)}</div></div>
      <div class="row-actions">${statusChipHtml(it)}${retryButtonHtml(it)}</div>
    </div>
  `).join("");
  list.querySelectorAll("[data-retry]").forEach((btn) => {
    btn.addEventListener("click", (event) => retryOne(event.currentTarget.dataset.retry));
  });
}

function statusChipHtml(it) {
  const labels = {
    waiting: "Waiting",
    uploading: "Processing…",
    done: "✓ Done",
    failed: "⚠ Failed",
  };
  return `<span class="status-chip ${it.status}">${labels[it.status]}</span>`;
}

function retryButtonHtml(it) {
  if (it.status !== "failed" || it.queueId == null) return "";
  return `<button class="btn ghost" type="button" data-retry="${it.clientId}">Retry</button>`;
}

function renderRow(it) {
  const row = $(`#processLiveList .queue-row[data-client-id="${it.clientId}"]`);
  if (!row) return;
  row.querySelector(".row-actions").innerHTML = statusChipHtml(it) + retryButtonHtml(it);
  const retryBtn = row.querySelector("[data-retry]");
  if (retryBtn) retryBtn.addEventListener("click", () => retryOne(it.clientId));
}

function updateMeter() {
  const total = selected.length;
  const finished = selected.filter((it) => it.status === "done" || it.status === "failed").length;
  const failed = selected.filter((it) => it.status === "failed").length;
  const pct = total ? Math.round((finished / total) * 100) : 0;
  const fill = $("#processProgressFill");
  fill.style.width = `${pct}%`;
  fill.classList.toggle("warning", failed > 0);
  $("#processProgressValue").textContent = `${finished} / ${total}`;

  if (finished === total && total > 0) {
    showCompletion(total, finished - failed, failed);
  }
}

function showCompletion(total, done, failed) {
  $("#processLiveTitle").textContent = failed
    ? `Processed ${done}, ${failed} need${failed === 1 ? "s" : ""} review`
    : `All ${total} processed`;
  $("#processLiveFooter").hidden = false;
  $("#processLiveCloseBtn").hidden = false;
  $("#processRetryAllBtn").hidden = failed === 0;
}

function handleQueueItemProcessed(event) {
  if (!processing) return;
  const id = event.detail?.id;
  if (id == null) return;
  const it = selected.find((entry) => entry.queueId === id);
  if (!it) return;
  it.status = event.detail.success ? "done" : "failed";
  renderRow(it);
  updateMeter();
}

// Upgrade waiting photos to "uploading" as the queue picks them up.
function handleQueueChangedForLive(event) {
  if (!processing) return;
  const items = event.detail?.items || [];
  const uploadingIds = new Set(items.filter((i) => i.status === "uploading").map((i) => i.id));
  let changed = false;
  for (const it of selected) {
    if (it.status === "waiting" && it.queueId != null && uploadingIds.has(it.queueId)) {
      it.status = "uploading";
      renderRow(it);
      changed = true;
    }
  }
  if (changed) updateMeter();
}

async function retryOne(clientId) {
  const it = selected.find((entry) => entry.clientId === clientId);
  if (!it || it.queueId == null) return;
  it.status = "waiting";
  renderRow(it);
  updateMeter();
  // Un-complete the footer while a retry is in flight.
  $("#processLiveTitle").textContent = "Processing…";
  $("#processLiveFooter").hidden = true;
  await retryQueueItem(it.queueId);
}

async function retryAllFailed() {
  const failed = selected.filter((it) => it.status === "failed" && it.queueId != null);
  if (!failed.length) return;
  for (const it of failed) {
    it.status = "waiting";
    renderRow(it);
  }
  updateMeter();
  $("#processLiveTitle").textContent = "Processing…";
  $("#processLiveFooter").hidden = true;
  for (const it of failed) {
    await retryQueueItem(it.queueId);
  }
}

function updateOfflineHint() {
  const hint = $("#processOfflineHint");
  if (!hint) return;
  hint.hidden = navigator.onLine || !processing;
}

// Runs on every close (Cancel, Done, Esc, backdrop). Enqueued items keep
// processing in the background via the durable queue — we only tear down the UI
// and release the object URLs this sheet owns.
function cleanup() {
  processing = false;
  for (const it of selected) {
    if (it.url) URL.revokeObjectURL(it.url);
  }
  selected = [];
}
