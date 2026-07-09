import * as api from "./api.js";
import { escapeHtml } from "./utils.js";
import { getQueueSnapshot, removeQueueItem, retryQueueItem } from "./queue.js";
import { usagePanelHtml } from "./usage-panel.js";

const $ = (selector) => document.querySelector(selector);

let deferredInstallPrompt = null;

export function wireMoreScreen() {
  $("#moreProcessQueueBtn").addEventListener("click", () => {
    window.dispatchEvent(new CustomEvent("attemptQueueFlush"));
  });
  $("#moreExportBtn").addEventListener("click", async () => {
    const { state, showToast } = await import("./app-shell.js");
    if (!state.eventId) return showToast("Select an event first.", "error");
    if (!state.online) return showToast("Export requires a connection.", "error");
    window.open(api.downloadUrl(state.eventId), "_blank");
  });

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    $("#installAppBtn").hidden = false;
  });
  window.addEventListener("appinstalled", () => {
    $("#installAppBtn").hidden = true;
    deferredInstallPrompt = null;
  });
  $("#installAppBtn").addEventListener("click", async () => {
    if (!deferredInstallPrompt) return;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    $("#installAppBtn").hidden = true;
  });

  window.addEventListener("queueChanged", async () => {
    const { state } = await import("./app-shell.js");
    if (state.route === "#/more") renderQueueList();
  });
}

export async function refreshMoreScreen(state) {
  renderQueueList();
  renderUsage(state);
  await renderHealth(state);
}

function renderQueueList() {
  const list = $("#moreQueueList");
  const queue = getQueueSnapshot();
  if (!queue.length) {
    list.innerHTML = `<p style="color:var(--text-dim);font-size:var(--font-sm)">Queue is empty.</p>`;
    return;
  }
  list.innerHTML = queue.map((item) => `
    <div class="queue-row" data-id="${item.id}">
      ${item.thumbUrl ? `<img src="${item.thumbUrl}" alt="">` : `<div style="width:44px;height:44px;border-radius:8px;background:#eef0f4"></div>`}
      <div class="queue-row-body">
        <div style="font-weight:700;font-size:var(--font-sm)">${escapeHtml(item.eventId)}</div>
        <div style="color:var(--text-dim);font-size:12px">${escapeHtml(new Date(item.capturedAt).toLocaleTimeString())}</div>
      </div>
      <span class="status-chip ${item.status}">${item.status === "failed" ? "Failed" : item.status === "uploading" ? "Uploading" : "Waiting"}</span>
      ${item.status === "failed" ? `<button class="btn outline" data-retry="${item.id}" style="min-height:36px;padding:6px 10px;">Retry</button>` : ""}
    </div>
  `).join("");
  list.querySelectorAll("[data-retry]").forEach((btn) => {
    btn.addEventListener("click", () => retryQueueItem(Number(btn.dataset.retry)));
  });
}

function renderUsage(state) {
  const el = $("#moreUsageMeters");
  el.innerHTML = usagePanelHtml(state.usage, state.health);
}

async function renderHealth(state) {
  const el = $("#healthList");
  try {
    const data = state.health || (await api.getHealth());
    el.innerHTML = `
      <div>Gemini: ${data.gemini_configured ? `configured (${data.gemini_key_count} key${data.gemini_key_count === 1 ? "" : "s"})` : "not configured"}</div>
      <div>Google Vision: ${data.google_vision_configured ? "configured" : "not configured"}</div>
      <div>Mode: ${escapeHtml(data.processing_mode || "")}</div>
    `;
  } catch {
    el.textContent = "Health check unavailable.";
  }
}
