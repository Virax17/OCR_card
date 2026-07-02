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
GEMINI_API_KEY_2 = os.getenv("GEMINI_API_KEY_2")
GEMINI_API_KEY_3 = os.getenv("GEMINI_API_KEY_3")
GEMINI_API_KEYS = [
    key.strip()
    for key in ",".join(
        value
        for value in [
            os.getenv("GEMINI_API_KEYS", ""),
            GEMINI_API_KEY or "",
            GEMINI_API_KEY_2 or "",
            GEMINI_API_KEY_3 or "",
        ]
        if value
    ).split(",")
    if key.strip()
]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
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
GOOGLE_APPLICATION_CREDENTIALS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    r"D:\tritorc\caramel-medley-500511-f3-b43018325a04.json",
)
GOOGLE_VISION_MODEL = os.getenv("GOOGLE_VISION_MODEL", "builtin/weekly")
GOOGLE_VISION_TIMEOUT_SECONDS = int(os.getenv("GOOGLE_VISION_TIMEOUT_SECONDS", "60"))
GOOGLE_VISION_MINUTE_REQUEST_LIMIT = int(os.getenv("GOOGLE_VISION_MINUTE_REQUEST_LIMIT", "1800"))
GOOGLE_VISION_FREE_UNITS_MONTHLY = int(os.getenv("GOOGLE_VISION_FREE_UNITS_MONTHLY", "1000"))
GOOGLE_VISION_PRICE_PER_1000 = float(os.getenv("GOOGLE_VISION_PRICE_PER_1000", "1.50"))

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}

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
