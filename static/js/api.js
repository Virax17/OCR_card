export async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const error = new Error(data.detail || `Request failed: ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

export function getHealth() {
  return fetchJson("/health");
}

export function listEvents() {
  return fetchJson("/events");
}

export function createEvent(payload) {
  return fetchJson("/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function listRecords(eventId) {
  return fetchJson(`/events/${eventId}/cards`);
}

export function uploadCard(eventId, frontBlob, frontName, backBlob, backName) {
  const form = new FormData();
  form.append("front", frontBlob, frontName || "front.jpg");
  if (backBlob) form.append("back", backBlob, backName || "back.jpg");
  return fetchJson(`/events/${eventId}/cards`, { method: "POST", body: form });
}

export function patchRecord(eventId, cardId, values) {
  return fetchJson(`/events/${eventId}/cards/${cardId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(values),
  });
}

export function resetCards(eventId) {
  return fetchJson(`/events/${eventId}/cards`, { method: "DELETE" });
}

export function getUsage() {
  return fetchJson("/llm-usage");
}

export function downloadUrl(eventId) {
  return `/events/${eventId}/download`;
}

export function imageUrl(eventId, filename) {
  return `/events/${eventId}/images/${encodeURIComponent(filename)}`;
}
