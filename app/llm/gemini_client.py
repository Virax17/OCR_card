from __future__ import annotations

import json
import re

from app.config import BUSINESS_CATEGORIES, GEMINI_API_KEY, GEMINI_MODEL
from app.extraction.field_resolver import infer_country_and_code, national_phone_number, normalize_email, normalize_phone, normalize_website
from app.llm.usage_monitor import estimate_tokens, record_usage, usage_snapshot

try:
    from google import genai
    from google.genai import types
except Exception:  # pragma: no cover
    genai = None
    types = None


FIELDS = [
    "name",
    "designation",
    "company",
    "business",
    "phone_primary",
    "phone_number",
    "mobile_number",
    "phone_extra",
    "fax_number",
    "country_code",
    "email",
    "website",
    "address",
    "city",
    "state",
    "country",
    "zip_code",
    "category",
]

BUSINESS_CARD_VISUAL_RULES = """
Business-card layout rules learned from local samples:
- Treat the front side as the primary source for name, designation, company/business, email, website, and phone fields.
- The company/business name is usually the top-most stylized brand/logo text on the front side. It may be on the top-left or top-right, not necessarily in plain body text.
- Do not use branch names, office labels, building names, service-list headings, back-side product lists, slogans, or address landmarks as the company name.
- Back sides often contain branch addresses, support facilities, product photos, service outlines, target/safety slogans, and "we sell" lists. Use these for address/category support only unless a missing contact field is clearly printed there.
- Ignore QR codes, decorative icons, certification icons, product photos, separators, and handwritten notes unless the printed text beside them is part of a contact field.
- Person name is commonly the largest personal text block, often near the center/right, with designation directly below it.
- Email may be preceded by E, Email, Mail, or an envelope icon. It must contain @ and a valid domain.
- Website may be preceded by W, Web, Website, a globe icon, or printed in the footer. It is a web/domain value, not the email address.
- Phone labels can be short: T/Telp/Tel/Phone for office, M/Mob/Mobile/HP/Cell for mobile, F/Fax for fax.
- For country_code, trust explicit phone prefixes like +62, +91, +971 before address guesses. Indonesia/Jakarta/Kalimantan/Papua/Sorong with +62 means country_code +62.
- If the card has multiple offices on the back, do not replace the front contact phone/mobile/email with back-side branch office numbers.
""".strip()


def is_gemini_configured() -> bool:
    return bool(GEMINI_API_KEY) and genai is not None


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
WEBSITE_RE = re.compile(r"(?:https?://)?(?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+(?:/[^\s,;]*)?", re.I)


def _clean_email(value: str | None) -> str | None:
    if not value:
        return None
    match = EMAIL_RE.search(value.replace(" ", ""))
    return normalize_email(match.group(0)) if match else normalize_email(value)


def _clean_website(value: str | None, email: str | None = None) -> str | None:
    if not value:
        return None
    compact = value.strip().replace(" ", "")
    match = WEBSITE_RE.search(compact)
    if not match:
        return normalize_website(value)
    website = match.group(0).rstrip(".")
    if email and website.lower() in email.lower():
        return None
    return normalize_website(website)


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
        digits = re.sub(r"[^\d+]", "", value)
        if digits.startswith("00"):
            digits = f"+{digits[2:]}"
        for code in sorted(known_codes, key=len, reverse=True):
            if digits.startswith(code):
                return code
    return None


def clean_structured_fields(fields: dict) -> dict:
    cleaned = {field: fields.get(field) for field in FIELDS}
    cleaned["email"] = _clean_email(cleaned.get("email"))
    cleaned["website"] = _clean_website(cleaned.get("website"), cleaned.get("email"))

    inferred_country, inferred_code = infer_country_and_code(
        cleaned.get("address"),
        cleaned.get("city"),
        cleaned.get("state"),
        cleaned.get("country"),
        cleaned.get("phone_number"),
        cleaned.get("mobile_number"),
        cleaned.get("fax_number"),
    )
    phone_code = _country_code_from_phone(cleaned.get("mobile_number"), cleaned.get("phone_number"), cleaned.get("fax_number"))
    cleaned["country_code"] = phone_code or inferred_code or cleaned.get("country_code")
    if not cleaned.get("country"):
        cleaned["country"] = inferred_country

    normalized_phone = normalize_phone(cleaned.get("phone_number"), cleaned.get("country_code"))
    normalized_mobile = normalize_phone(cleaned.get("mobile_number"), cleaned.get("country_code"))
    normalized_fax = normalize_phone(cleaned.get("fax_number"), cleaned.get("country_code"))
    cleaned["phone_number"] = national_phone_number(normalized_phone, cleaned.get("country_code"))
    cleaned["mobile_number"] = national_phone_number(normalized_mobile, cleaned.get("country_code"))
    cleaned["fax_number"] = national_phone_number(normalized_fax, cleaned.get("country_code"))
    cleaned["phone_primary"] = normalize_phone(cleaned.get("phone_primary"), cleaned.get("country_code")) or normalized_mobile or normalized_phone
    return cleaned


def structure_card_image(
    event_id: str,
    front_image: bytes,
    front_mime_type: str,
    back_image: bytes | None = None,
    back_mime_type: str | None = None,
) -> dict:
    prompt = f"""
Read this business card image directly and extract the visible contact details.
Return only valid JSON with these keys:
{", ".join(FIELDS)}

Rules:
{BUSINESS_CARD_VISUAL_RULES}
- Use only values visible on the card image.
- Do not invent missing values.
- Return null for fields not present.
- Read both sides if a back image is provided.
- company and business mean the top-most brand/logo/company name on the card. On most business cards this is at the top of the front side, often as a stylized logo. Prefer that top brand text over address lines, building names, legal footers, or back-side office branch names.
- If the company name is stylized as a design/logo, interpret the visible letters as the company name. Do not describe the logo.
- country_code is the international dialing code, for example +91, +62, +971.
- phone_number means office/telephone/landline number from labels like T, Tel, Phone, Office.
- mobile_number means mobile/cell number from labels like M, Mob, Mobile, Cell.
- fax_number means fax number from labels like F or Fax.
- phone_primary should prefer mobile_number when present, otherwise phone_number, and include country_code.
- Email must contain @ and a valid domain. Do not confuse email with website.
- Website must be the printed web/domain value such as www.example.com or example.com. Do not use email domains unless a website is separately printed.
- Use address/country text and printed phone prefixes to infer country_code. The phone prefix wins when it conflicts with a guessed country.
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
