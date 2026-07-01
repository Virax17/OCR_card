from __future__ import annotations

import re

from app.models import FieldCandidate, OCRSideResult

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
LABELED_PHONE_RE = re.compile(
    r"^\s*(?P<label>T|TEL|TELEPHONE|PHONE|OFFICE|LANDLINE|M|MOB|MOBILE|CELL|F|FAX)\s*[:\-]?\s*(?P<number>\+?\d[\d\s().-]{6,}\d)\s*$",
    re.I,
)
WEBSITE_RE = re.compile(r"\b(?:https?://)?(?:www\.)?[A-Z0-9-]+(?:\.[A-Z0-9-]+)+(?:/\S*)?\b", re.I)

TITLE_KEYWORDS = {
    "founder",
    "co-founder",
    "ceo",
    "cto",
    "cfo",
    "director",
    "manager",
    "sales",
    "engineer",
    "consultant",
    "partner",
    "head",
    "vp",
    "president",
    "executive",
}
COMPANY_KEYWORDS = {
    "pvt",
    "ltd",
    "llc",
    "inc",
    "llp",
    "industries",
    "solutions",
    "technologies",
    "systems",
    "services",
    "enterprise",
}
ADDRESS_KEYWORDS = {
    "road",
    "street",
    "st.",
    "floor",
    "near",
    "area",
    "industrial",
    "nagar",
    "city",
    "state",
    "india",
    "pin",
    "zip",
}


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" \t|,:;")


def _candidate(field: str, value: str, confidence: float, source: str, evidence: str | None = None) -> FieldCandidate:
    return FieldCandidate(field=field, value=clean_line(value), confidence=confidence, source=source, evidence=evidence)


def _phone_field_from_label(label: str) -> str:
    normalized = label.strip().lower()
    if normalized in {"m", "mob", "mobile", "cell"}:
        return "mobile"
    if normalized in {"f", "fax"}:
        return "fax"
    return "phone"


def extract_candidates(results: list[OCRSideResult]) -> list[FieldCandidate]:
    candidates: list[FieldCandidate] = []
    all_lines: list[tuple[str, str, float, int]] = []
    for result in results:
        for block in result.blocks:
            line = clean_line(block.text)
            if line:
                all_lines.append((line, result.side, block.confidence, block.line_index))

    joined = "\n".join(line for line, _, _, _ in all_lines)
    emails = sorted(set(EMAIL_RE.findall(joined)))
    email_domains = {email.split("@", 1)[1].lower() for email in emails if "@" in email}
    for email in emails:
        candidates.append(_candidate("email", email, 0.95, "rule", "email_regex"))

    labeled_numbers: set[str] = set()
    for line, side, confidence, _ in all_lines:
        match = LABELED_PHONE_RE.match(line)
        if not match:
            continue
        number = match.group("number")
        digits = re.sub(r"\D", "", number)
        if 7 <= len(digits) <= 15:
            labeled_numbers.add(re.sub(r"\D", "", number))
            candidates.append(
                _candidate(
                    _phone_field_from_label(match.group("label")),
                    number,
                    max(confidence, 0.9),
                    side,
                    f"{match.group('label').upper()}_label",
                )
            )

    for phone in sorted(set(PHONE_RE.findall(joined))):
        digits = re.sub(r"\D", "", phone)
        if 8 <= len(digits) <= 15 and digits not in labeled_numbers:
            candidates.append(_candidate("phone", phone, 0.85, "rule", "phone_regex"))
    for website in sorted(set(WEBSITE_RE.findall(joined))):
        if "@" in website or website.lower().endswith((".jpg", ".png")):
            continue
        lower_site = website.lower()
        normalized_site = re.sub(r"^https?://", "", lower_site).removeprefix("www.").strip("/")
        explicit_site = lower_site.startswith(("http://", "https://", "www."))
        if not explicit_site and normalized_site in email_domains:
            continue
        if any(char.isdigit() for char in website) and "." not in website:
            continue
        candidates.append(_candidate("website", website, 0.8, "rule", "website_regex"))

    for line, side, confidence, line_index in all_lines:
        lower = line.lower()
        if any(keyword in lower for keyword in TITLE_KEYWORDS):
            candidates.append(_candidate("designation", line, max(confidence, 0.72), side, "title_keyword"))
        if any(keyword in lower for keyword in COMPANY_KEYWORDS):
            candidates.append(_candidate("company", line, max(confidence, 0.72), side, "company_keyword"))
        if any(keyword in lower for keyword in ADDRESS_KEYWORDS):
            candidates.append(_candidate("address", line, max(confidence, 0.68), side, "address_keyword"))
        if (
            side == "front"
            and line_index <= 4
            and 1 < len(line.split()) <= 4
            and not EMAIL_RE.search(line)
            and not PHONE_RE.search(line)
            and not WEBSITE_RE.search(line)
            and not any(keyword in lower for keyword in TITLE_KEYWORDS | COMPANY_KEYWORDS | ADDRESS_KEYWORDS)
        ):
            candidates.append(_candidate("name", line, max(confidence, 0.65), side, "top_front_line"))

    return candidates
