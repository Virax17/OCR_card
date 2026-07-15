import * as api from "./api.js";
import { escapeHtml } from "./utils.js";
import { usagePanelHtml } from "./usage-panel.js";

const $ = (selector) => document.querySelector(selector);

let deferredInstallPrompt = null;

export function wireMoreScreen() {
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

}

export async function refreshMoreScreen(state) {
  renderUsage(state);
  await renderHealth(state);
}

function renderUsage(state) {
  const el = $("#moreUsageMeters");
  el.innerHTML = usagePanelHtml(state.usage, state.health);
}

async function renderHealth(state) {
  const el = $("#healthList");
  try {
    const data = state.health || (await api.getHealth());
    const usageMongo = state.usage?.mongo;
    const mongo = usageMongo || data.mongo_usage || {};
    const mongoStatus = mongo.enabled
      ? (
          mongo.available
            ? "live"
            : mongo.checked === false && !usageMongo
              ? "configured - checked during usage"
              : (mongo.blocking_scans ? "unavailable - blocking scans" : "fallback - local counters")
        )
      : "disabled";
    el.innerHTML = `
      <div>Gemini: ${data.gemini_configured ? `configured (${data.gemini_key_count} key${data.gemini_key_count === 1 ? "" : "s"})` : "not configured"}</div>
      <div>Google Vision: ${data.google_vision_configured ? "configured" : "not configured"}</div>
      <div>MongoDB tracker: ${escapeHtml(mongoStatus)}</div>
      <div>Mode: ${escapeHtml(data.processing_mode || "")}</div>
    `;
  } catch {
    el.textContent = "Health check unavailable.";
  }
}
