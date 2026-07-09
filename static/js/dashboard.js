import * as api from "./api.js";
import { escapeHtml, confidenceLevel, isDuplicate, avatarTint, initials } from "./utils.js";
import { getQueueSnapshot } from "./queue.js";
import { usagePanelHtml } from "./usage-panel.js";

const $ = (selector) => document.querySelector(selector);

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
}

export async function refreshDashboard(state) {
  renderHero(state);
  renderQueueBanner(state);
  renderRecent(state);
  renderUsage(state);
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

function renderRecent(state) {
  const list = $("#recentList");
  if (state.loading) {
    list.innerHTML = Array.from({ length: 3 }, () => `
      <div class="recent-row">
        <div class="skeleton-block" style="width:34px;height:34px;border-radius:50%"></div>
        <div class="recent-row-body">
          <div class="skeleton-line" style="width:50%"></div>
          <div class="skeleton-line" style="width:70%"></div>
        </div>
      </div>
    `).join("");
    return;
  }
  if (!state.eventId) {
    list.innerHTML = "";
    return;
  }
  if (!state.records.length) {
    list.innerHTML = `<div class="empty-card"><strong>No cards scanned yet</strong>Tap Scan to start.</div>`;
    return;
  }
  const recent = [...state.records].slice(0, 5);
  list.innerHTML = recent.map((record) => recentRowHtml(state, record)).join("");
  list.querySelectorAll("[data-card-id]").forEach((el) => {
    el.addEventListener("click", async () => {
      const { openRecordDetail } = await import("./records.js");
      const record = state.records.find((r) => r.card_id === el.dataset.cardId);
      if (record) openRecordDetail(record);
    });
  });
}

function recentRowHtml(state, record) {
  const image = record.front_image_filename ? api.imageUrl(state.eventId, record.front_image_filename) : "";
  const level = confidenceLevel(record);
  const tint = avatarTint(record.name);
  return `
    <div class="recent-row" data-card-id="${escapeHtml(record.card_id)}">
      <div class="recent-avatar" style="--avatar-bg:${tint.bg};--avatar-fg:${tint.fg}">
        ${image ? `<img src="${image}" alt="">` : escapeHtml(initials(record.name))}
      </div>
      <div class="recent-row-body">
        <div class="recent-row-name">${escapeHtml(record.name || "Unnamed")}</div>
        <div class="recent-row-meta">${escapeHtml(record.company || record.business || "")}</div>
      </div>
      <span class="confidence-dot ${level}"></span>
    </div>
  `;
}

function renderUsage(state) {
  const el = $("#usageMeters");
  el.innerHTML = usagePanelHtml(state.usage, state.health);
}
