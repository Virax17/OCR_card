const state = { eventId: "test_uploads", events: [], records: [] };

const $ = (selector) => document.querySelector(selector);

document.addEventListener("DOMContentLoaded", async () => {
  $("#processBtn").addEventListener("click", uploadCard);
  $("#refreshBtn").addEventListener("click", refreshRecords);
  $("#resetBtn").addEventListener("click", resetCurrentEvent);
  $("#downloadBtn").addEventListener("click", downloadExcel);
  $("#downloadBtnInline").addEventListener("click", downloadExcel);
  $("#newEventBtn").addEventListener("click", openEventDialog);
  $("#saveEventBtn").addEventListener("click", createEvent);
  $("#saveEditBtn").addEventListener("click", saveEdit);
  $("#closeImageBtn").addEventListener("click", () => $("#imageDialog").close());
  $("#imageDialog").addEventListener("click", (event) => {
    if (event.target.id === "imageDialog") $("#imageDialog").close();
  });
  await checkHealth();
  await loadEvents();
  await loadRecords();
  await loadUsage();
});

async function checkHealth() {
  try {
    const data = await fetchJson("/health");
    $("#health").textContent = data.gemini_configured && data.google_vision_configured
      ? `API online - Vision OCR + Gemini (${data.gemini_key_count || 0} key${data.gemini_key_count === 1 ? "" : "s"})`
      : "API online - configure Gemini and Google Vision";
  } catch {
    $("#health").textContent = "API offline";
  }
}

async function loadEvents() {
  const events = await fetchJson("/events");
  state.events = events || [];
  const select = $("#eventSelect");
  const previous = state.eventId;
  select.innerHTML = "";
  state.events.forEach((event) => {
    const option = document.createElement("option");
    option.value = event.event_id;
    option.textContent = `${event.name}${event.location ? ` - ${event.location}` : ""}`;
    select.appendChild(option);
  });
  if (state.events.some((event) => event.event_id === previous)) {
    state.eventId = previous;
    select.value = previous;
  } else {
    state.eventId = select.value || "test_uploads";
  }
  updateEventMeta();
  select.addEventListener("change", () => {
    state.eventId = select.value;
    updateEventMeta();
    loadRecords();
    loadUsage();
  });
}

function updateEventMeta() {
  const event = state.events.find((item) => item.event_id === state.eventId);
  $("#eventMeta").textContent = event
    ? `${event.date}${event.location ? ` - ${event.location}` : ""}`
    : "No event selected";
  $("#downloadBtn").disabled = !event;
  $("#downloadBtnInline").disabled = !event;
}

function openEventDialog() {
  const today = new Date().toISOString().slice(0, 10);
  $("#eventName").value = "";
  $("#eventDate").value = today;
  $("#eventLocation").value = "";
  $("#eventDialog").showModal();
}

async function createEvent(event) {
  event.preventDefault();
  const name = $("#eventName").value.trim();
  const date = $("#eventDate").value;
  const location = $("#eventLocation").value.trim();
  if (!name || !date) return setMessage("Event name and date are required.");
  $("#saveEventBtn").disabled = true;
  try {
    const created = await fetchJson("/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, date, location }),
    });
    state.eventId = created.event_id;
    $("#eventDialog").close();
    await loadEvents();
    await loadRecords();
    setMessage(`Created event: ${created.name}`);
  } catch (error) {
    setMessage(error.message);
  } finally {
    $("#saveEventBtn").disabled = false;
  }
}

async function uploadCard() {
  const front = $("#frontInput").files[0];
  const back = $("#backInput").files[0];
  if (!front) return setMessage("Select a front image first.");
  const form = new FormData();
  form.append("front", front);
  if (back) form.append("back", back);
  setMessage("Processing card with Google Vision OCR and Gemini sorting...");
  $("#processBtn").disabled = true;
  try {
    const result = await fetchJson(`/events/${state.eventId}/cards`, { method: "POST", body: form });
    setMessage(result.error_message || `Processed with ${result.card.confidence_score} confidence.`);
    $("#frontInput").value = "";
    $("#backInput").value = "";
    await loadRecords();
    await loadUsage();
  } catch (error) {
    setMessage(error.message);
  } finally {
    $("#processBtn").disabled = false;
  }
}

async function loadRecords() {
  const data = await fetchJson(`/events/${state.eventId}/cards`);
  state.records = data.records || [];
  $("#recordSummary").textContent = `${state.records.length} card${state.records.length === 1 ? "" : "s"} in this event`;
  const body = $("#recordsBody");
  body.innerHTML = "";
  if (!state.records.length) {
    body.innerHTML = `<tr><td colspan="11" class="empty-state">No cards in this event yet.</td></tr>`;
    return;
  }
  state.records.forEach((record) => {
    const tr = document.createElement("tr");
    const image = record.front_image_filename
      ? `/events/${state.eventId}/images/${encodeURIComponent(record.front_image_filename)}`
      : "";
    tr.innerHTML = `
      <td>${image ? `<img class="thumb" src="${image}" alt="Card front" data-full-image="${image}">` : ""}</td>
      <td>${escapeHtml(record.name || "")}</td>
      <td>${escapeHtml(record.business || record.company || "")}</td>
      <td>${escapeHtml(record.category || "")}</td>
      <td>${escapeHtml(record.contact1 || "")}</td>
      <td>${escapeHtml(record.contact2 || "")}</td>
      <td>${escapeHtml(record.contact3 || "")}</td>
      <td>${escapeHtml(record.email1 || record.email || "")}</td>
      <td><span class="badge ${escapeHtml(record.confidence_score)}">${escapeHtml(record.confidence_score)}</span></td>
      <td>${escapeHtml(record.duplicate_flag || "No")}</td>
      <td><button class="btn secondary" data-edit="${record.card_id}">Edit</button></td>
    `;
    const thumb = tr.querySelector("[data-full-image]");
    if (thumb) thumb.addEventListener("click", () => openImage(thumb.dataset.fullImage));
    tr.querySelector("[data-edit]").addEventListener("click", () => openEdit(record));
    body.appendChild(tr);
  });
}

async function refreshRecords() {
  const button = $("#refreshBtn");
  button.disabled = true;
  setMessage("Refreshing records...");
  try {
    await loadRecords();
    await loadUsage();
    setMessage(`Refreshed ${state.records.length} records.`);
  } catch (error) {
    setMessage(error.message);
  } finally {
    button.disabled = false;
  }
}

async function resetCurrentEvent() {
  const ok = window.confirm("Start a new file? This will delete all records, images, OCR text, and Excel exports for the selected event.");
  if (!ok) return;
  const button = $("#resetBtn");
  button.disabled = true;
  setMessage("Starting a new file...");
  try {
    const result = await fetchJson(`/events/${state.eventId}/cards`, { method: "DELETE" });
    await loadRecords();
    await loadUsage();
    setMessage(`New file ready. Deleted ${result.deleted.records || 0} records and ${result.deleted.images || 0} images.`);
  } catch (error) {
    setMessage(error.message);
  } finally {
    button.disabled = false;
  }
}

function openImage(imageUrl) {
  $("#fullCardImage").src = imageUrl;
  $("#imageDialog").showModal();
}

async function loadUsage() {
  try {
    const usage = await fetchJson("/llm-usage");
    const gemini = usage.gemini || usage;
    const vision = usage.google_vision || {};
    const geminiAlerts = [
      quotaAlert("Gemini daily requests", gemini.daily_requests, gemini.daily_request_limit),
      quotaAlert("Gemini minute requests", gemini.minute_requests, gemini.minute_request_limit),
      quotaAlert("Gemini daily tokens", gemini.daily_tokens_estimated, gemini.daily_token_limit),
    ].filter(Boolean);
    const visionAlerts = [
      quotaAlert("Google Vision minute requests", vision.minute_requests, vision.minute_request_limit),
      quotaAlert("Google Vision free monthly OCR units", vision.monthly_units, vision.free_units_monthly),
    ].filter(Boolean);
    const geminiStatus = quotaStatus([
      quotaPercent(gemini.daily_requests, gemini.daily_request_limit),
      quotaPercent(gemini.minute_requests, gemini.minute_request_limit),
      quotaPercent(gemini.daily_tokens_estimated, gemini.daily_token_limit),
    ]);
    const visionStatus = quotaStatus([
      quotaPercent(vision.minute_requests, vision.minute_request_limit),
      quotaPercent(vision.monthly_units, vision.free_units_monthly),
    ]);
    const keyLines = gemini.by_key
      ? Object.entries(gemini.by_key).map(([key, count]) => `<div class="usage-sub">${escapeHtml(key)}: ${count} request${count === 1 ? "" : "s"} today</div>`).join("")
      : "";
    $("#llmUsage").innerHTML = `
      <div class="usage-grid">
        <section class="usage-provider ${geminiStatus}">
          <div class="usage-provider-title">
            <strong>Gemini</strong>
            <span>${gemini.key_count ?? 0} key${Number(gemini.key_count || 0) === 1 ? "" : "s"}</span>
          </div>
          <div>${formatQuota("Requests today", gemini.daily_requests, gemini.daily_request_limit)}</div>
          <div>${formatQuota("Requests this minute", gemini.minute_requests, gemini.minute_request_limit)}</div>
          <div>${formatQuota("Estimated tokens today", gemini.daily_tokens_estimated, gemini.daily_token_limit)}</div>
          ${keyLines}
          ${renderAlerts(geminiAlerts, geminiStatus)}
        </section>
        <section class="usage-provider ${visionStatus}">
          <div class="usage-provider-title">
            <strong>Google Vision</strong>
            <span>OCR</span>
          </div>
          <div>Requests today: ${vision.daily_requests ?? 0}</div>
          <div>${formatQuota("Requests this minute", vision.minute_requests, vision.minute_request_limit)}</div>
          <div>${formatQuota("Monthly OCR units", vision.monthly_units, vision.free_units_monthly)}</div>
          <div>Estimated OCR cost: $${Number(vision.estimated_cost_usd || 0).toFixed(4)}</div>
          ${renderAlerts(visionAlerts, visionStatus)}
        </section>
      </div>
      <div class="usage-note">${escapeHtml(usage.note || "Local monitor only.")}</div>
    `;
  } catch {
    $("#llmUsage").textContent = "Usage unavailable";
  }
}

function formatQuota(label, used, limit) {
  const safeUsed = Number(used || 0);
  const safeLimit = Number(limit || 0);
  const suffix = safeLimit > 0 ? `${safeUsed} / ${safeLimit}` : `${safeUsed} / console limit`;
  const percent = safeLimit > 0 ? ` (${Math.round((safeUsed / safeLimit) * 100)}%)` : "";
  return `${label}: ${suffix}${percent}`;
}

function quotaPercent(used, limit) {
  const safeLimit = Number(limit || 0);
  if (!safeLimit) return 0;
  return Number(used || 0) / safeLimit;
}

function quotaStatus(percentages) {
  if (percentages.some((value) => value >= 0.95)) return "danger";
  if (percentages.some((value) => value >= 0.8)) return "warning";
  return "ok";
}

function quotaAlert(label, used, limit) {
  const percent = quotaPercent(used, limit);
  if (percent >= 0.95) return `${label} is at ${Math.round(percent * 100)}%. Stop and switch keys/quota soon.`;
  if (percent >= 0.8) return `${label} is at ${Math.round(percent * 100)}%. You are close to quota.`;
  return "";
}

function renderAlerts(alerts, status) {
  if (!alerts.length) return "";
  return `<div class="usage-alert ${status}">${alerts.map(escapeHtml).join("<br>")}</div>`;
}

function openEdit(record) {
  $("#editCardId").value = record.card_id;
  $("#editName").value = record.name || "";
  $("#editDesignation").value = record.designation || "";
  $("#editCompany").value = record.company || "";
  $("#editBusiness").value = record.business || record.company || "";
  $("#editEmail1").value = record.email1 || record.email || "";
  $("#editEmail2").value = record.email2 || "";
  $("#editContact1").value = record.contact1 || "";
  $("#editContact2").value = record.contact2 || "";
  $("#editContact3").value = record.contact3 || "";
  $("#editWebsite").value = record.website || "";
  $("#editSocialMedia").value = record.social_media || "";
  $("#editNotes").value = record.notes || "";
  $("#editAddress").value = record.address || "";
  $("#editCategory").value = record.category || "";
  $("#editDialog").showModal();
}

async function saveEdit(event) {
  event.preventDefault();
  const cardId = $("#editCardId").value;
  await fetchJson(`/events/${state.eventId}/cards/${cardId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: $("#editName").value,
      designation: $("#editDesignation").value,
      company: $("#editCompany").value,
      business: $("#editBusiness").value,
      email1: $("#editEmail1").value,
      email2: $("#editEmail2").value,
      contact1: $("#editContact1").value,
      contact2: $("#editContact2").value,
      contact3: $("#editContact3").value,
      website: $("#editWebsite").value,
      social_media: $("#editSocialMedia").value,
      notes: $("#editNotes").value,
      address: $("#editAddress").value,
      category: $("#editCategory").value,
    }),
  });
  $("#editDialog").close();
  setMessage("Record saved.");
  await loadRecords();
}

function downloadExcel() {
  if (!state.eventId) return setMessage("Select an event first.");
  setMessage("Preparing event Excel file...");
  window.open(`/events/${state.eventId}/download`, "_blank");
}

function setMessage(message) {
  $("#message").textContent = message;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(data.detail || `Request failed: ${response.status}`);
  return data;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}
