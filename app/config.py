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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def _gemini_api_keys_from_env() -> list[str]:
    numbered_keys = [
        value
        for _, value in sorted(
            (
                (int(name.rsplit("_", 1)[1]), value)
                for name, value in os.environ.items()
                if name.startswith("GEMINI_API_KEY_")
                and name.rsplit("_", 1)[1].isdigit()
                and value
            ),
            key=lambda item: item[0],
        )
    ]
    values = [os.getenv("GEMINI_API_KEYS", ""), GEMINI_API_KEY or "", *numbered_keys]
    keys: list[str] = []
    seen: set[str] = set()
    for value in values:
        for key in value.split(","):
            clean = key.strip()
            if clean and clean not in seen:
                keys.append(clean)
                seen.add(clean)
    return keys


GEMINI_API_KEYS = _gemini_api_keys_from_env()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# When true, send the card image(s) to Gemini alongside the OCR transcript
# (multimodal) so brand/logo vs. person-name layout is judged from the actual
# picture instead of flattened OCR text. Still exactly one Gemini call per
# card either way, so it doesn't change free-tier request-quota usage.
GEMINI_USE_IMAGE = os.getenv("GEMINI_USE_IMAGE", "true").lower() in {"1", "true", "yes"}
GEMINI_PROJECT_COUNT = max(1, int(os.getenv("GEMINI_PROJECT_COUNT", str(len(GEMINI_API_KEYS) or 1))))
GEMINI_DAILY_REQUEST_LIMIT_PER_PROJECT = int(
    os.getenv("GEMINI_DAILY_REQUEST_LIMIT_PER_PROJECT", os.getenv("GEMINI_DAILY_REQUEST_LIMIT", "50"))
)
GEMINI_MINUTE_REQUEST_LIMIT_PER_PROJECT = int(
    os.getenv("GEMINI_MINUTE_REQUEST_LIMIT_PER_PROJECT", os.getenv("GEMINI_MINUTE_REQUEST_LIMIT", "10"))
)
GEMINI_DAILY_TOKEN_LIMIT_PER_PROJECT = int(
    os.getenv("GEMINI_DAILY_TOKEN_LIMIT_PER_PROJECT", os.getenv("GEMINI_DAILY_TOKEN_LIMIT", "100000"))
)
GEMINI_DAILY_REQUEST_LIMIT = GEMINI_DAILY_REQUEST_LIMIT_PER_PROJECT * GEMINI_PROJECT_COUNT
GEMINI_MINUTE_REQUEST_LIMIT = GEMINI_MINUTE_REQUEST_LIMIT_PER_PROJECT * GEMINI_PROJECT_COUNT
GEMINI_DAILY_TOKEN_LIMIT = GEMINI_DAILY_TOKEN_LIMIT_PER_PROJECT * GEMINI_PROJECT_COUNT
# Cloud-friendly credential source: the full service-account JSON as a string
# (raw JSON or base64-encoded). Preferred on hosts where you cannot place a file.
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
# Local-dev credential source: path to a service-account JSON file on disk.
# No default path — an unset value fails loudly instead of pointing at a dead path.
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GOOGLE_VISION_MODEL = os.getenv("GOOGLE_VISION_MODEL", "builtin/stable")
GOOGLE_VISION_TIMEOUT_SECONDS = int(os.getenv("GOOGLE_VISION_TIMEOUT_SECONDS", "60"))
GOOGLE_VISION_MINUTE_REQUEST_LIMIT = int(os.getenv("GOOGLE_VISION_MINUTE_REQUEST_LIMIT", "1800"))
GOOGLE_VISION_FREE_UNITS_MONTHLY = int(os.getenv("GOOGLE_VISION_FREE_UNITS_MONTHLY", "1000"))
GOOGLE_VISION_PRICE_PER_1000 = float(os.getenv("GOOGLE_VISION_PRICE_PER_1000", "1.50"))
# Comma-separated BCP-47 language hints to improve Vision's recognition of
# non-English names/text commonly seen on cards (e.g. "en,id,ar,zh").
GOOGLE_VISION_LANGUAGE_HINTS = [
    hint.strip() for hint in os.getenv("GOOGLE_VISION_LANGUAGE_HINTS", "en").split(",") if hint.strip()
]

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}

# MongoDB — persistent, restart-surviving usage counters with per-period buckets.
# Unset MONGODB_URI (or MONGO_USAGE_ENABLED=false) disables the feature entirely;
# processing then falls back to the local SQLite-only behaviour.
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "cardscan")
MONGO_USAGE_ENABLED = os.getenv("MONGO_USAGE_ENABLED", "true").lower() not in {"0", "false", "no"}
# Deprecated compatibility flag. The app now fails open when MongoDB is
# unreachable so trade-show scanning can continue with local counters.
MONGO_USAGE_FAIL_CLOSED = os.getenv("MONGO_USAGE_FAIL_CLOSED", "true").lower() not in {"0", "false", "no"}
# Google Vision free tier is 1000 OCR units per calendar month.
MONGO_VISION_MONTHLY_LIMIT = int(os.getenv("MONGO_VISION_MONTHLY_LIMIT", "1000"))
# Gemini: hard global cap on requests per day across all API keys.
MONGO_GEMINI_DAILY_LIMIT = int(os.getenv("MONGO_GEMINI_DAILY_LIMIT", "120"))
# How long a usage bucket document lives before Mongo auto-deletes it (TTL).
# Comfortably longer than a month so the current bucket is never expired early.
MONGO_USAGE_TTL_DAYS = int(os.getenv("MONGO_USAGE_TTL_DAYS", "40"))

EXCEL_COLUMNS = [
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
    "category",
    "social_media",
    "notes",
    "email1",
    "email2",
    "contact1",
    "contact2",
    "contact3",
    "card",
]

EXCEL_HEADERS = {
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
    "category": "Category",
    "social_media": "Social Media",
    "notes": "Notes",
    "email1": "Email1",
    "email2": "Email2",
    "contact1": "Contact1",
    "contact2": "Contact2",
    "contact3": "Contact3",
    "card": "Card",
}

BUSINESS_CATEGORIES = [
    "Engineering",
    "Engineering Services",
    "Industrial Services",
    "Industrial Equipment",
    "Certification",
    "Supply Chain Management",
    "Marine Contractors",
    "Marine Services",
    "Oil & Gas",
    "Oil and Gas",
    "Oilfield Services",
    "Manufacturing",
    "Construction",
    "Logistics",
    "Trading",
    "Energy",
    "Energy Services",
    "Renewable Energy",
    "Technology",
    "Sales",
    "Services",
    "Business Services",
    "Industrial",
    "Other",
]
