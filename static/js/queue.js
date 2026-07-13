import * as api from "./api.js";

const DB_NAME = "cardscan";
const STORE_NAME = "captureQueue";
const MAX_ATTEMPTS = 5;
const BACKOFF_MS = [10000, 30000, 120000, 120000, 120000];
const SAFETY_FLUSH_MS = 25000;

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

// Mobile browsers silently close IndexedDB connections when a PWA is
// backgrounded (e.g. while the camera opens). Without reopening, every later
// transaction throws InvalidStateError and the queue stalls until a full page
// reload. ensureDb transparently (re)opens the connection on demand.
async function ensureDb() {
  if (db) return db;
  if (!("indexedDB" in window)) return null;
  try {
    db = await openDb();
    db.onclose = () => {
      db = null;
    };
    db.onversionchange = () => {
      try {
        db.close();
      } catch {
        // ignore
      }
      db = null;
    };
    return db;
  } catch {
    db = null;
    return null;
  }
}

// Run a transaction against a guaranteed-open connection, reopening once if the
// connection was closed out from under us.
async function withStore(mode, fn) {
  let database = await ensureDb();
  if (!database) throw new Error("IndexedDB unavailable");
  try {
    const store = database.transaction(STORE_NAME, mode).objectStore(STORE_NAME);
    return await fn(store);
  } catch (error) {
    db = null;
    database = await ensureDb();
    if (!database) throw error;
    const store = database.transaction(STORE_NAME, mode).objectStore(STORE_NAME);
    return await fn(store);
  }
}

function requestToPromise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function initQueue() {
  if (!("indexedDB" in window)) return;
  await ensureDb();
  await refreshSnapshot();
  window.addEventListener("attemptQueueFlush", () => processQueue());
  window.addEventListener("online", () => processQueue());
  // Resume when the tab returns to the foreground (the camera/backgrounding is
  // exactly when the IndexedDB connection tends to get dropped).
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") processQueue();
  });
  // Safety net: the browser 'online' event is unreliable on mobile/venue WiFi.
  window.setInterval(() => {
    if (navigator.onLine) processQueue();
  }, SAFETY_FLUSH_MS);
  if (navigator.onLine) processQueue();
}

async function refreshSnapshot() {
  try {
    const all = await withStore("readonly", (store) => requestToPromise(store.getAll()));
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
  } catch {
    // Leave the last known snapshot in place if the DB is momentarily gone.
  }
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
  try {
    const id = await withStore("readwrite", (store) => requestToPromise(store.add(record)));
    record.id = id;
    await refreshSnapshot();
  } catch {
    const { showToast } = await import("./app-shell.js");
    showToast("Couldn't save the capture locally. Please try again.", "error");
    return record;
  }
  processQueue();
  return record;
}

export async function removeQueueItem(id) {
  try {
    await withStore("readwrite", (store) => requestToPromise(store.delete(id)));
    await refreshSnapshot();
  } catch {
    // ignore — the item stays queued and will retry
  }
}

export async function retryQueueItem(id) {
  try {
    const item = await withStore("readonly", (store) => requestToPromise(store.get(id)));
    if (!item) return;
    item.status = "pending";
    item.attempts = 0;
    await withStore("readwrite", (store) => requestToPromise(store.put(item)));
    await refreshSnapshot();
    processQueue();
  } catch {
    // ignore — a later flush will pick it up
  }
}

export async function processQueue() {
  if (processing || !navigator.onLine) return;
  const database = await ensureDb();
  if (!database) return;
  processing = true;
  try {
    let item = await getNextPending();
    while (item) {
      await processOne(item);
      item = await getNextPending();
    }
  } catch {
    // Connection dropped mid-drain; a later trigger (visibility/interval/online)
    // will resume from where we left off.
  } finally {
    processing = false;
  }
}

async function getNextPending() {
  const all = await withStore("readonly", (store) => requestToPromise(store.getAll()));
  return all.find((entry) => entry.status !== "uploading" && entry.status !== "failed") || null;
}

async function processOne(item) {
  item.status = "uploading";
  await withStore("readwrite", (store) => requestToPromise(store.put(item)));
  await refreshSnapshot();
  try {
    await api.uploadCard(item.eventId, item.frontBlob, "front.jpg", item.backBlob, "back.jpg");
    await withStore("readwrite", (store) => requestToPromise(store.delete(item.id)));
    await refreshSnapshot();
    window.dispatchEvent(new CustomEvent("queueItemProcessed", { detail: { id: item.id, success: true } }));
  } catch (error) {
    item.attempts = (item.attempts || 0) + 1;
    // A 429 means a usage credit limit was hit — retrying won't help until it
    // resets, so mark it failed immediately instead of burning 5 backoff cycles.
    if (error.status === 429 || item.attempts >= MAX_ATTEMPTS) {
      item.status = "failed";
      await withStore("readwrite", (store) => requestToPromise(store.put(item)));
      await refreshSnapshot();
    } else {
      item.status = "pending";
      await withStore("readwrite", (store) => requestToPromise(store.put(item)));
      await refreshSnapshot();
      const delay = BACKOFF_MS[Math.min(item.attempts - 1, BACKOFF_MS.length - 1)];
      await new Promise((resolve) => window.setTimeout(resolve, delay));
    }
    window.dispatchEvent(new CustomEvent("queueItemProcessed", { detail: { id: item.id, success: false, error: error.message } }));
  }
}
