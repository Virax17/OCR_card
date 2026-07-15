import * as api from "./api.js";
import { wireDashboard, refreshDashboard } from "./dashboard.js";
import { renderRecords, refreshRecords, openRecordsMenu, wireRecordsScreen } from "./records.js";
import { wireEventSheet, openEventSheet, refreshEventLabel } from "./events.js";
import { wireScanScreen, openScanScreen } from "./scan.js";
import { wireMoreScreen, refreshMoreScreen } from "./more.js";
import { wireProcessSheet } from "./process-sheet.js";
import { initQueue, getQueueSnapshot } from "./queue.js";

export const state = {
  eventId: null,
  events: [],
  records: [],
  route: "#/home",
  online: navigator.onLine,
  pendingQueue: [],
  filters: { search: "", needsReviewOnly: false, category: null },
  loading: true,
};

const $ = (selector) => document.querySelector(selector);

const ROUTES = ["#/home", "#/records", "#/more"];

document.addEventListener("DOMContentLoaded", async () => {
  wireNav();
  wireEventSheet();
  wireDashboard();
  wireRecordsScreen();
  wireScanScreen();
  wireMoreScreen();
  wireProcessSheet();
  window.addEventListener("hashchange", handleRouteChange);
  window.addEventListener("online", handleConnectivityChange);
  window.addEventListener("offline", handleConnectivityChange);
  window.addEventListener("queueChanged", handleQueueChanged);
  window.matchMedia("(min-width: 1024px)").addEventListener("change", handleRouteChange);

  if (!window.location.hash || !ROUTES.includes(window.location.hash)) {
    window.location.hash = "#/home";
  }
  handleRouteChange();

  await initQueue();
  await checkHealth();
  await loadEvents();
  await loadRecords();
  await loadUsage();
  state.loading = false;
  handleRouteChange();
  registerServiceWorker();
});

function wireNav() {
  document.querySelectorAll("[data-route]").forEach((el) => {
    el.addEventListener("click", () => {
      window.location.hash = el.dataset.route;
    });
  });
  $("#navLinkScan")?.addEventListener("click", () => openScanScreen());
  $("#appBarEvent").addEventListener("click", () => openEventSheet());
  $("#netStatus").addEventListener("click", () => {
    window.location.hash = "#/more";
  });
}

function handleRouteChange() {
  const hash = window.location.hash || "#/home";
  const [routeBase] = hash.split("/").slice(0, 2);
  const normalized = ROUTES.includes(hash) ? hash : (hash.startsWith("#/records") ? "#/records" : "#/home");
  state.route = normalized;
  document.querySelectorAll(".screen[data-screen]").forEach((section) => {
    section.classList.remove("is-active");
  });
  document.querySelectorAll(".nav-item[data-route], .nav-link[data-route]").forEach((el) => {
    el.classList.toggle("active", el.dataset.route === normalized);
  });

  const screenMap = { "#/home": "screen-home", "#/records": "screen-records", "#/more": "screen-more" };
  const target = document.getElementById(screenMap[normalized]);
  if (target) target.classList.add("is-active");
  document.body.classList.toggle("more-active", normalized === "#/more");

  // Desktop (>=1024px) renders home + records as one merged 2-pane view via
  // CSS regardless of route, so both must stay populated with fresh data.
  const isDesktop = window.matchMedia("(min-width: 1024px)").matches;
  if (normalized === "#/home" || isDesktop) refreshDashboard(state);
  if (normalized === "#/records" || isDesktop) refreshRecords(state);
  if (normalized === "#/more") refreshMoreScreen(state);
}

async function checkHealth() {
  try {
    state.health = await api.getHealth();
  } catch {
    state.health = null;
  }
}

export async function loadEvents() {
  const events = await api.listEvents();
  state.events = events || [];
  const previous = state.eventId;
  if (state.events.some((event) => event.event_id === previous)) {
    state.eventId = previous;
  } else {
    state.eventId = state.events[0]?.event_id || null;
  }
  refreshEventLabel(state);
}

export async function loadRecords() {
  if (!state.eventId) {
    state.records = [];
    return;
  }
  const data = await api.listRecords(state.eventId);
  state.records = data.records || [];
}

export async function loadUsage() {
  try {
    state.usage = await api.getUsage();
  } catch {
    // Keep the last good usage so a single failed poll doesn't leave the panel
    // stuck on "Usage unavailable"; only blank it if we never loaded any.
    if (state.usage === undefined) state.usage = null;
  }
}

export async function switchEvent(eventId) {
  state.eventId = eventId;
  refreshEventLabel(state);
  await loadRecords();
  await loadUsage();
  handleRouteChange();
  showToast(`Switched to ${state.events.find((e) => e.event_id === eventId)?.name || eventId}`, "success");
}

export async function refreshAll() {
  await loadRecords();
  await loadUsage();
  handleRouteChange();
}

function handleConnectivityChange() {
  state.online = navigator.onLine;
  updateNetStatusPill();
}

function handleQueueChanged(event) {
  state.pendingQueue = event.detail?.items || getQueueSnapshot();
  updateNetStatusPill();
  // Desktop (>=1024px) renders home + records as one merged 2-pane view via
  // CSS regardless of route, so the left-rail processing panel must stay live
  // even while the user is looking at Records (mirrors handleRouteChange).
  const isDesktop = window.matchMedia("(min-width: 1024px)").matches;
  if (state.route === "#/home" || isDesktop) refreshDashboard(state);
  if (state.route === "#/more") refreshMoreScreen(state);
}

function updateNetStatusPill() {
  const pill = $("#netStatus");
  const text = $("#netStatusText");
  const queued = state.pendingQueue.length;
  if (!state.online) {
    pill.classList.add("visible");
    text.textContent = queued ? `Offline · ${queued} queued` : "Offline";
  } else if (queued > 0) {
    pill.classList.add("visible");
    text.textContent = `${queued} queued`;
  } else {
    pill.classList.remove("visible");
  }
}

export function showToast(message, variant = "info") {
  const container = $("#toast");
  const item = document.createElement("div");
  item.className = `toast-item ${variant}`;
  item.setAttribute("role", variant === "error" ? "alert" : "status");
  const text = document.createElement("span");
  text.textContent = message;
  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.setAttribute("aria-label", "Dismiss");
  closeBtn.textContent = "✕";
  closeBtn.addEventListener("click", () => item.remove());
  item.appendChild(text);
  item.appendChild(closeBtn);
  container.appendChild(item);
  const timeout = variant === "error" ? null : 3500;
  if (timeout) window.setTimeout(() => item.remove(), timeout);
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

export { handleRouteChange as rerender };
