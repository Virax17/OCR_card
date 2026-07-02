const state = {
  eventId: "test_uploads",
  events: [],
  records: [],
  activeMode: "single",
  bulkFiles: [],
  bulkConfirmed: false,
  processing: false,
};

const $ = (selector) => document.querySelector(selector);

document.addEventListener("DOMContentLoaded", async () => {
  $("#processBtn").addEventListener("click", processActiveMode);
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
  setupTabs();
  setupFileLabels();
  setupBulkPreview();
  setupCameraPreview();
  updateProcessButton();
  await checkHealth();
  await loadEvents();
  await loadRecords();
  await loadUsage();
});

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tabpane").forEach((pane) => pane.classList.remove("active"));
      button.classList.add("active");
      $(`#tab-${button.dataset.tab}`).classList.add("active");
      state.activeMode = button.dataset.tab;
      updateProcessButton();
      if (button.dataset.tab === "bulk") {
        setMessage(state.bulkFiles.length ? "Confirm the selected bulk images before processing." : "Add images, confirm selection, then process the batch.");
      } else if (button.dataset.tab === "camera") {
        setMessage("Capture a card image. It will be added as the front image for single-card processing.");
      } else {
        setMessage("");
      }
    });
  });
}

function setupFileLabels() {
  $("#frontInput").addEventListener("change", () => updateFileLabel("frontInput", "frontFileName"));
  $("#backInput").addEventListener("change", () => updateFileLabel("backInput", "backFileName"));
}

function updateFileLabel(inputId, labelId) {
  const file = $(`#${inputId}`).files[0];
  $(`#${labelId}`).textContent = file ? file.name : "No file chosen";
}

function setupBulkPreview() {
  const dropzone = $("#dropzone");
  const bulkInput = $("#bulkInput");
  if (!dropzone || !bulkInput) return;
  dropzone.addEventListener("click", () => bulkInput.click());
  $("#confirmBulkBtn").addEventListener("click", confirmBulkSelection);
  bulkInput.addEventListener("change", () => setBulkFiles(bulkInput.files));
  ["dragenter", "dragover"].forEach((name) => {
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    });
  });
  ["dragleave", "drop"].forEach((name) => {
    dropzone.addEventListener(name, (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });
  dropzone.addEventListener("drop", (event) => {
    setBulkFiles(event.dataTransfer.files);
  });
}

function setBulkFiles(files) {
  state.bulkFiles = Array.from(files || []).filter((file) => file.type.startsWith("image/"));
  state.bulkConfirmed = false;
  renderPreviewQueue(state.bulkFiles, "bulkQueue", "Needs confirmation");
  $("#confirmBulkBtn").disabled = !state.bulkFiles.length;
  updateProcessButton();
  if (state.bulkFiles.length) {
    setMessage(`${state.bulkFiles.length} image${state.bulkFiles.length === 1 ? "" : "s"} selected. Click Confirm Bulk Selection.`);
  }
}

function confirmBulkSelection() {
  if (!state.bulkFiles.length) return setMessage("Add bulk images first.");
  state.bulkConfirmed = true;
  renderPreviewQueue(state.bulkFiles, "bulkQueue", "Confirmed");
  $("#confirmBulkBtn").disabled = true;
  updateProcessButton();
  setMessage(`${state.bulkFiles.length} bulk card${state.bulkFiles.length === 1 ? "" : "s"} confirmed. Click Process ${state.bulkFiles.length} Cards.`);
}

function renderPreviewQueue(files, queueId, statusText) {
  const queue = $(`#${queueId}`);
  const imageFiles = Array.from(files || []).filter((file) => file.type.startsWith("image/"));
  queue.innerHTML = imageFiles.map((file) => `
    <div class="queue-item">
      <img src="${URL.createObjectURL(file)}" alt="">
      <div class="qmeta"><strong>${escapeHtml(file.name)}</strong><span>${escapeHtml(statusText)}</span></div>
    </div>
  `).join("");
  if (imageFiles.length) setMessage(`${imageFiles.length} image${imageFiles.length === 1 ? "" : "s"} added to preview queue.`);
}

function setupCameraPreview() {
  const enableButton = $("#enableCamBtn");
  const shutterButton = $("#shutterBtn");
  const cameraBox = $("#cameraBox");
  if (!enableButton || !shutterButton || !cameraBox) return;
  let video;
  enableButton.addEventListener("click", async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      cameraBox.innerHTML = `<div class="camera-placeholder">Camera capture is not available in this browser.</div>`;
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      video = document.createElement("video");
      video.autoplay = true;
      video.playsInline = true;
      video.srcObject = stream;
      cameraBox.innerHTML = "";
      cameraBox.appendChild(video);
      shutterButton.hidden = false;
      enableButton.textContent = "Camera On";
      enableButton.disabled = true;
    } catch {
      cameraBox.innerHTML = `<div class="camera-placeholder">Could not access camera. Check browser permissions.</div>`;
    }
  });
  shutterButton.addEventListener("click", async () => {
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 960;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    if (!blob) return;
    const file = new File([blob], `camera-card-${Date.now()}.jpg`, { type: "image/jpeg" });
    const transfer = new DataTransfer();
    transfer.items.add(file);
    $("#frontInput").files = transfer.files;
    updateFileLabel("frontInput", "frontFileName");
    renderPreviewQueue([file], "cameraQueue", "Captured to front image");
    document.querySelector('[data-tab="single"]').click();
    setMessage("Camera capture added as the front image. Click Process Card.");
  });
}

function updateProcessButton() {
  const button = $("#processBtn");
  if (!button) return;
  if (state.processing) return;
  if (state.activeMode === "bulk") {
    button.textContent = state.bulkFiles.length ? `Process ${state.bulkFiles.length} Card${state.bulkFiles.length === 1 ? "" : "s"}` : "Process Bulk Cards";
    button.disabled = !state.bulkFiles.length || !state.bulkConfirmed;
    return;
  }
  button.textContent = "Process Card";
  button.disabled = false;
}

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

async function processActiveMode() {
  if (state.activeMode === "bulk") return uploadBulkCards();
  return uploadCard();
}

async function uploadCard() {
  const front = $("#frontInput").files[0];
  const back = $("#backInput").files[0];
  if (!front) return setMessage("Select a front image first.");
  const form = new FormData();
  form.append("front", front);
  if (back) form.append("back", back);
  setMessage("Processing card with Google Vision OCR and Gemini sorting...");
  state.processing = true;
  $("#processBtn").disabled = true;
  $("#processBtn").textContent = "Processing...";
  const progress = startSingleProgress(front.name);
  try {
    const result = await fetchJson(`/events/${state.eventId}/cards`, { method: "POST", body: form });
    finishSingleProgress(result.status === "error" ? "error" : "done", result.error_message || "Saved to records");
    setMessage(result.error_message || `Processed with ${result.card.confidence_score} confidence.`);
    $("#frontInput").value = "";
    $("#backInput").value = "";
    updateFileLabel("frontInput", "frontFileName");
    updateFileLabel("backInput", "backFileName");
    await loadRecords();
    await loadUsage();
  } catch (error) {
    finishSingleProgress("error", error.message);
    setMessage(error.message);
  } finally {
    window.clearInterval(progress);
    state.processing = false;
    updateProcessButton();
  }
}

async function uploadBulkCards() {
  if (!state.bulkFiles.length) return setMessage("Add bulk images first.");
  if (!state.bulkConfirmed) return setMessage("Confirm the bulk selection before processing.");
  state.processing = true;
  $("#processBtn").disabled = true;
  $("#processBtn").textContent = "Processing...";
  $("#confirmBulkBtn").disabled = true;
  showProgressTickets(state.bulkFiles);
  let successCount = 0;
  let failCount = 0;
  setMessage(`Processing ${state.bulkFiles.length} bulk cards...`);
  for (let index = 0; index < state.bulkFiles.length; index += 1) {
    const file = state.bulkFiles[index];
    updateTicket(index, "busy", "Vision OCR + Gemini");
    try {
      const form = new FormData();
      form.append("front", file);
      const result = await fetchJson(`/events/${state.eventId}/cards`, { method: "POST", body: form });
      if (result.status === "error") {
        failCount += 1;
        updateTicket(index, "error", result.error_message || "Failed");
      } else {
        successCount += 1;
        updateTicket(index, "done", result.card?.confidence_score ? `Done - ${result.card.confidence_score}` : "Done");
      }
    } catch (error) {
      failCount += 1;
      updateTicket(index, "error", error.message);
    }
    updateProgress(index + 1, state.bulkFiles.length);
    await loadUsage();
  }
  await loadRecords();
  state.bulkFiles = [];
  state.bulkConfirmed = false;
  $("#bulkInput").value = "";
  $("#bulkQueue").innerHTML = "";
  setMessage(`Bulk processing complete. ${successCount} done, ${failCount} failed.`);
  state.processing = false;
  updateProcessButton();
}

function showProgressTickets(files) {
  $("#progressPanel").hidden = false;
  $("#progressTitle").textContent = files.length === 1 ? "Processing Card" : "Processing Bulk Queue";
  $("#progressFill").style.width = "0%";
  $("#progressFill").classList.add("active");
  $("#progressPercent").textContent = "0%";
  $("#ticketList").innerHTML = files.map((file, index) => `
    <div class="ticket" data-ticket-index="${index}">
      <div class="status-icon queued">...</div>
      <div class="tname">${escapeHtml(file.name)}</div>
      <div class="tstage">Queued</div>
    </div>
  `).join("");
}

function updateTicket(index, status, stage) {
  const ticket = document.querySelector(`[data-ticket-index="${index}"]`);
  if (!ticket) return;
  const icon = ticket.querySelector(".status-icon");
  const stageEl = ticket.querySelector(".tstage");
  ticket.classList.toggle("scanning", status === "busy");
  icon.className = `status-icon ${status}`;
  icon.textContent = status === "done" ? "OK" : status === "error" ? "!" : "...";
  stageEl.textContent = stage;
}

function updateProgress(done, total) {
  const percent = Math.round((done / total) * 100);
  $("#progressFill").style.width = `${percent}%`;
  $("#progressPercent").textContent = `${percent}%`;
  if (percent >= 100) $("#progressFill").classList.remove("active");
}

function startSingleProgress(fileName) {
  $("#progressPanel").hidden = false;
  $("#progressTitle").textContent = "Processing Card";
  $("#progressFill").classList.add("active");
  $("#progressFill").style.width = "8%";
  $("#progressPercent").textContent = "8%";
  $("#ticketList").innerHTML = `
    <div class="ticket scanning" data-ticket-index="0">
      <div class="status-icon busy">...</div>
      <div class="tname">${escapeHtml(fileName)}</div>
      <div class="tstage">Uploading image</div>
    </div>
  `;
  const stages = [
    [20, "Google Vision OCR"],
    [45, "Extracting field candidates"],
    [70, "Gemini sorting"],
    [86, "Validating fields"],
    [94, "Saving record"],
  ];
  let index = 0;
  return window.setInterval(() => {
    if (index >= stages.length) return;
    const [percent, label] = stages[index];
    $("#progressFill").style.width = `${percent}%`;
    $("#progressPercent").textContent = `${percent}%`;
    updateTicket(0, "busy", label);
    index += 1;
  }, 1200);
}

function finishSingleProgress(status, label) {
  $("#progressFill").style.width = "100%";
  $("#progressPercent").textContent = "100%";
  $("#progressFill").classList.remove("active");
  updateTicket(0, status, label);
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
      <td>${escapeHtml(formatPhoneForDisplay(record.contact1 || record.mobile_number || record.phone_primary, record.country_code))}</td>
      <td>${escapeHtml(formatPhoneForDisplay(record.contact2 || record.phone_number, record.country_code))}</td>
      <td>${escapeHtml(formatPhoneForDisplay(record.contact3 || record.fax_number, record.country_code))}</td>
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

function formatPhoneForDisplay(value, countryCode) {
  if (!value) return "";
  const digits = String(value).replace(/\D/g, "");
  if (!digits) return String(value).trim();
  let codeDigits = String(countryCode || "").replace(/\D/g, "");
  if (!codeDigits && String(value).trim().startsWith("+")) {
    const knownCodes = ["91", "62", "971", "966", "974", "968", "965", "973", "1", "44", "65", "60"];
    codeDigits = knownCodes.find((code) => digits.startsWith(code)) || "";
  }
  let national = digits;
  if (codeDigits && national.startsWith(codeDigits)) national = national.slice(codeDigits.length);
  national = national.replace(/^0+/, "") || digits;
  return codeDigits ? `(+${codeDigits}) ${national}` : national;
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
