import * as api from "./api.js";
import { escapeHtml, formatPhoneForDisplay, debounce, isDuplicate, needsReview, normalizeWebsiteUrl } from "./utils.js";

const $ = (selector) => document.querySelector(selector);

let editMode = false;
let activeRecord = null;
// Review-queue state: null when the sheet was opened normally; otherwise
// { records, index } so Previous/Next can step through the flagged set.
let reviewQueue = null;

export function wireRecordsScreen() {
  $("#recordSearch").addEventListener("input", debounce(async () => {
    const { state } = await import("./app-shell.js");
    state.filters.search = $("#recordSearch").value.trim().toLowerCase();
    renderRecords(state);
  }, 250));

  document.querySelectorAll('.chip[data-filter]').forEach((chip) => {
    chip.addEventListener("click", async () => {
      const { state } = await import("./app-shell.js");
      document.querySelectorAll('.chip[data-filter]').forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.filters.needsReviewOnly = chip.dataset.filter === "needs-review";
      renderRecords(state);
    });
  });

  $("#recordsMenuBtn").addEventListener("click", openRecordsMenu);
  $("#recordsMenuSheet").addEventListener("click", (event) => {
    if (event.target.id === "recordsMenuSheet") $("#recordsMenuSheet").close();
  });
  $("#menuRefreshBtn").addEventListener("click", async () => {
    $("#recordsMenuSheet").close();
    const { refreshAll, showToast } = await import("./app-shell.js");
    await refreshAll();
    showToast("Records refreshed.", "success");
  });
  $("#menuExportBtn").addEventListener("click", async () => {
    $("#recordsMenuSheet").close();
    const { state, showToast } = await import("./app-shell.js");
    if (!state.online) return showToast("Export requires a connection.", "error");
    window.open(api.downloadUrl(state.eventId), "_blank");
  });
  $("#menuResetBtn").addEventListener("click", () => {
    $("#recordsMenuSheet").close();
    openResetConfirm();
  });
  $("#moreResetBtn")?.addEventListener("click", openResetConfirm);

  wireResetConfirm();
  wireRecordSheet();
  wireReviewQueue();
  wireImageDialog();
}

export function openRecordsMenu() {
  $("#recordsMenuSheet").showModal();
}

function wireResetConfirm() {
  $("#resetConfirmCancelBtn").addEventListener("click", () => $("#resetConfirmSheet").close());
  $("#resetConfirmSheet").addEventListener("click", (event) => {
    if (event.target.id === "resetConfirmSheet") $("#resetConfirmSheet").close();
  });
  $("#resetConfirmInput").addEventListener("input", async () => {
    const { state } = await import("./app-shell.js");
    const event = state.events.find((e) => e.event_id === state.eventId);
    $("#resetConfirmDeleteBtn").disabled = $("#resetConfirmInput").value.trim() !== (event?.name || "");
  });
  $("#resetConfirmDeleteBtn").addEventListener("click", async () => {
    const { state, refreshAll, showToast } = await import("./app-shell.js");
    if (!state.online) return showToast("Reset requires a connection.", "error");
    $("#resetConfirmDeleteBtn").disabled = true;
    try {
      const result = await api.resetCards(state.eventId);
      $("#resetConfirmSheet").close();
      await refreshAll();
      showToast(`Deleted ${result.deleted.records || 0} records and ${result.deleted.images || 0} images.`, "success");
    } catch (error) {
      showToast(error.message, "error");
    }
  });
}

async function openResetConfirm() {
  const { state } = await import("./app-shell.js");
  const event = state.events.find((e) => e.event_id === state.eventId);
  $("#resetConfirmEventName").textContent = event?.name || state.eventId || "";
  $("#resetConfirmInput").value = "";
  $("#resetConfirmDeleteBtn").disabled = true;
  $("#resetConfirmSheet").showModal();
}

export async function refreshRecords(state) {
  renderRecords(state);
}

export function renderRecords(state) {
  const filtered = applyFilters(state);
  $("#recordsCountBadge").textContent = state.records.length ? `(${filtered.length}/${state.records.length})` : "";
  renderReviewAllBanner(state, filtered);

  const emptyEl = $("#recordsEmptyState");
  const listEl = $("#recordsList");
  const tableWrapEl = $("#recordsTableWrap");

  if (state.loading) {
    emptyEl.innerHTML = "";
    tableWrapEl.style.display = "";
    renderMobileList(state, filtered);
    renderDesktopTable(state, filtered);
    return;
  }

  if (state.eventId && !filtered.length) {
    emptyEl.innerHTML = emptyStateHtml(state);
    listEl.innerHTML = "";
    tableWrapEl.style.display = "none";
    wireEmptyStateScan(emptyEl);
    return;
  }

  emptyEl.innerHTML = "";
  tableWrapEl.style.display = "";
  renderMobileList(state, filtered);
  renderDesktopTable(state, filtered);
}

// A "Review all" shortcut when the Needs-review filter is active — jumps
// straight into the edit-first Next/Previous flow instead of tapping every
// flagged row one at a time.
function renderReviewAllBanner(state, filtered) {
  const wrap = $("#recordsReviewAllWrap");
  if (!wrap) return;
  if (state.loading || !state.filters.needsReviewOnly || !filtered.length) {
    wrap.innerHTML = "";
    return;
  }
  wrap.innerHTML = `
    <button id="recordsReviewAllBtn" class="btn outline block" type="button" style="margin:var(--space-2) 0 var(--space-3)">
      Review all ${filtered.length} &rarr;
    </button>
  `;
  $("#recordsReviewAllBtn").addEventListener("click", () => openReviewQueue(filtered));
}

function emptyStateHtml(state) {
  if (!state.records.length) {
    return `
      <div class="empty-card">
        <svg class="icon" aria-hidden="true" style="width:40px;height:40px;color:var(--text-dim)"><use href="#icon-camera"/></svg>
        <strong>No cards scanned yet</strong>
        Tap Scan to add your first card.
        <button class="btn primary" id="emptyStateScanBtn" type="button" style="margin-top:var(--space-3)">Scan a card</button>
      </div>
    `;
  }
  return `
    <div class="empty-card">
      <svg class="icon" aria-hidden="true" style="width:40px;height:40px;color:var(--text-dim)"><use href="#icon-search"/></svg>
      <strong>No matches</strong>
      Try a different search or filter.
    </div>
  `;
}

function wireEmptyStateScan(container) {
  container.querySelector("#emptyStateScanBtn")?.addEventListener("click", async () => {
    const { openScanScreen } = await import("./scan.js");
    openScanScreen();
  });
}

function applyFilters(state) {
  let list = [...state.records];
  const { search, needsReviewOnly } = state.filters;
  if (needsReviewOnly) list = list.filter(needsReview);
  if (search) {
    list = list.filter((r) => {
      const haystack = [r.name, r.company, r.business, r.email1, r.email, r.contact1, r.contact2, r.phone_primary]
        .filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(search);
    });
  }
  return list;
}

function renderMobileList(state, records) {
  const list = $("#recordsList");
  if (state.loading) {
    list.innerHTML = skeletonCards(5);
    return;
  }
  if (!state.eventId || !records.length) {
    list.innerHTML = "";
    return;
  }
  list.innerHTML = records.map((record) => cardHtml(state, record)).join("");
  list.querySelectorAll("[data-card-id]").forEach((el) => {
    el.addEventListener("click", () => {
      const record = state.records.find((r) => r.card_id === el.dataset.cardId);
      if (record) openRecordDetail(record);
    });
  });
}

function skeletonCards(count) {
  return Array.from({ length: count }, () => `
    <div class="contact-card contact-card--skeleton">
      <div class="skeleton-block contact-card-thumb"></div>
      <div class="contact-card-body">
        <div class="skeleton-line" style="width:50%"></div>
        <div class="skeleton-line" style="width:70%"></div>
        <div class="skeleton-line" style="width:40%"></div>
      </div>
    </div>
  `).join("");
}

function reviewChipHtml(record) {
  if (isDuplicate(record)) return `<span class="status-chip duplicate">Duplicate</span>`;
  return "";
}

function cardHtml(state, record) {
  const image = record.front_image_filename ? api.imageUrl(state.eventId, record.front_image_filename) : "";
  const phone = formatPhoneForDisplay(record.contact1 || record.mobile_number || record.phone_primary, record.country_code);
  const email = record.email1 || record.email || "";
  return `
    <div class="contact-card" data-card-id="${escapeHtml(record.card_id)}">
      ${image ? `<img class="contact-card-thumb" src="${image}" alt="">` : `<div class="contact-card-thumb"></div>`}
      <div class="contact-card-body">
        <div class="contact-card-name">${escapeHtml(record.name || "Unnamed")}</div>
        <div class="contact-card-meta">${escapeHtml([record.designation, record.company || record.business].filter(Boolean).join(" · "))}</div>
        <div class="contact-card-sub">${escapeHtml([phone, email].filter(Boolean).join(" · "))}</div>
      </div>
      <div class="contact-card-side">
        ${reviewChipHtml(record)}
      </div>
    </div>
  `;
}

function renderDesktopTable(state, records) {
  const body = $("#recordsTableBody");
  if (!records.length) {
    body.innerHTML = `<tr><td colspan="7" class="empty-state" style="padding:24px;text-align:center;color:var(--text-dim)">No records to show.</td></tr>`;
    return;
  }
  body.innerHTML = records.map((record) => {
    const image = record.front_image_filename ? api.imageUrl(state.eventId, record.front_image_filename) : "";
    const phone = formatPhoneForDisplay(record.contact1 || record.mobile_number || record.phone_primary, record.country_code);
    return `
      <tr data-card-id="${escapeHtml(record.card_id)}">
        <td>${image ? `<img class="thumb" src="${image}" alt="">` : ""}</td>
        <td>${escapeHtml(record.name || "")}</td>
        <td>${escapeHtml(record.company || record.business || "")}</td>
        <td>${escapeHtml(record.category || "")}</td>
        <td>${escapeHtml(phone)}</td>
        <td>${escapeHtml(record.email1 || record.email || "")}</td>
        <td>${reviewChipHtml(record) || `<span class="status-chip reviewed">Reviewed</span>`}</td>
      </tr>
    `;
  }).join("");
  body.querySelectorAll("tr[data-card-id]").forEach((row) => {
    row.addEventListener("click", () => {
      const record = state.records.find((r) => r.card_id === row.dataset.cardId);
      if (record) openRecordDetail(record);
    });
  });
}

// ---- Record detail / edit sheet ----

const FIELD_GROUPS = [
  { title: "Identity", fields: [
    ["name", "Name"], ["designation", "Designation"], ["company", "Company"], ["business", "Business"], ["category", "Category"],
  ] },
  { title: "Contact", fields: [
    ["contact1", "Contact 1"], ["contact2", "Contact 2"], ["contact3", "Contact 3"], ["email1", "Email 1"], ["email2", "Email 2"],
  ] },
  { title: "Location", fields: [
    ["address", "Address"], ["city", "City"], ["state", "State"], ["country", "Country"], ["zip_code", "Zip"],
  ] },
  { title: "Web", fields: [
    ["website", "Website"], ["social_media", "Social media"],
  ] },
  { title: "Notes", fields: [
    ["notes", "Notes"],
  ] },
];

function wireRecordSheet() {
  $("#recordSheetCloseBtn").addEventListener("click", closeRecordSheet);
  $("#recordSheet").addEventListener("click", (event) => {
    if (event.target.id === "recordSheet") closeRecordSheet();
  });
  $("#recordEditToggleBtn").addEventListener("click", () => setEditMode(true));
  $("#recordEditCancelBtn").addEventListener("click", () => setEditMode(false));
  $("#recordEditSaveBtn").addEventListener("click", () => saveRecordEdit());
  $("#recordSheetImage").addEventListener("click", () => {
    if (activeRecord?.__imageUrl) openImage(activeRecord.__imageUrl);
  });
  $("#qaSaveContact").addEventListener("click", downloadVCard);
}

function closeRecordSheet() {
  $("#recordSheet").close();
  setEditMode(false);
  exitReviewQueue();
}

export async function openRecordDetail(record) {
  exitReviewQueue();
  const { state } = await import("./app-shell.js");
  activeRecord = record;
  activeRecord.__imageUrl = record.front_image_filename ? api.imageUrl(state.eventId, record.front_image_filename) : "";
  renderRecordView(record);
  setEditMode(false);
  $("#recordSheet").showModal();
}

// ---- Review-queue mode: edit-first, Next/Previous through flagged records ----

function wireReviewQueue() {
  $("#recordReviewPrevBtn").addEventListener("click", () => stepReviewQueue(-1));
  $("#recordReviewNextBtn").addEventListener("click", () => stepReviewQueue(1));
}

// Opens the record sheet pre-filtered to `records`, edit form shown by
// default, with Previous/Next controls — the direct fix for "ability to
// correct the mistakes" instead of hunting through the list one at a time.
export async function openReviewQueue(records) {
  if (!records || !records.length) return;
  reviewQueue = { records, index: 0 };
  await openReviewRecord(0);
}

async function openReviewRecord(index) {
  const record = reviewQueue.records[index];
  const { state } = await import("./app-shell.js");
  activeRecord = record;
  activeRecord.__imageUrl = record.front_image_filename ? api.imageUrl(state.eventId, record.front_image_filename) : "";
  renderRecordView(record);
  setEditMode(true);
  renderReviewBar();
  if (!$("#recordSheet").open) $("#recordSheet").showModal();
}

function renderReviewBar() {
  const bar = $("#recordReviewBar");
  if (!reviewQueue) {
    bar.hidden = true;
    return;
  }
  bar.hidden = false;
  const { records, index } = reviewQueue;
  $("#recordReviewProgress").textContent = `${index + 1} of ${records.length} need review`;
  $("#recordReviewPrevBtn").disabled = index === 0;
  $("#recordReviewNextBtn").textContent = index === records.length - 1 ? "Done" : "Save & next →";
}

// Saves the current record's edits (if any were made), then advances to the
// next flagged record or, past the last one, closes the sheet.
async function stepReviewQueue(direction) {
  if (!reviewQueue) return;
  if (direction > 0) {
    const saved = await saveRecordEdit({ silent: true });
    if (!saved) return; // save failed — stay put so the user can retry/fix
  }
  const nextIndex = reviewQueue.index + direction;
  if (nextIndex < 0) return;
  if (nextIndex >= reviewQueue.records.length) {
    const { showToast } = await import("./app-shell.js");
    $("#recordSheet").close();
    showToast("All caught up — nothing left to review.", "success");
    return;
  }
  reviewQueue.index = nextIndex;
  await openReviewRecord(nextIndex);
}

function exitReviewQueue() {
  reviewQueue = null;
  $("#recordReviewBar").hidden = true;
}

function renderRecordView(record) {
  $("#recordSheetImage").src = record.__imageUrl || "";
  $("#recordSheetImage").style.display = record.__imageUrl ? "block" : "none";
  $("#recordSheetName").textContent = record.name || "Unnamed";
  $("#recordSheetSubtitle").textContent = [record.designation, record.company || record.business].filter(Boolean).join(" · ");
  $("#recordDupBanner").classList.toggle("visible", isDuplicate(record));

  const phone = record.phone_primary || record.contact1;
  const email = record.email1 || record.email;
  setQuickAction("#qaCall", phone ? `tel:${phone}` : null);
  setQuickAction("#qaEmail", email ? `mailto:${email}` : null);
  const website = normalizeWebsiteUrl(record.website);
  setQuickAction("#qaWebsite", website);

  const view = $("#recordViewMode");
  view.innerHTML = FIELD_GROUPS.map((group) => {
    const rows = group.fields
      .map(([key, label]) => [key, label, record[key]])
      .filter(([, , value]) => value)
      .map(([, label, value]) => `
        <div class="field-row">
          <div class="field-row-label">${escapeHtml(label)}</div>
          <div class="field-row-value">${escapeHtml(value)}</div>
        </div>
      `).join("");
    if (!rows) return "";
    return `<div class="field-group"><div class="field-group-title">${escapeHtml(group.title)}</div>${rows}</div>`;
  }).join("") || `<p style="color:var(--text-dim)">No additional fields captured.</p>`;
}

function setQuickAction(selector, href) {
  const el = $(selector);
  if (href) {
    el.href = href;
    el.hidden = false;
  } else {
    el.hidden = true;
  }
}

function setEditMode(on) {
  editMode = on;
  $("#recordViewMode").hidden = on;
  $("#recordEditForm").hidden = !on;
  // In review-queue mode the dedicated Previous/Next bar replaces the normal
  // Cancel/Save footer and edit-toggle pencil entirely (Next itself saves),
  // so there's only ever one set of controls on screen at a time.
  $("#recordSheetFooter").hidden = !on || Boolean(reviewQueue);
  $("#recordEditToggleBtn").hidden = on || Boolean(reviewQueue);
  if (on) renderRecordEditForm(activeRecord);
}

function renderRecordEditForm(record) {
  const idMap = {
    name: "editName", designation: "editDesignation", company: "editCompany", business: "editBusiness",
    email1: "editEmail1", email2: "editEmail2", contact1: "editContact1", contact2: "editContact2", contact3: "editContact3",
    website: "editWebsite", social_media: "editSocialMedia", notes: "editNotes", address: "editAddress", category: "editCategory",
  };
  const container = $("#recordEditFields");
  container.innerHTML = `
    <input type="hidden" id="editCardId" value="${escapeHtml(record.card_id)}">
    ${Object.entries(idMap).map(([key, id]) => {
      const isTextarea = key === "notes" || key === "address";
      const inputMode = key.startsWith("contact") ? ' inputmode="tel"' : key.startsWith("email") ? ' type="email"' : "";
      const autocap = key === "name" ? ' autocapitalize="words"' : "";
      const label = id.replace("edit", "").replace(/([A-Z])/g, " $1").trim();
      const value = escapeHtml(record[key] || "");
      return `
        <div class="field-row">
          <label>${escapeHtml(label)}
            ${isTextarea ? `<textarea id="${id}">${value}</textarea>` : `<input id="${id}" value="${value}"${inputMode}${autocap}>`}
          </label>
        </div>
      `;
    }).join("")}
  `;
}

async function saveRecordEdit({ silent = false } = {}) {
  const { state, loadRecords, showToast } = await import("./app-shell.js");
  const cardId = $("#editCardId").value;
  const values = {
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
  };
  const previous = { ...activeRecord };
  Object.assign(activeRecord, values);
  renderRecordView(activeRecord);
  if (!silent) setEditMode(false);
  const index = state.records.findIndex((r) => r.card_id === cardId);
  if (index >= 0) state.records[index] = { ...state.records[index], ...values };
  renderRecords(state);
  try {
    if (!state.online) throw new Error("Requires connection");
    await api.patchRecord(state.eventId, cardId, values);
    if (!silent) showToast("Record saved.", "success");
    await loadRecords();
    return true;
  } catch (error) {
    Object.assign(activeRecord, previous);
    if (index >= 0) state.records[index] = previous;
    renderRecords(state);
    showToast(error.message || "Save failed.", "error");
    return false;
  }
}

function downloadVCard() {
  const record = activeRecord;
  if (!record) return;
  const lines = [
    "BEGIN:VCARD",
    "VERSION:3.0",
    `N:${record.name || ""};;;;`,
    `FN:${record.name || ""}`,
  ];
  if (record.company || record.business) lines.push(`ORG:${record.company || record.business}`);
  if (record.designation) lines.push(`TITLE:${record.designation}`);
  [record.contact1, record.contact2, record.contact3, record.phone_primary].filter(Boolean).forEach((tel) => {
    lines.push(`TEL:${tel}`);
  });
  [record.email1, record.email2, record.email].filter(Boolean).forEach((email) => {
    lines.push(`EMAIL:${email}`);
  });
  if (record.website) lines.push(`URL:${record.website}`);
  const address = [record.address, record.city, record.state, record.zip_code, record.country].filter(Boolean).join(";");
  if (address) lines.push(`ADR:;;${record.address || ""};${record.city || ""};${record.state || ""};${record.zip_code || ""};${record.country || ""}`);
  if (record.notes) lines.push(`NOTE:${record.notes.replace(/\n/g, "\\n")}`);
  lines.push("END:VCARD");
  const blob = new Blob([lines.join("\r\n")], { type: "text/vcard" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${(record.name || "contact").replace(/[^a-z0-9]+/gi, "_")}.vcf`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// ---- Image viewer ----

function wireImageDialog() {
  $("#closeImageBtn").addEventListener("click", () => $("#imageDialog").close());
  $("#imageDialog").addEventListener("click", (event) => {
    if (event.target.id === "imageDialog") $("#imageDialog").close();
  });
}

function openImage(imageUrl) {
  $("#fullCardImage").src = imageUrl;
  $("#imageDialog").showModal();
}
