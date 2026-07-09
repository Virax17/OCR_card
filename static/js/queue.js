import * as api from "./api.js";

const DB_NAME = "cardscan";
const STORE_NAME = "captureQueue";
const MAX_ATTEMPTS = 5;
const BACKOFF_MS = [10000, 30000, 120000, 120000, 120000];

let db = null;
let processing = false;
let cachedSnapshot = [];

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: "id", autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function tx(mode) {
  return db.transaction(STORE_NAME, mode).objectStore(STORE_NAME);
}

function requestToPromise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function initQueue() {
  if (!("indexedDB" in window)) return;
  try {
    db = await openDb();
    await refreshSnapshot();
  } catch {
    db = null;
  }
  window.addEventListener("attemptQueueFlush", () => processQueue());
  window.addEventListener("online", () => processQueue());
  if (navigator.onLine) processQueue();
}

async function refreshSnapshot() {
  if (!db) return;
  const all = await requestToPromise(tx("readonly").getAll());
  cachedSnapshot = all.map((item) => ({
    id: item.id,
    eventId: item.eventId,
    capturedAt: item.capturedAt,
    status: item.status,
    attempts: item.attempts,
    hasBack: Boolean(item.backBlob),
    thumbUrl: item.frontBlob ? URL.createObjectURL(item.frontBlob) : "",
  }));
  emitChange();
}

function emitChange() {
  window.dispatchEvent(new CustomEvent("queueChanged", { detail: { items: cachedSnapshot } }));
}

export function getQueueSnapshot() {
  return cachedSnapshot;
}

export async function enqueueCapture(eventId, frontBlob, backBlob) {
  const record = {
    eventId,
    frontBlob,
    backBlob: backBlob || null,
    capturedAt: new Date().toISOString(),
    attempts: 0,
    status: "pending",
  };
  if (db) {
    await requestToPromise(tx("readwrite").add(record));
    await refreshSnapshot();
  }
  processQueue();
  return record;
}

export async function removeQueueItem(id) {
  if (!db) return;
  await requestToPromise(tx("readwrite").delete(id));
  await refreshSnapshot();
}

export async function retryQueueItem(id) {
  if (!db) return;
  const item = await requestToPromise(tx("readonly").get(id));
  if (!item) return;
  item.status = "pending";
  item.attempts = 0;
  await requestToPromise(tx("readwrite").put(item));
  await refreshSnapshot();
  processQueue();
}

export async function processQueue() {
  if (processing || !db || !navigator.onLine) return;
  processing = true;
  try {
    let item = await getNextPending();
    while (item) {
      await processOne(item);
      item = await getNextPending();
    }
  } finally {
    processing = false;
  }
}

async function getNextPending() {
  const all = await requestToPromise(tx("readonly").getAll());
  return all.find((entry) => entry.status !== "uploading" && entry.status !== "failed") || null;
}

async function processOne(item) {
  item.status = "uploading";
  await requestToPromise(tx("readwrite").put(item));
  await refreshSnapshot();
  try {
    await api.uploadCard(item.eventId, item.frontBlob, "front.jpg", item.backBlob, "back.jpg");
    await requestToPromise(tx("readwrite").delete(item.id));
    await refreshSnapshot();
    window.dispatchEvent(new CustomEvent("queueItemProcessed", { detail: { success: true } }));
  } catch (error) {
    item.attempts = (item.attempts || 0) + 1;
    if (item.attempts >= MAX_ATTEMPTS) {
      item.status = "failed";
      await requestToPromise(tx("readwrite").put(item));
      await refreshSnapshot();
    } else {
      item.status = "pending";
      await requestToPromise(tx("readwrite").put(item));
      await refreshSnapshot();
      const delay = BACKOFF_MS[Math.min(item.attempts - 1, BACKOFF_MS.length - 1)];
      await new Promise((resolve) => window.setTimeout(resolve, delay));
    }
    window.dispatchEvent(new CustomEvent("queueItemProcessed", { detail: { success: false, error: error.message } }));
  }
}
