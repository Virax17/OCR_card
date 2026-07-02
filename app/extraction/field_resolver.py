from __future__ import annotations

import re
from datetime import datetime

from app.config import BUSINESS_CATEGORIES, DEFAULT_COUNTRY
from app.models import BusinessCardRecord, FieldCandidate, OCRSideResult
from app.storage.db import new_id


def _best(candidates: list[FieldCandidate], field: str) -> FieldCandidate | None:
    field_candidates = [candidate for candidate in candidates if candidate.field == field]
    if not field_candidates:
        return None
    return sorted(field_candidates, key=lambda candidate: candidate.confidence, reverse=True)[0]


def normalize_email(value: str | None) -> str | None:
    return value.strip().lower() if value else None


COUNTRY_HINTS = [
    ("India", "IN", "+91", ["india", "bharat", "maharashtra", "gujarat", "mumbai", "pune", "delhi", "chennai", "kolkata", "bengaluru", "bangalore"]),
    ("Indonesia", "ID", "+62", ["indonesia", "jakarta", "balikpapan", "kalimantan", "papua", "sorong", "bekasi", "banten", "cilegon", "gresik", "cikarang"]),
    ("United Arab Emirates", "AE", "+971", ["uae", "united arab emirates", "dubai", "abu dhabi", "sharjah"]),
    ("Saudi Arabia", "SA", "+966", ["saudi", "ksa", "riyadh", "jeddah", "dammam"]),
    ("Qatar", "QA", "+974", ["qatar", "doha"]),
    ("Oman", "OM", "+968", ["oman", "muscat"]),
    ("Kuwait", "KW", "+965", ["kuwait"]),
    ("Bahrain", "BH", "+973", ["bahrain"]),
    ("United States", "US", "+1", ["usa", "united states", "america", "california", "texas", "new york"]),
    ("United Kingdom", "GB", "+44", ["uk", "united kingdom", "england", "london"]),
    ("Singapore", "SG", "+65", ["singapore"]),
    ("Malaysia", "MY", "+60", ["malaysia", "kuala lumpur"]),
]


def infer_country_and_code(*values: str | None) -> tuple[str, str]:
    text = " ".join(value or "" for value in values).lower()
    for country, _, dial_code, hints in COUNTRY_HINTS:
        if any(hint in text for hint in hints):
            return country, dial_code
    default = DEFAULT_COUNTRY.upper()
    for country, iso_code, dial_code, _ in COUNTRY_HINTS:
        if iso_code == default or country.upper() == default:
            return country, dial_code
    return "India", "+91"


def country_name_from_code(country_code: str | None) -> str | None:
    if not country_code:
        return None
    code_digits = re.sub(r"\D", "", country_code)
    if not code_digits:
        return None
    for country, _, dial_code, _ in COUNTRY_HINTS:
        if code_digits == re.sub(r"\D", "", dial_code):
            return country
    return None


def normalize_country_name(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    normalized_key = normalized.lower()
    for country, iso_code, _, hints in COUNTRY_HINTS:
        if normalized_key in {country.lower(), iso_code.lower()} or normalized_key in hints:
            return country
    return normalized


def normalize_phone(value: str | None, country_code: str | None = None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[^\d+]", "", value)
    if cleaned.count("+") > 1:
        cleaned = cleaned.replace("+", "")
    if cleaned.startswith("00"):
        cleaned = f"+{cleaned[2:]}"
    if country_code and cleaned and not cleaned.startswith("+"):
        digits = re.sub(r"\D", "", cleaned)
        if digits.startswith("0"):
            digits = digits.lstrip("0")
        cleaned = f"{country_code}{digits}"
    return cleaned or None


def national_phone_number(value: str | None, country_code: str | None = None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if country_code:
        code_digits = re.sub(r"\D", "", country_code)
        if digits.startswith(code_digits):
            digits = digits[len(code_digits):]
    return digits.lstrip("0") or None


def normalize_website(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if value.lower().startswith(("http://", "https://")):
        return value
    return f"https://{value}"


def category_from_business_text(*values: str | None) -> str:
    text = " ".join(value or "" for value in values).lower()
    rules = [
        ("Oil & Gas", ["oil", "gas", "petroleum", "petrochemical", "offshore", "refinery"]),
        ("Marine Contractors", ["marine", "ship", "vessel", "dock", "port", "harbour", "harbor"]),
        ("Certification", ["certification", "inspection", "audit", "iso", "testing", "quality"]),
        ("Supply Chain Management", ["supply chain", "logistics", "warehouse", "procurement", "freight"]),
        ("Industrial Services", ["industrial service", "maintenance", "fabrication", "shutdown", "repair"]),
        ("Engineering", ["engineering", "engineers", "automation", "design", "technical", "consulting"]),
        ("Manufacturing", ["manufacturing", "manufacturer", "factory", "production"]),
        ("Construction", ["construction", "contractor", "infrastructure", "civil"]),
        ("Trading", ["trading", "traders", "exports", "imports", "distributor", "supplier"]),
        ("Logistics", ["logistics", "transport", "cargo", "shipping"]),
    ]
    for category, keywords in rules:
        if any(keyword in text for keyword in keywords):
            return category
    return "Other"


def resolve_record(
    *,
    event_id: str,
    event_name: str,
    card_id: str,
    front_image_filename: str,
    back_image_filename: str | None,
    ocr_results: list[OCRSideResult],
    candidates: list[FieldCandidate],
    duplicate_flag: str = "No",
) -> BusinessCardRecord:
    now = datetime.now()
    phone_candidates = sorted([candidate for candidate in candidates if candidate.field == "phone"], key=lambda item: item.confidence, reverse=True)
    mobile_candidates = sorted([candidate for candidate in candidates if candidate.field == "mobile"], key=lambda item: item.confidence, reverse=True)
    fax_candidates = sorted([candidate for candidate in candidates if candidate.field == "fax"], key=lambda item: item.confidence, reverse=True)
    address_lines = [candidate.value for candidate in candidates if candidate.field == "address"]
    avg_ocr = sum(result.average_confidence for result in ocr_results) / max(1, len(ocr_results))
    raw_text = " ".join(result.raw_text for result in ocr_results)

    name = _best(candidates, "name")
    designation = _best(candidates, "designation")
    company = _best(candidates, "company")
    email = _best(candidates, "email")
    website = _best(candidates, "website")
    address = ", ".join(dict.fromkeys(address_lines)) or None
    country, country_code = infer_country_and_code(address, raw_text)

    normalized_phone = normalize_phone(phone_candidates[0].value, country_code) if phone_candidates else None
    normalized_mobile = normalize_phone(mobile_candidates[0].value, country_code) if mobile_candidates else None
    normalized_primary = normalized_mobile or normalized_phone
    resolved = {
        "name": name.value if name else None,
        "designation": designation.value if designation else None,
        "company": company.value if company else None,
        "business": company.value if company else None,
        "phone_primary": normalized_primary,
        "phone_number": national_phone_number(normalized_phone, country_code),
        "mobile_number": national_phone_number(normalized_mobile, country_code),
        "phone_extra": normalize_phone(phone_candidates[1].value, country_code) if len(phone_candidates) > 1 else None,
        "fax_number": national_phone_number(normalize_phone(fax_candidates[0].value, country_code), country_code) if fax_candidates else None,
        "country_code": country_code,
        "email": normalize_email(email.value if email else None),
        "website": normalize_website(website.value if website else None),
        "address": address,
        "country": country,
    }
    resolved["category"] = category_from_business_text(
        resolved["business"],
        resolved["designation"],
        resolved["website"],
        resolved["address"],
        raw_text,
    )

    low_fields = [
        field
        for field in ["name", "company", "phone_primary", "email"]
        if not resolved.get(field)
    ]
    if avg_ocr < 0.65:
        low_fields.append("ocr")
    if resolved["email"] or resolved["phone_primary"]:
        confidence = "High" if not low_fields[:2] and avg_ocr >= 0.75 else "Medium"
    else:
        confidence = "Low"

    return BusinessCardRecord(
        record_id=new_id("record"),
        card_id=card_id,
        event_id=event_id,
        date=now.strftime("%Y-%m-%d"),
        time=now.strftime("%H:%M:%S"),
        event_name=event_name,
        confidence_score=confidence,
        low_confidence_fields=sorted(set(low_fields)),
        duplicate_flag=duplicate_flag,
        front_image_filename=front_image_filename,
        back_image_filename=back_image_filename,
        **resolved,
    )
