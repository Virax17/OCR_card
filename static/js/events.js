import * as api from "./api.js";
import { escapeHtml } from "./utils.js";

const $ = (selector) => document.querySelector(selector);

export function wireEventSheet() {
  $("#eventSheetCloseBtn").addEventListener("click", () => $("#eventSheet").close());
  $("#eventSheet").addEventListener("click", (event) => {
    if (event.target.id === "eventSheet") $("#eventSheet").close();
  });
  $("#eventNewBtn").addEventListener("click", () => {
    const today = new Date().toISOString().slice(0, 10);
    $("#eventName").value = "";
    $("#eventDate").value = today;
    $("#eventLocation").value = "";
    $("#eventCreateForm").classList.add("visible");
    $("#eventList").hidden = true;
    $("#eventNewBtn").hidden = true;
    $("#eventName").focus();
  });
  $("#eventCreateCancelBtn").addEventListener("click", () => {
    $("#eventCreateForm").classList.remove("visible");
    $("#eventList").hidden = false;
    $("#eventNewBtn").hidden = false;
  });
  $("#eventCreateForm").addEventListener("submit", handleCreateEvent);
}

export function openEventSheet() {
  import("./app-shell.js").then(({ state }) => {
    renderEventList(state);
    $("#eventCreateForm").classList.remove("visible");
    $("#eventList").hidden = false;
    $("#eventNewBtn").hidden = false;
    $("#eventSheet").showModal();
  });
}

function renderEventList(state) {
  const list = $("#eventList");
  if (!state.events.length) {
    list.innerHTML = `<p style="color:var(--text-dim);font-size:var(--font-sm)">No events yet. Create one below.</p>`;
    return;
  }
  list.innerHTML = state.events.map((event) => `
    <div class="event-row ${event.event_id === state.eventId ? "current" : ""}" data-event-id="${escapeHtml(event.event_id)}">
      <div>
        <div class="event-row-name">${escapeHtml(event.name)}</div>
        <div class="event-row-meta">${escapeHtml(event.date)}${event.location ? ` · ${escapeHtml(event.location)}` : ""}</div>
      </div>
      <svg class="icon" aria-hidden="true"><use href="#icon-check"/></svg>
    </div>
  `).join("");
  list.querySelectorAll("[data-event-id]").forEach((row) => {
    row.addEventListener("click", async () => {
      const { switchEvent } = await import("./app-shell.js");
      $("#eventSheet").close();
      await switchEvent(row.dataset.eventId);
    });
  });
}

async function handleCreateEvent(event) {
  event.preventDefault();
  const { showToast, loadEvents, switchEvent } = await import("./app-shell.js");
  const name = $("#eventName").value.trim();
  const date = $("#eventDate").value;
  const location = $("#eventLocation").value.trim();
  if (!name || !date) return showToast("Event name and date are required.", "error");
  $("#eventCreateSaveBtn").disabled = true;
  try {
    const created = await api.createEvent({ name, date, location });
    await loadEvents();
    $("#eventSheet").close();
    await switchEvent(created.event_id);
    showToast(`Created event: ${created.name}`, "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    $("#eventCreateSaveBtn").disabled = false;
  }
}

export function refreshEventLabel(state) {
  const event = state.events.find((item) => item.event_id === state.eventId);
  const label = $("#appBarEvent .name");
  label.textContent = event ? event.name : "Select event";
}
