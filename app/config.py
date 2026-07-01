from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv:
    load_dotenv()

EVENTS_ROOT = Path(os.getenv("EVENTS_ROOT", "events"))
DEFAULT_EVENT_ID = os.getenv("DEFAULT_EVENT_ID", "test_uploads")
DEFAULT_EVENT_NAME = os.getenv("DEFAULT_EVENT_NAME", "Test Uploads")
DEFAULT_EVENT_DATE = os.getenv("DEFAULT_EVENT_DATE", "2026-07-01")
DEFAULT_COUNTRY = os.getenv("DEFAULT_COUNTRY", "IN")
LLM_FALLBACK_ENABLED = os.getenv("LLM_FALLBACK_ENABLED", "false").lower() in {"1", "true", "yes"}
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_DAILY_REQUEST_LIMIT = int(os.getenv("GEMINI_DAILY_REQUEST_LIMIT", "50"))
GEMINI_MINUTE_REQUEST_LIMIT = int(os.getenv("GEMINI_MINUTE_REQUEST_LIMIT", "10"))
GEMINI_DAILY_TOKEN_LIMIT = int(os.getenv("GEMINI_DAILY_TOKEN_LIMIT", "100000"))

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}

EXCEL_COLUMNS = [
    "front_image",
    "back_image",
    "date",
    "name",
    "designation",
    "business",
    "address",
    "city",
    "state",
    "country",
    "zip_code",
    "website",
    "country_code",
    "phone_number",
    "mobile_number",
    "fax_number",
    "category",
]

EXCEL_HEADERS = {
    "front_image": "Front Image",
    "back_image": "Back Image",
    "date": "Date",
    "name": "Name",
    "designation": "Designation",
    "business": "Business",
    "address": "Address",
    "city": "City",
    "state": "State",
    "country": "Country",
    "zip_code": "Zip Code",
    "website": "Website",
    "country_code": "Country Code",
    "phone_number": "Phone Number",
    "mobile_number": "Mobile Number",
    "fax_number": "Fax Number",
    "category": "Category",
}

BUSINESS_CATEGORIES = [
    "Engineering",
    "Industrial Services",
    "Certification",
    "Supply Chain Management",
    "Marine Contractors",
    "Oil & Gas",
    "Manufacturing",
    "Construction",
    "Logistics",
    "Trading",
    "Other",
]
