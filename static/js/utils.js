export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

export function formatPhoneForDisplay(value, countryCode) {
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

export function debounce(fn, wait) {
  let timer;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), wait);
  };
}

export function confidenceLevel(record) {
  const label = String(record.confidence_score || "").toLowerCase();
  if (label === "high") return "high";
  if (label === "medium") return "medium";
  return "low";
}

export function isDuplicate(record) {
  return String(record.duplicate_flag || "No").toLowerCase() !== "no";
}

// Single definition of "needs your attention" shared by Home's callout card,
// the Records filter, and the review-queue mode — a record qualifies for any
// of those surfaces if and only if this returns true.
export function needsReview(record) {
  return isDuplicate(record) || confidenceLevel(record) === "low";
}

const AVATAR_TINTS = [
  { bg: "#e7f7f5", fg: "#0b5c55" }, // teal
  { bg: "#fdecd9", fg: "#b1560c" }, // amber
  { bg: "#ece9fb", fg: "#5b47c9" }, // purple
];

export function avatarTint(name) {
  const str = String(name || "?");
  let hash = 0;
  for (let i = 0; i < str.length; i += 1) hash = (hash * 31 + str.charCodeAt(i)) >>> 0;
  return AVATAR_TINTS[hash % AVATAR_TINTS.length];
}

export function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  return parts.slice(0, 2).map((part) => part[0].toUpperCase()).join("");
}
