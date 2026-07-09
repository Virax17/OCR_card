from __future__ import annotations

import re

from app.models import FieldCandidate, OCRSideResult

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
EMAIL_JOINER_RE = re.compile(r"\s*([@._+-])\s*")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
LABELED_PHONE_RE = re.compile(
    r"^\s*(?P<label>T|TEL|TELEPHONE|PHONE|OFFICE|LANDLINE|M|MOB|MOBILE|CELL|F|FAX)\s*[:\-]?\s*(?P<number>\+?\d[\d\s().-]{6,}\d)\s*$",
    re.I,
)
WEBSITE_RE = re.compile(r"\b(?:https?://)?(?:www\.)?[A-Z0-9-]+(?:\.[A-Z0-9-]+)*\.[A-Z]{2,}(?:/\S*)?\b", re.I)

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
    "officer",
    "marketing",
    "procurement",
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
# A standalone 4-8 digit run on/near an address-flavored line, not embedded in
# a longer digit run (which would make it part of a phone/fax number).
ZIP_RE = re.compile(r"(?<!\d)\d{4,8}(?!\d)")


def clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" \t|,:;")


def email_search_text(text: str) -> str:
    normalized_lines = []
    for line in text.splitlines():
        line = line.replace("＠", "@")
        line = re.sub(r"\s*[\[(]?\s*at\s*[\])]?\s*", "@", line, flags=re.I)
        line = re.sub(r"\s*[\[(]?\s*dot\s*[\])]?\s*", ".", line, flags=re.I)
        normalized_lines.append(EMAIL_JOINER_RE.sub(r"\1", line))
    return "\n".join(normalized_lines)


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
    all_lines: list[tuple[str, str, float, int, str | None]] = []
    for result in results:
        for block in result.blocks:
            line = clean_line(block.text)
            if line:
                all_lines.append((line, result.side, block.confidence, block.line_index, block.size_tag))

    joined = "\n".join(line for line, *_rest in all_lines)
    emails = sorted(set(EMAIL_RE.findall(joined) + EMAIL_RE.findall(email_search_text(joined))))
    email_domains = {email.split("@", 1)[1].lower() for email in emails if "@" in email}
    for email in emails:
        candidates.append(_candidate("email", email, 0.95, "rule", "email_regex"))

    labeled_numbers: set[str] = set()
    for line, side, confidence, _line_index, _size_tag in all_lines:
        if re.search(r"\b(iso|asme|certified|ohsas|sk3|lrga|wqa|ykan|htri)\b", line.lower()):
            continue
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
        line_start = joined.rfind("\n", 0, joined.find(phone)) + 1
        line_end = joined.find("\n", joined.find(phone))
        line = joined[line_start: line_end if line_end != -1 else len(joined)]
        if re.search(r"\b(iso|asme|certified|ohsas|sk3|lrga|wqa|ykan|htri)\b", line.lower()):
            continue
        if 8 <= len(digits) <= 15 and digits not in labeled_numbers:
            candidates.append(_candidate("phone", phone, 0.85, "rule", "phone_regex"))
    for website in sorted(set(WEBSITE_RE.findall(joined))):
        if "@" in website or website.lower().endswith((".jpg", ".png")):
            continue
        start = joined.find(website)
        if start > 0 and joined[start - 1] == "@":
            continue
        if start >= 0 and start + len(website) < len(joined) and joined[start + len(website)] == "@":
            continue
        lower_site = website.lower()
        normalized_site = re.sub(r"^https?://", "", lower_site).removeprefix("www.").strip("/")
        explicit_site = lower_site.startswith(("http://", "https://", "www."))
        if not explicit_site and normalized_site in email_domains:
            continue
        if any(char.isdigit() for char in website) and "." not in website:
            continue
        candidates.append(_candidate("website", website, 0.8, "rule", "website_regex"))

    for block_line, side, confidence, line_index, size_tag in all_lines:
        lower = block_line.lower()
        if any(keyword in lower for keyword in TITLE_KEYWORDS):
            candidates.append(_candidate("designation", block_line, max(confidence, 0.72), side, "title_keyword"))
        if any(keyword in lower for keyword in COMPANY_KEYWORDS):
            candidates.append(_candidate("company", block_line, max(confidence, 0.72), side, "company_keyword"))
        if side == "front" and line_index <= 4 and re.search(r"\b(pt|pvt|ltd|llc|inc|tbk|co\.?)\b", lower):
            candidates.append(_candidate("company", block_line, max(confidence, 0.82), side, "top_front_company"))
        if any(keyword in lower for keyword in ADDRESS_KEYWORDS):
            candidates.append(_candidate("address", block_line, max(confidence, 0.68), side, "address_keyword"))
            for zip_match in ZIP_RE.finditer(block_line):
                digits = zip_match.group(0)
                # Skip anything that reads as (part of) a phone number: those
                # lines carry a phone label or the OCR line also matches the
                # phone regex, which a genuine standalone postal code won't.
                if PHONE_RE.search(block_line) or re.search(r"\b(t|tel|telp|phone|m|mob|mobile|f|fax)\b", lower):
                    continue
                if 4 <= len(digits) <= 8:
                    candidates.append(_candidate("zip", digits, max(confidence, 0.7), side, "address_line_digits"))
        # Widened from the first 5 lines / 2-4 words: names are sometimes
        # lower on the card (below a logo/tagline) or a single/five-word name,
        # so scan more of the front and allow 1-5 words to actually produce a
        # hint for both Gemini and the deterministic fallback.
        if (
            side == "front"
            and line_index <= 8
            and 0 < len(block_line.split()) <= 5
            and not re.search(r"\b(pt|pvt|ltd|llc|inc|tbk|co\.?)\b", lower)
            and not EMAIL_RE.search(block_line)
            and not PHONE_RE.search(block_line)
            and not WEBSITE_RE.search(block_line)
            and not any(keyword in lower for keyword in TITLE_KEYWORDS | COMPANY_KEYWORDS | ADDRESS_KEYWORDS)
        ):
            # A line Vision reported as noticeably larger than the card's
            # median text is a strong signal for a personal name (or the
            # brand — the front-line/word-count/keyword gates above already
            # filter out most company lines), so boost its confidence.
            base_confidence = 0.72 if size_tag == "large" else 0.65
            candidates.append(_candidate("name", block_line, max(confidence, base_confidence), side, "top_front_line"))

    return candidates
