const CACHE_VERSION = "cardscan-v6";
const PRECACHE_URLS = [
  "/",
  "/manifest.webmanifest",
  "/static/css/tokens.css",
  "/static/css/components.css",
  "/static/css/screens.css",
  "/static/js/app-shell.js",
  "/static/js/api.js",
  "/static/js/utils.js",
  "/static/js/scan.js",
  "/static/js/queue.js",
  "/static/js/process-sheet.js",
  "/static/js/records.js",
  "/static/js/dashboard.js",
  "/static/js/events.js",
  "/static/js/more.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
  "/static/icons/icon-192-maskable.png",
  "/static/icons/icon-512-maskable.png",
  "/static/fonts/ibm-plex-sans-400.woff2",
  "/static/fonts/ibm-plex-sans-500.woff2",
  "/static/fonts/ibm-plex-sans-600.woff2",
  "/static/fonts/ibm-plex-mono-500.woff2",
];

const NETWORK_FIRST_PATTERNS = [/^\/events$/, /^\/events\/[^/]+\/cards$/, /^\/llm-usage$/, /^\/health$/];
const CACHE_FIRST_PATTERN = /^\/events\/[^/]+\/images\//;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(PRECACHE_URLS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.pathname === "/download" || url.pathname.endsWith("/download")) return;

  if (CACHE_FIRST_PATTERN.test(url.pathname)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  if (NETWORK_FIRST_PATTERNS.some((pattern) => pattern.test(url.pathname))) {
    event.respondWith(networkFirst(request));
    return;
  }

  if (PRECACHE_URLS.includes(url.pathname) || url.pathname.startsWith("/static/")) {
    event.respondWith(cacheFirst(request));
  }
});

async function cacheFirst(request) {
  const cache = await caches.open(CACHE_VERSION);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

async function networkFirst(request) {
  const cache = await caches.open(CACHE_VERSION);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}
