import { enqueueCapture } from "./queue.js";

const $ = (selector) => document.querySelector(selector);

let stream = null;
let currentSide = "front";
let frontBlob = null;
let backBlob = null;
let batchMode = false;
let batchItems = []; // { blob, url }
let stats = { processing: 0, done: 0, failed: 0 };
let returnRoute = "#/home";

export function wireScanScreen() {
  $("#scanCloseBtn").addEventListener("click", closeScanScreen);
  $("#scanGalleryBtn").addEventListener("click", () => $("#scanGalleryInput").click());
  $("#scanFallbackGalleryBtn").addEventListener("click", () => $("#scanGalleryInput").click());
  $("#scanGalleryInput").addEventListener("change", handleGalleryChange);
  $("#shutterBtn").addEventListener("click", handleShutter);
  $("#batchToggle").addEventListener("click", toggleBatchMode);
  $("#batchDoneBtn").addEventListener("click", finishBatch);
  $("#reviewRetakeBtn").addEventListener("click", retakePhoto);
  $("#reviewAddBackBtn").addEventListener("click", addBackSide);
  $("#reviewUsePhotoBtn").addEventListener("click", usePhoto);
  $("#scanStatusStrip").addEventListener("click", () => {
    import("./more.js").then(({ openQueueSheetFromScan }) => openQueueSheetFromScan?.());
  });
  document.querySelectorAll("#sideToggle button").forEach((btn) => {
    btn.addEventListener("click", () => setSide(btn.dataset.side));
  });
  window.addEventListener("queueItemProcessed", handleQueueEvent);
  window.addEventListener("queueChanged", updateStatusStrip);
}

export async function openScanScreen() {
  const { state } = await import("./app-shell.js");
  if (!state.eventId) {
    const { showToast } = await import("./app-shell.js");
    showToast("Create or select an event first.", "error");
    return;
  }
  returnRoute = window.location.hash || "#/home";
  document.body.classList.add("scan-open");
  $("#scanScreen").classList.add("is-active");
  frontBlob = null;
  backBlob = null;
  setSide("front");
  hideReview();
  await startCamera();
  updateStatusStrip();
}

function closeScanScreen() {
  stopCamera();
  document.body.classList.remove("scan-open");
  $("#scanScreen").classList.remove("is-active");
  resetBatch();
  frontBlob = null;
  backBlob = null;
  hideReview();
  window.location.hash = returnRoute;
}

async function startCamera() {
  $("#scanFallback").classList.remove("is-active");
  $("#scanVideo").style.display = "block";
  if (!navigator.mediaDevices?.getUserMedia) {
    showFallback();
    return;
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    $("#scanVideo").srcObject = stream;
  } catch {
    showFallback();
  }
}

function showFallback() {
  $("#scanFallback").classList.add("is-active");
  $("#scanVideo").style.display = "none";
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach((track) => track.stop());
    stream = null;
  }
}

function setSide(side) {
  currentSide = side;
  document.querySelectorAll("#sideToggle button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.side === side);
  });
}

function toggleBatchMode() {
  batchMode = !batchMode;
  $("#batchToggle").classList.toggle("active", batchMode);
  $("#scanGalleryBtn").classList.toggle("is-hidden", batchMode);
  $("#batchDoneBtn").classList.toggle("visible", batchMode);
  $("#batchTray").classList.toggle("visible", batchMode && batchItems.length > 0);
  if (!batchMode) resetBatch();
}

function resetBatch() {
  batchItems.forEach((item) => URL.revokeObjectURL(item.url));
  batchItems = [];
  renderBatchTray();
}

async function handleShutter() {
  const blob = await captureFrame();
  if (!blob) return;
  if (batchMode) {
    const url = URL.createObjectURL(blob);
    batchItems.push({ blob, url });
    renderBatchTray();
    return;
  }
  if (currentSide === "front") {
    frontBlob = blob;
  } else {
    backBlob = blob;
  }
  showReviewFrame(blob);
}

function captureFrame() {
  return new Promise((resolve) => {
    const video = $("#scanVideo");
    if (!video.videoWidth) return resolve(null);
    const canvas = $("#scanCanvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.9);
  });
}

function renderBatchTray() {
  const tray = $("#batchTray");
  tray.innerHTML = batchItems.map((item, index) => `
    <div class="batch-thumb" data-index="${index}">
      <img src="${item.url}" alt="">
      <button type="button" aria-label="Remove">✕</button>
    </div>
  `).join("");
  tray.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      const index = Number(event.currentTarget.parentElement.dataset.index);
      URL.revokeObjectURL(batchItems[index].url);
      batchItems.splice(index, 1);
      renderBatchTray();
    });
  });
  $("#batchCount").textContent = String(batchItems.length);
  $("#batchCount").classList.toggle("visible", batchItems.length > 0);
  $("#batchDoneBtn").textContent = `Done (${batchItems.length})`;
  $("#batchTray").classList.toggle("visible", batchMode && batchItems.length > 0);
}

async function finishBatch() {
  if (!batchItems.length) {
    toggleBatchMode();
    return;
  }
  // Hand the captured blobs to the preview/confirm sheet, then clear the tray.
  const blobs = batchItems.map((item) => item.blob);
  resetBatch();
  toggleBatchMode();
  const { openProcessSheet } = await import("./process-sheet.js");
  openProcessSheet(blobs.map((blob) => ({ blob })));
}

function showReviewFrame(blob) {
  const url = URL.createObjectURL(blob);
  $("#scanFrozenFrame").src = url;
  $("#scanFrozenFrame").style.display = "block";
  $("#scanReviewSheet").classList.add("visible");
  $("#reviewAddBackBtn").hidden = currentSide === "back";
}

function hideReview() {
  $("#scanReviewSheet").classList.remove("visible");
  $("#scanFrozenFrame").style.display = "none";
}

function retakePhoto() {
  if (currentSide === "front") frontBlob = null; else backBlob = null;
  hideReview();
}

function addBackSide() {
  hideReview();
  setSide("back");
}

async function usePhoto() {
  const { state, showToast } = await import("./app-shell.js");
  hideReview();
  if (currentSide === "back") {
    setSide("front");
  }
  const front = frontBlob;
  const back = backBlob;
  frontBlob = null;
  backBlob = null;
  setSide("front");
  if (!front) return;
  stats.processing += 1;
  updateStatusStrip();
  showToast("Processing…", "info");
  await enqueueAndTrack(state.eventId, front, back);
}

async function enqueueAndTrack(eventId, front, back) {
  await enqueueCapture(eventId, front, back);
}

function handleQueueEvent(event) {
  // Only the single-capture path feeds this aggregate strip now; gallery/batch
  // uploads report their own per-photo status in the process sheet. Update the
  // counters only while we're actually tracking a single capture, but always
  // refresh records so newly processed cards appear regardless of the source.
  if (stats.processing > 0) {
    stats.processing -= 1;
    if (event.detail?.success) stats.done += 1; else stats.failed += 1;
    updateStatusStrip();
  }
  import("./app-shell.js").then(({ refreshAll }) => refreshAll());
}

function updateStatusStrip() {
  const strip = $("#scanStatusStrip");
  const parts = [];
  if (stats.processing) parts.push(`⏳ ${stats.processing} processing`);
  if (stats.done) parts.push(`✓ ${stats.done} done`);
  if (stats.failed) parts.push(`⚠ ${stats.failed} failed`);
  if (!parts.length) {
    strip.classList.remove("visible");
    return;
  }
  strip.textContent = parts.join(" · ");
  strip.classList.add("visible");
}

async function handleGalleryChange() {
  const files = Array.from($("#scanGalleryInput").files || []);
  $("#scanGalleryInput").value = "";
  await importGalleryFiles(files);
}

export async function importGalleryFiles(files) {
  const imageFiles = files.filter((file) => file.type.startsWith("image/"));
  if (!imageFiles.length) return;
  const { state, showToast } = await import("./app-shell.js");
  if (!state.eventId) return showToast("Create or select an event first.", "error");
  const { openProcessSheet } = await import("./process-sheet.js");
  openProcessSheet(imageFiles.map((file) => ({ blob: file, name: file.name })));
}
