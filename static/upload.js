const state = { eventId: "test_uploads", records: [] };

const $ = (selector) => document.querySelector(selector);

document.addEventListener("DOMContentLoaded", async () => {
  $("#processBtn").addEventListener("click", uploadCard);
  $("#refreshBtn").addEventListener("click", refreshRecords);
  $("#resetBtn").addEventListener("click", resetCurrentEvent);
  $("#downloadBtn").addEventListener("click", downloadExcel);
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
    $("#health").textContent = data.gemini_configured
      ? "API online - Gemini Vision ready"
      : "API online - configure Gemini to process images";
  } catch {
    $("#health").textContent = "API offline";
  }
}

async function loadEvents() {
  const events = await fetchJson("/events");
  const select = $("#eventSelect");
  select.innerHTML = "";
  events.forEach((event) => {
    const option = document.createElement("option");
    option.value = event.event_id;
    option.textContent = event.name;
    select.appendChild(option);
  });
  state.eventId = select.value || "test_uploads";
  select.addEventListener("change", () => {
    state.eventId = select.value;
    loadRecords();
    loadUsage();
  });
}

async function uploadCard() {
  const front = $("#frontInput").files[0];
  const back = $("#backInput").files[0];
  if (!front) return setMessage("Select a front image first.");
  const form = new FormData();
  form.append("front", front);
  if (back) form.append("back", back);
  setMessage("Processing card with one Gemini Vision call...");
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
  const body = $("#recordsBody");
  body.innerHTML = "";
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
      <td>${escapeHtml(record.country_code || "")}</td>
      <td>${escapeHtml(record.phone_number || "")}</td>
      <td>${escapeHtml(record.mobile_number || "")}</td>
      <td>${escapeHtml(record.fax_number || "")}</td>
      <td>${escapeHtml(record.email || "")}</td>
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
    $("#llmUsage").innerHTML = `
      <div>Requests today: ${usage.daily_requests} / ${usage.daily_request_limit}</div>
      <div>Requests this minute: ${usage.minute_requests} / ${usage.minute_request_limit}</div>
      <div>Estimated tokens today: ${usage.daily_tokens_estimated} / ${usage.daily_token_limit}</div>
    `;
  } catch {
    $("#llmUsage").textContent = "Usage unavailable";
  }
}

function openEdit(record) {
  $("#editCardId").value = record.card_id;
  $("#editName").value = record.name || "";
  $("#editDesignation").value = record.designation || "";
  $("#editCompany").value = record.company || "";
  $("#editBusiness").value = record.business || record.company || "";
  $("#editCountryCode").value = record.country_code || "";
  $("#editPhoneNumber").value = record.phone_number || "";
  $("#editMobileNumber").value = record.mobile_number || "";
  $("#editFaxNumber").value = record.fax_number || "";
  $("#editEmail").value = record.email || "";
  $("#editWebsite").value = record.website || "";
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
      country_code: $("#editCountryCode").value,
      phone_number: $("#editPhoneNumber").value,
      mobile_number: $("#editMobileNumber").value,
      fax_number: $("#editFaxNumber").value,
      email: $("#editEmail").value,
      website: $("#editWebsite").value,
      address: $("#editAddress").value,
      category: $("#editCategory").value,
    }),
  });
  $("#editDialog").close();
  setMessage("Record saved.");
  await loadRecords();
}

function downloadExcel() {
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
