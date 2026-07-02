from __future__ import annotations

import json
import re
import hashlib

from app.config import BUSINESS_CATEGORIES, GEMINI_API_KEY, GEMINI_API_KEYS, GEMINI_MODEL
from app.extraction.field_resolver import (
    country_name_from_code,
    infer_country_and_code,
    national_phone_number,
    normalize_country_name,
    normalize_email,
    normalize_phone,
    normalize_website,
)
from app.llm.usage_monitor import estimate_tokens, record_usage, usage_snapshot

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover
    genai = None
    types = None


FIELDS = [
    "front_text",
    "back_text",
    "all_visible_text",
    "name",
    "designation",
    "business",
    "address",
    "city",
    "state",
    "country",
    "zip_code",
    "website",
    "category",
    "social_media",
    "notes",
    "email1",
    "email2",
    "contact1",
    "contact2",
    "contact3",
    "company",
    "phone_primary",
    "phone_number",
    "mobile_number",
    "phone_extra",
    "fax_number",
    "country_code",
    "email",
    "field_evidence",
    "uncertain_fields",
]

BUSINESS_CARD_VISUAL_RULES = """
Business-card layout rules learned from local samples:
- First transcribe all readable printed text from each card side before choosing fields. Field values must come from that transcript.
- Treat the front side as the primary source for name, designation, company/business, email, website, and phone fields.
- The company/business name is usually the top-most stylized brand/logo text on the front side. It may be on the top-left or top-right, not necessarily in plain body text.
- Do not use branch names, office labels, building names, service-list headings, back-side product lists, slogans, or address landmarks as the company name.
- Back sides often contain branch addresses, support facilities, product photos, service outlines, target/safety slogans, and "we sell" lists. Use these for address/category support only unless a missing contact field is clearly printed there.
- Ignore QR codes, decorative icons, certification icons, product photos, separators, and handwritten notes unless the printed text beside them is part of a contact field.
- Person name is commonly the largest personal text block, often near the center/right, with designation directly below it.
- Designation is a role title such as Director, Procurement Manager, Plant Manager, Sales Engineer, Regional Sales Manager, or Quick Contact Specialist. Do not put company/service text into designation.
- Business is the company/legal entity/brand, such as PETROSEA, Babcock & Wilcox, TOKKI, PT Kezindo Sejahtera Abadi, PT. AIR SURYA RADIATOR, PT. Mechatechra Triasindo Indonesia, CESCO, or TIMAS SUPLINDO.
- Email may be preceded by E, Email, Mail, or an envelope icon. It must contain @ and a valid domain.
- Website may be preceded by W, Web, Website, a globe icon, or printed in the footer. It is a web/domain value, not the email address.
- Phone labels can be short: T/Telp/Tel/Phone for office, M/Mob/Mobile/HP/Cell for mobile, F/Fax for fax.
- Match the reference Excel format: Email1 is primary email, Email2 is secondary email, Contact1 is the main direct/mobile number, Contact2 is office/telephone, Contact3 is fax or another printed number.
- Contact1, Contact2, and Contact3 must be digits only with country calling code included when visible or inferable, for example 60133581918 or 912241266030. Do not include +, spaces, hyphens, or parentheses.
- For country_code, trust explicit phone prefixes like +62, +91, +971 before address guesses. Indonesia/Jakarta/Kalimantan/Papua/Sorong with +62 means country_code +62.
- If the card has multiple offices on the back, do not replace the front contact phone/mobile/email with back-side branch office numbers.
""".strip()


def _key_label(api_key: str | None, index: int | None = None) -> str | None:
    if not api_key:
        return None
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:8]
    prefix = f"key{index + 1}" if index is not None else "key"
    return f"{prefix}_{digest}"


def gemini_key_labels() -> list[str]:
    return [_key_label(key, index) or f"key{index + 1}" for index, key in enumerate(GEMINI_API_KEYS)]


def is_gemini_configured() -> bool:
    return bool(GEMINI_API_KEYS or GEMINI_API_KEY) and genai is not None


def _gemini_keys() -> list[tuple[str, str]]:
    keys = GEMINI_API_KEYS or ([GEMINI_API_KEY] if GEMINI_API_KEY else [])
    return [(key, _key_label(key, index) or f"key{index + 1}") for index, key in enumerate(keys)]


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)
WEBSITE_RE = re.compile(r"(?:https?://)?(?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)*\.[a-z]{2,}(?:/[^\s,;]*)?", re.I)
PHONE_RE = re.compile(r"(?:\+|00)?\d[\d\s()./-]{5,}\d")
EMAIL_JOINER_RE = re.compile(r"\s*([@._+-])\s*")


def _clean_email(value: str | None) -> str | None:
    if not value:
        return None
    compact = EMAIL_JOINER_RE.sub(r"\1", value.replace("＠", "@"))
    match = EMAIL_RE.search(compact.replace(" ", ""))
    return normalize_email(match.group(0)) if match else normalize_email(value)


def _clean_contact(value: str | None, country_code: str | None = None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None
    if digits.startswith("00"):
        digits = digits[2:]
    if country_code:
        code_digits = re.sub(r"\D", "", country_code)
        if code_digits and digits.startswith(code_digits):
            return digits
        if digits.startswith("00"):
            digits = digits[2:]
            if code_digits and digits.startswith(code_digits):
                return digits
        if code_digits:
            digits = f"{code_digits}{digits.lstrip('0')}"
    return digits or None


def _clean_website(value: str | None, email: str | None = None) -> str | None:
    if not value:
        return None
    compact = value.strip().replace(" ", "")
    match = WEBSITE_RE.search(compact)
    if not match:
        return None
    website = match.group(0).rstrip(".")
    if email and website.lower() in email.lower():
        return None
    return normalize_website(website)


DESIGNATION_RE = re.compile(
    r"\b(procurement|marketing|sales|director|manager|engineer|officer|executive|specialist|consultant|head|president)\b",
    re.I,
)
ADDRESS_RE = re.compile(
    r"\b(jl\.?|jalan|street|road|kav\.?|kel\.?|kec\.?|kota|bekasi|banten|cilegon|jakarta|ruko|wisma|building|floor|office|rt\.?|rw\.?|no\.?)\b",
    re.I,
)
NOISE_RE = re.compile(
    r"\b(asme|certified|iso|lrga|wqa|ykan|htri|ohsas|sk3|location|website|e-mail|email|mobile|telp|tel|fax)\b",
    re.I,
)
SERVICE_RE = re.compile(
    r"\b(design|fabrication|heavy duty|radiator|oil cooler|heat exchanger|shell|tube|pressure vessel|special order|engineering and fabrication)\b",
    re.I,
)
FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "icloud.com",
}


def _text_lines(text: str) -> list[str]:
    return [line.strip(" \t|,:;") for line in text.splitlines() if line.strip(" \t|,:;")]


def _has_contact_value(line: str) -> bool:
    return bool(EMAIL_RE.search(line) or PHONE_RE.search(line) or WEBSITE_RE.search(line))


def _looks_like_person_name(line: str) -> bool:
    if _has_contact_value(line) or NOISE_RE.search(line) or ADDRESS_RE.search(line) or SERVICE_RE.search(line):
        return False
    words = [word for word in re.findall(r"[A-Za-z][A-Za-z.'-]*", line) if len(word) > 1]
    if not 2 <= len(words) <= 4:
        return False
    banned = {"office", "factory", "engineering", "fabrication", "radiator", "location", "website"}
    return not any(word.lower() in banned for word in words)


def _looks_like_business(line: str) -> bool:
    if _has_contact_value(line) or NOISE_RE.search(line) or ADDRESS_RE.search(line):
        return False
    words = re.findall(r"[A-Za-z0-9&.'-]+", line)
    if not words:
        return False
    if re.search(r"\b(pt|pvt|ltd|llc|inc|tbk|co\.?)\b", line, re.I):
        return True
    if DESIGNATION_RE.search(line):
        return False
    if SERVICE_RE.search(line):
        return False
    if line.isupper() and len(" ".join(words)) >= 3:
        return True
    return len(words) <= 4 and any(len(word) >= 4 for word in words)


def _infer_designation(lines: list[str]) -> tuple[str | None, int | None]:
    for index, line in enumerate(lines):
        if DESIGNATION_RE.search(line) and not SERVICE_RE.search(line) and not _has_contact_value(line):
            return line, index
    return None, None


def _infer_name(lines: list[str], designation_index: int | None) -> str | None:
    if designation_index is not None:
        for index in range(designation_index - 1, max(-1, designation_index - 4), -1):
            if index >= 0 and _looks_like_person_name(lines[index]):
                return lines[index]
    for line in lines[:12]:
        if _looks_like_person_name(line):
            return line
    return None


def _infer_business(lines: list[str], name: str | None = None) -> str | None:
    for line in lines[:8]:
        if line == name:
            continue
        if _looks_like_business(line):
            return line
    return None


def _infer_address(lines: list[str]) -> str | None:
    address_lines = []
    for line in lines:
        lowered = line.lower()
        if _has_contact_value(line):
            continue
        if ADDRESS_RE.search(line) or "indonesia" in lowered or re.search(r"\b\d{5}\b", line):
            address_lines.append(line)
    return "\n".join(dict.fromkeys(address_lines)) or None


def _infer_zip(text: str) -> str | None:
    matches = re.findall(r"\b\d{5,6}\b", text)
    return matches[-1] if matches else None


def _infer_city_state(text: str) -> tuple[str | None, str | None]:
    lowered = text.lower()
    rules = [
        ("Jakarta Timur", "Jakarta", ["jakarta timur"]),
        ("Jakarta Barat", "Jakarta", ["jakarta barat"]),
        ("Jakarta", "Jakarta", ["jakarta"]),
        ("Bekasi", "West Java", ["bekasi"]),
        ("Cilegon", "Banten", ["cilegon"]),
        ("Gresik", "East Java", ["gresik"]),
        ("Cikarang", "West Java", ["cikarang"]),
    ]
    for city, state, hints in rules:
        if any(hint in lowered for hint in hints):
            return city, state
    return None, None


def _domain_for_score(website: str) -> str:
    domain = website.lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = domain.removeprefix("www.")
    return domain.split("/", 1)[0]


def _brand_tokens(*values: str | None) -> set[str]:
    ignored = {
        "pt",
        "pvt",
        "ltd",
        "llc",
        "inc",
        "tbk",
        "co",
        "company",
        "the",
        "and",
        "services",
        "service",
        "engineering",
        "industries",
        "industrial",
        "limited",
        "private",
        "head",
        "office",
    }
    tokens = set()
    for value in values:
        for token in re.findall(r"[a-z0-9]+", (value or "").lower()):
            if len(token) >= 3 and token not in ignored:
                tokens.add(token)
    return tokens


def _website_score(website: str, brand_tokens: set[str], line: str, email_domains: set[str]) -> tuple[int, int]:
    domain = _domain_for_score(website)
    root = domain.split(".")[0]
    line_lower = line.lower()
    score = 0
    if re.search(r"\b(w|web|website|www)\b", line_lower):
        score += 10
    if brand_tokens:
        for token in brand_tokens:
            if token in domain or domain in token:
                score += 8
            elif token[:5] in root or root[:5] in token:
                score += 4
    if domain in email_domains:
        score += 2
    if website.lower().startswith(("http://", "https://")) or domain.startswith("www."):
        score += 1
    return score, -len(domain)


def _country_code_from_phone(*values: str | None) -> str | None:
    known_codes = {
        "+1",
        "+44",
        "+60",
        "+62",
        "+65",
        "+91",
        "+965",
        "+966",
        "+968",
        "+971",
        "+973",
        "+974",
    }
    for value in values:
        if not value:
            continue
        explicit = re.match(r"\s*(?:\+\s*(\d{1,3})|00\s*(\d{1,3}))(?=[\s()./-]|$)", value)
        if explicit:
            return f"+{explicit.group(1) or explicit.group(2)}"
        digits = re.sub(r"[^\d+]", "", value)
        if digits.startswith("00"):
            digits = f"+{digits[2:]}"
        for code in sorted(known_codes, key=len, reverse=True):
            code_digits = code.replace("+", "")
            if digits.startswith(code) or re.sub(r"\D", "", digits).startswith(code_digits):
                return code
    return None


def _visible_text(fields: dict) -> str:
    parts = [
        str(fields.get("front_text") or ""),
        str(fields.get("back_text") or ""),
        str(fields.get("all_visible_text") or ""),
    ]
    return "\n".join(part for part in parts if part.strip())


def _normalize_match_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _value_supported_by_text(value: str | None, text: str) -> bool:
    if not value:
        return False
    normalized_value = _normalize_match_text(value)
    normalized_text = _normalize_match_text(text)
    if not normalized_value:
        return False
    if normalized_value in normalized_text:
        return True
    tokens = [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 1]
    if not tokens:
        return False
    return all(token in normalized_text for token in tokens)


def _unique(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _email_search_variants(text: str) -> list[str]:
    variants = [text]
    normalized_lines = []
    for line in text.splitlines():
        line = line.replace("＠", "@")
        line = re.sub(r"\s*[\[(]?\s*at\s*[\])]?\s*", "@", line, flags=re.I)
        line = re.sub(r"\s*[\[(]?\s*dot\s*[\])]?\s*", ".", line, flags=re.I)
        normalized_lines.append(EMAIL_JOINER_RE.sub(r"\1", line))
    variants.append("\n".join(normalized_lines))
    variants.append(EMAIL_JOINER_RE.sub(r"\1", text.replace("＠", "@")))
    return variants


def _emails_from_text(text: str) -> list[str]:
    emails = []
    for variant in _email_search_variants(text):
        emails.extend(normalize_email(match.group(0)) for match in EMAIL_RE.finditer(variant))
    return _unique(emails)


def _websites_from_text(text: str, emails: list[str], *brand_values: str | None) -> list[str]:
    email_domains = {email.split("@", 1)[1].lower() for email in emails if "@" in email}
    brand_tokens = _brand_tokens(*brand_values)
    scored: list[tuple[tuple[int, int], str]] = []
    for match in WEBSITE_RE.finditer(text):
        raw = match.group(0).strip().rstrip(".,;")
        if not raw or "@" in raw:
            continue
        if match.start() > 0 and text[match.start() - 1] == "@":
            continue
        if match.end() < len(text) and text[match.end()] == "@":
            continue
        normalized = normalize_website(raw)
        domain = normalized.replace("https://", "").replace("http://", "").split("/", 1)[0].lower()
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        line = text[line_start: line_end if line_end != -1 else len(text)].lower()
        if domain in email_domains and not re.search(r"\b(w|web|website|www)\b", line):
            continue
        scored.append((_website_score(normalized, brand_tokens, line, email_domains), normalized))
    if not scored and email_domains and brand_tokens:
        for domain in email_domains:
            fallback = normalize_website(domain)
            score, _ = _website_score(fallback, brand_tokens, "", email_domains)
            if score >= 8:
                scored.append(((score - 1, -len(domain)), fallback))
    if not scored and email_domains:
        for domain in sorted(email_domains):
            if domain not in FREE_EMAIL_DOMAINS:
                scored.append(((1, -len(domain)), normalize_website(domain)))
    return _unique([website for _, website in sorted(scored, key=lambda item: item[0], reverse=True)])


def structure_card_text_deterministic(
    front_text: str,
    back_text: str | None = None,
    candidate_hints: list[dict] | None = None,
) -> dict:
    fields = {field: None for field in FIELDS}
    fields["front_text"] = front_text
    fields["back_text"] = back_text
    fields["all_visible_text"] = "\n".join(part for part in [front_text, back_text or ""] if part.strip()).strip()
    lines = _text_lines(fields["all_visible_text"])

    candidate_hints = candidate_hints or []
    by_field: dict[str, list[dict]] = {}
    for candidate in candidate_hints:
        by_field.setdefault(str(candidate.get("field") or ""), []).append(candidate)
    for values in by_field.values():
        values.sort(key=lambda item: float(item.get("confidence") or 0), reverse=True)

    field_map = {
        "name": "name",
        "designation": "designation",
        "company": "business",
        "address": "address",
        "website": "website",
        "mobile": "contact1",
        "phone": "contact2",
        "fax": "contact3",
    }
    for source, target in field_map.items():
        if by_field.get(source):
            fields[target] = by_field[source][0].get("value")
    if fields.get("designation") and SERVICE_RE.search(str(fields["designation"])):
        fields["designation"] = None

    inferred_designation, designation_index = _infer_designation(lines)
    if not fields.get("designation"):
        fields["designation"] = inferred_designation
    if not fields.get("name"):
        fields["name"] = _infer_name(lines, designation_index)
    if not fields.get("business"):
        fields["business"] = _infer_business(lines, fields.get("name"))
    if not fields.get("address"):
        fields["address"] = _infer_address(lines)
    if not fields.get("zip_code"):
        fields["zip_code"] = _infer_zip(fields["all_visible_text"])
    city, state = _infer_city_state(fields["all_visible_text"])
    fields["city"] = fields.get("city") or city
    fields["state"] = fields.get("state") or state

    emails = [candidate.get("value") for candidate in by_field.get("email", []) if candidate.get("value")]
    if emails:
        fields["email1"] = emails[0]
    if len(emails) > 1:
        fields["email2"] = emails[1]

    fields["company"] = fields.get("business")
    fields["field_evidence"] = {
        target: by_field[source][0].get("evidence") or by_field[source][0].get("value")
        for source, target in field_map.items()
        if by_field.get(source)
    }
    fields["uncertain_fields"] = ["llm_sorting_skipped_or_failed"]
    return clean_structured_fields(fields)


def _label_for_phone_line(line: str) -> str | None:
    lowered = line.lower()
    if re.search(r"\b(f|fax)\b", lowered):
        return "contact3"
    if re.search(r"\b(m|mob|mobile|hp|cell|direct)\b", lowered):
        return "contact1"
    if re.search(r"\b(t|tel|telp|phone|office|landline)\b", lowered):
        return "contact2"
    return None


def _contacts_from_text(text: str, country_code: str | None) -> dict[str, str | None]:
    contacts: dict[str, str | None] = {"contact1": None, "contact2": None, "contact3": None}
    unlabeled: list[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if "@" in line or re.search(r"\b(iso|asme|certified|ohsas|sk3|lrga|wqa|ykan|htri)\b", lowered):
            continue
        line_numbers = []
        for match in PHONE_RE.finditer(line):
            raw = match.group(0)
            raw_digits = re.sub(r"\D", "", raw)
            if len(raw_digits) < 8 or len(raw_digits) > 15:
                continue
            cleaned = _clean_contact(raw, country_code)
            if not cleaned or len(cleaned) < 7:
                continue
            line_numbers.append(cleaned)

        if not line_numbers:
            continue
        if re.search(r"\b(f|fax)\b", lowered) and re.search(r"\b(t|tel|telp|phone|office|landline)\b", lowered) and len(line_numbers) >= 2:
            if not contacts["contact2"]:
                contacts["contact2"] = line_numbers[0]
            if not contacts["contact3"]:
                contacts["contact3"] = line_numbers[-1]
            continue

        for cleaned in line_numbers:
            label = _label_for_phone_line(line)
            if label and not contacts[label]:
                contacts[label] = cleaned
            elif not label:
                unlabeled.append(cleaned)

    for key in ("contact1", "contact2", "contact3"):
        if not contacts[key] and unlabeled:
            contacts[key] = unlabeled.pop(0)
    return contacts


def _drop_unsupported_fields(cleaned: dict, text: str) -> None:
    for field in [
        "name",
        "designation",
        "business",
        "company",
        "address",
        "city",
        "state",
        "zip_code",
        "social_media",
        "notes",
    ]:
        value = cleaned.get(field)
        if value and not _value_supported_by_text(str(value), text):
            cleaned[field] = None


def clean_structured_fields(fields: dict) -> dict:
    cleaned = {field: fields.get(field) for field in FIELDS}
    visible_text = _visible_text(cleaned)
    if not cleaned.get("all_visible_text"):
        cleaned["all_visible_text"] = visible_text or None

    transcript_emails = _emails_from_text(visible_text)
    cleaned["email1"] = transcript_emails[0] if transcript_emails else _clean_email(cleaned.get("email1") or cleaned.get("email"))
    cleaned["email2"] = transcript_emails[1] if len(transcript_emails) > 1 else _clean_email(cleaned.get("email2"))
    cleaned["email"] = cleaned["email1"]
    transcript_websites = _websites_from_text(
        visible_text,
        transcript_emails,
        cleaned.get("business"),
        cleaned.get("company"),
        cleaned.get("name"),
    )
    cleaned["website"] = transcript_websites[0] if transcript_websites else _clean_website(cleaned.get("website"), cleaned.get("email1"))

    inferred_country, inferred_code = infer_country_and_code(
        cleaned.get("address"),
        visible_text,
        cleaned.get("city"),
        cleaned.get("state"),
        cleaned.get("country"),
        cleaned.get("phone_number"),
        cleaned.get("mobile_number"),
        cleaned.get("fax_number"),
    )
    phone_code = _country_code_from_phone(
        cleaned.get("contact1"),
        cleaned.get("contact2"),
        cleaned.get("contact3"),
        cleaned.get("mobile_number"),
        cleaned.get("phone_number"),
        cleaned.get("fax_number"),
        visible_text,
    )
    cleaned["country_code"] = phone_code or inferred_code or cleaned.get("country_code")
    phone_country = country_name_from_code(cleaned.get("country_code"))
    cleaned["country"] = phone_country or normalize_country_name(cleaned.get("country")) or inferred_country
    inferred_city, inferred_state = _infer_city_state("\n".join([visible_text, str(cleaned.get("address") or "")]))
    cleaned["city"] = cleaned.get("city") or inferred_city
    cleaned["state"] = cleaned.get("state") or inferred_state

    transcript_contacts = _contacts_from_text(visible_text, cleaned.get("country_code"))
    cleaned["contact1"] = transcript_contacts.get("contact1") or _clean_contact(cleaned.get("contact1") or cleaned.get("mobile_number"), cleaned.get("country_code"))
    cleaned["contact2"] = transcript_contacts.get("contact2") or _clean_contact(cleaned.get("contact2") or cleaned.get("phone_number"), cleaned.get("country_code"))
    cleaned["contact3"] = transcript_contacts.get("contact3") or _clean_contact(cleaned.get("contact3") or cleaned.get("fax_number"), cleaned.get("country_code"))
    if cleaned.get("contact2") == cleaned.get("contact1"):
        cleaned["contact2"] = None
    if cleaned.get("contact3") in {cleaned.get("contact1"), cleaned.get("contact2")}:
        cleaned["contact3"] = None
    normalized_phone = normalize_phone(cleaned.get("phone_number"), cleaned.get("country_code"))
    normalized_mobile = normalize_phone(cleaned.get("mobile_number"), cleaned.get("country_code"))
    normalized_fax = normalize_phone(cleaned.get("fax_number"), cleaned.get("country_code"))
    cleaned["phone_number"] = cleaned.get("contact2") or national_phone_number(normalized_phone, cleaned.get("country_code"))
    cleaned["mobile_number"] = cleaned.get("contact1") or national_phone_number(normalized_mobile, cleaned.get("country_code"))
    cleaned["fax_number"] = cleaned.get("contact3") or national_phone_number(normalized_fax, cleaned.get("country_code"))
    cleaned["phone_primary"] = (
        f"+{cleaned['contact1']}" if cleaned.get("contact1") else None
    ) or normalize_phone(cleaned.get("phone_primary"), cleaned.get("country_code")) or normalized_mobile or normalized_phone
    if not cleaned.get("company"):
        cleaned["company"] = cleaned.get("business")
    _drop_unsupported_fields(cleaned, visible_text)
    if cleaned.get("business") and not cleaned.get("company"):
        cleaned["company"] = cleaned["business"]
    if cleaned.get("company") and not cleaned.get("business"):
        cleaned["business"] = cleaned["company"]
    return cleaned


def structure_card_image(
    event_id: str,
    front_image: bytes,
    front_mime_type: str,
    back_image: bytes | None = None,
    back_mime_type: str | None = None,
) -> dict:
    prompt = f"""
Read this business card image directly. Do the task in two internal passes:
1. TEXT PASS: transcribe every readable printed text line from the front image and back image. Preserve line order and side labels. Include small footer text, icon-labeled contact lines, and logo text. Ignore QR payload decoding unless the QR's printed caption is visible.
2. SORTING PASS: map only the transcribed text into the requested Excel fields.

Return only valid JSON with these keys:
{", ".join(FIELDS)}

Rules:
{BUSINESS_CARD_VISUAL_RULES}
- Use only values visible on the card image.
- Do not invent missing values.
- Return null for fields not present.
- Prefer blank/null over guessing. Accuracy is more important than filling every cell.
- Every non-null field except category/country_code must be supported by a line in front_text/back_text.
- Never use service bullet text, marketing slogans, product names, product categories, or "Business Outline" headings as a person name or business name.
- If the front side contains a person block, name is the person block's name, designation is the line directly under/near that name, and business is the logo/company name.
- front_text must contain the full transcription of the front side, with lines separated by "\\n".
- back_text must contain the full transcription of the back side if provided, with lines separated by "\\n"; otherwise null.
- all_visible_text must combine front_text and back_text.
- field_evidence must be an object whose keys are field names and whose values are the exact transcript line(s) used for that field.
- uncertain_fields must be an array of field names you are not confident about.
- Read both sides if a back image is provided.
- Output must match this Excel schema: Date is created by the app; you return Name, Designation, Business, Address, City, State, Country, Zip Code, Website, Category, Social Media, Notes, Email1, Email2, Contact1, Contact2, Contact3.
- company and business mean the top-most brand/logo/company name on the card. On most business cards this is at the top of the front side, often as a stylized logo. Prefer that top brand text over address lines, building names, legal footers, or back-side office branch names.
- If the company name is stylized as a design/logo, interpret the visible letters as the company name. Do not describe the logo.
- country_code is the international dialing code, for example +91, +62, +971.
- phone_number means office/telephone/landline number from labels like T, Tel, Phone, Office.
- mobile_number means mobile/cell number from labels like M, Mob, Mobile, Cell.
- fax_number means fax number from labels like F or Fax.
- contact1 is the main direct/mobile number. contact2 is office/telephone/landline. contact3 is fax or another printed number.
- contact1, contact2, and contact3 must be digits only and include the country calling code when visible or inferable. Example: +60 13-358 1918 becomes 60133581918.
- If a number is already written as digits with country code, do not add the country code again.
- email1 is the primary email. email2 is the secondary email if printed.
- social_media should contain printed LinkedIn/Facebook/Instagram/WeChat/social handles or URLs only.
- notes should be null unless there is important printed context that does not fit any other column.
- phone_primary should prefer mobile_number when present, otherwise phone_number, and include country_code.
- Email must contain @ and a valid domain. Do not confuse email with website.
- Website must be the printed web/domain value such as www.example.com or example.com. Do not use email domains unless a website is separately printed.
- If multiple domains are visible, choose the website whose domain is most similar to the company/business name.
- If no separate website is printed, use an email domain as website only when it clearly matches the company/business name.
- Use address/country text and printed phone prefixes to infer country_code. The phone prefix wins when it conflicts with a guessed country.
- Country must be the full country name, not ISO code. For example use Indonesia, not ID.
- category must be exactly one of:
{", ".join(BUSINESS_CATEGORIES)}
""".strip()

    snapshot = usage_snapshot()
    prompt_tokens = estimate_tokens(prompt)
    if not snapshot.allowed or snapshot.daily_tokens + prompt_tokens > snapshot.daily_token_limit:
        record_usage(
            event_id,
            model=GEMINI_MODEL,
            purpose="business_card_image_structuring",
            prompt_tokens=prompt_tokens,
            status="blocked_local_limit",
            error_message="Local Gemini usage limit reached",
        )
        return {}


def structure_card_text(
    event_id: str,
    front_text: str,
    back_text: str | None = None,
    candidate_hints: list[dict] | None = None,
) -> dict:
    all_visible_text = "\n".join(part for part in [front_text, back_text or ""] if part.strip()).strip()
    prompt = f"""
You are sorting OCR text from a two-sided business card into Excel contact fields.

Return only valid JSON with these keys:
{", ".join(FIELDS)}

Rules:
{BUSINESS_CARD_VISUAL_RULES}
- The OCR text below is the only source of truth. Do not use outside knowledge.
- Do not invent missing values. Prefer null over a guessed value.
- Every non-null field except category/country_code must be supported by an exact OCR line.
- Preserve front_text and back_text exactly as supplied.
- Set all_visible_text to the combined OCR text.
- field_evidence must cite the exact OCR line(s) used for each non-null field.
- uncertain_fields must list fields where OCR is ambiguous or incomplete.
- Email fields must contain @.
- Website must be a printed website/domain value, not just the domain part of an email unless separately printed.
- If multiple domains are visible, choose the website whose domain is most similar to Business/company.
- If no separate website is printed, use the email domain as Website only when it clearly matches Business/company.
- Country must be the full country name, not ISO code. For example use Indonesia, not ID.
- Contact1 is main direct/mobile. Contact2 is office/telephone. Contact3 is fax or another printed number.
- Contact1, Contact2, and Contact3 must be digits only and include country calling code when visible or inferable.
- Business/company should be the top brand/company line from the front OCR text. If OCR missed the logo text, return null rather than guessing.
- Category must be exactly one of:
{", ".join(BUSINESS_CATEGORIES)}

OCR front:
{front_text or ""}

OCR back:
{back_text or ""}

Rule-based candidate hints:
{json.dumps(candidate_hints or [], ensure_ascii=False, indent=2)}
""".strip()

    snapshot = usage_snapshot()
    prompt_tokens = estimate_tokens(prompt)
    if not snapshot.allowed or snapshot.daily_tokens + prompt_tokens > snapshot.daily_token_limit:
        record_usage(
            event_id,
            model=GEMINI_MODEL,
            purpose="business_card_text_structuring",
            prompt_tokens=prompt_tokens,
            status="blocked_local_limit",
            error_message="Local Gemini usage limit reached",
        )
        return {}

    if not is_gemini_configured():
        record_usage(
            event_id,
            model=GEMINI_MODEL,
            purpose="business_card_text_structuring",
            prompt_tokens=prompt_tokens,
            status="skipped_not_configured",
            error_message="Gemini SDK or API key is missing",
        )
        return {}

    try:
        last_error: Exception | None = None
        for api_key, key_label in _gemini_keys():
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
                text = (getattr(response, "text", None) or "").strip()
                completion_tokens = estimate_tokens(text)
                record_usage(
                    event_id,
                    provider="gemini",
                    model=GEMINI_MODEL,
                    purpose="business_card_text_structuring",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    key_label=key_label,
                )
                parsed = _parse_json(text)
                parsed["front_text"] = front_text or parsed.get("front_text")
                parsed["back_text"] = back_text if back_text is not None else parsed.get("back_text")
                parsed["all_visible_text"] = all_visible_text or parsed.get("all_visible_text")
                return clean_structured_fields(parsed)
            except Exception as exc:
                last_error = exc
                message = str(exc)
                record_usage(
                    event_id,
                    provider="gemini",
                    model=GEMINI_MODEL,
                    purpose="business_card_text_structuring",
                    prompt_tokens=prompt_tokens,
                    status="error",
                    error_message=message[:500],
                    key_label=key_label,
                )
                if "429" not in message and "RESOURCE_EXHAUSTED" not in message:
                    break
        if last_error:
            raise last_error
        return {}
    except Exception as exc:
        return {}

    if not is_gemini_configured() or types is None:
        record_usage(
            event_id,
            model=GEMINI_MODEL,
            purpose="business_card_image_structuring",
            prompt_tokens=prompt_tokens,
            status="skipped_not_configured",
            error_message="Gemini SDK or API key is missing",
        )
        return {}

    contents = [
        prompt,
        types.Part.from_bytes(data=front_image, mime_type=front_mime_type or "image/jpeg"),
    ]
    if back_image:
        contents.append(types.Part.from_bytes(data=back_image, mime_type=back_mime_type or "image/jpeg"))

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(model=GEMINI_MODEL, contents=contents)
        text = (getattr(response, "text", None) or "").strip()
        completion_tokens = estimate_tokens(text)
        record_usage(
            event_id,
            model=GEMINI_MODEL,
            purpose="business_card_image_structuring",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        parsed = _parse_json(text)
        return clean_structured_fields(parsed)
    except Exception as exc:
        record_usage(
            event_id,
            model=GEMINI_MODEL,
            purpose="business_card_image_structuring",
            prompt_tokens=prompt_tokens,
            status="error",
            error_message=str(exc)[:500],
        )
        return {}
