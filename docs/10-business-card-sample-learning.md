# Business Card Sample Learning

Status: Active extraction guidance  
Last updated: 2026-07-01  
Source images: `D:\tritorc\ocr\data`

## What The Local Samples Show

The current sample folder contains 15 WhatsApp business-card images. The cards are not plain documents. They include:

```text
front/back pairs
stylized logos
QR codes
branch-office lists on back side
product photos
service-outline panels
colored backgrounds
icons beside contact fields
some handwritten notes
```

This means extraction should not treat every visible text line equally.

## Primary Extraction Rule

Use a two-pass extraction method inside the single Gemini call:

```text
1. Transcribe all visible printed text from the front and back images.
2. Sort only that transcribed text into the Excel fields.
```

The app saves the LLM transcript audit here:

```text
events/<event_id>/ocr/<card_id>_llm_transcript.txt
```

The audit file contains:

```text
front_text
back_text
all_visible_text
field_evidence
uncertain_fields
```

When a row is wrong, inspect this file first. If the text was read correctly but sorted into the wrong field, improve field rules. If the text was not transcribed correctly, improve image quality or Vision prompt examples.

Post-processing now validates the LLM output against the transcript:

```text
Email1 / Email2 -> re-extracted from transcript using email patterns
Website         -> re-extracted from printed URL/domain text
Contact1-3      -> re-extracted from transcript phone lines and labels
Name/Business/etc. -> removed if not supported by transcript text
```

The system should prefer blank cells over hallucinated cells.

Use the front side as the primary source for:

```text
Name
Designation
Company / Business
Phone Number
Mobile Number
Fax Number
Email
Website
```

Use the back side mainly for:

```text
Address support
Country/city hints
Category classification
Secondary branch-office context
```

Do not let back-side product/service lists replace the front-side contact person details.

## Company Name Rule

The company/business name is usually the top-most stylized brand/logo text on the front side.

Examples from the sample set:

```text
PETROSEA
Babcock & Wilcox
TOKKI
PT. AIR SURYA RADIATOR
PT. Kezindo Sejahtera Abadi
Mechatechra
```

The company may appear as a logo, not as normal body text. It may be top-left, top-right, or embedded in a visual mark.

Avoid using these as company names:

```text
Head Office
Support Facilities
Business Outline
We Sell
Target Zero
address building names
branch office names
product category headings
```

## Contact Field Labels

Use label-aware extraction:

```text
T / Tel / Telp / Phone / Office / Landline -> phone_number
M / Mob / Mobile / HP / Cell               -> mobile_number
F / Fax                                    -> fax_number
E / Email / Mail                           -> email
W / Web / Website                          -> website
```

Icons can replace labels. Envelope-like icons usually indicate email. Globe/web icons usually indicate website.

## Email And Website Rules

Email:

```text
must contain @
must have a valid domain
should not be copied into website
```

Website:

```text
must be a printed domain or URL
may appear near the bottom/footer
may be shown without https://
should not be guessed from email unless separately printed
```

## Country Code Rules

Country code should be inferred using this order:

```text
1. explicit phone prefix, such as +62, +91, +971
2. country/city/address text
3. default country only as last fallback
```

If a phone number starts with a country prefix, split it:

```text
country_code: +62
phone_number: local/national number only
mobile_number: local/national number only
fax_number: local/national number only
phone_primary: normalized international number for duplicate matching
```

## Visual Noise To Ignore

Do not extract these as business-card fields:

```text
QR code payloads
decorative stripes
certification icons
product photos
safety slogans
marketing bullet lists
handwritten notes
```

Marketing/service text can still help classify `Category`.

## MCP Update

The same guidance has been added to:

```text
.agents/mcp_gemini_config.json
app/llm/gemini_client.py
```

This keeps the app prompt and future MCP/agent usage aligned.

## Supervised Excel Format

The `Grid AI - Contacts.xlsx` workbook is the target output format. The app should export exactly these headers in sheet `contacts`:

```text
Date
Name
Designation
Business
Address
City
State
Country
Zip Code
Website
Category
Social Media
Notes
Email1
Email2
Contact1
Contact2
Contact3
Card
```

Learning from the workbook:

```text
Email1 = primary email
Email2 = secondary email
Contact1 = main direct/mobile number
Contact2 = office/telephone/landline
Contact3 = fax or another printed number
Card = card image for verification
```

Contact columns should be digits only with country calling code included when visible or inferable:

```text
+60 13-358 1918 -> 60133581918
+91 82919 71166 -> 918291971166
+62 21 2977 0999 -> 622129770999
```

Do not include plus signs, spaces, hyphens, or parentheses in `Contact1`, `Contact2`, or `Contact3`.

If a contact already starts with the country code, do not add it again:

```text
60133581918 stays 60133581918
not 6060133581918
```

## APAC Visit Image Set

The `Madhav Tiwari-APAC Visit-20260701T113500Z-3-001` folder shows several recurring card patterns:

```text
front/back card pairs
duplicate image copies
logo-heavy company names
business-outline backs
product/service backs
QR-code cards
handwritten notes that should usually be ignored
Indonesia/Malaysia/Singapore contact formats
```

The extraction prompt now prioritizes the front side for contact details and uses the back side mostly for address, service context, and category.

## UI Workflow

The app UI supports event-local scanning:

```text
1. Create or select an event.
2. Upload front image and optional back image.
3. Store the card under that event.
4. Download that event's Excel file only.
```

The download button uses:

```text
GET /events/<event_id>/download
```

The resulting workbook uses sheet `contacts`, the 19 Grid AI headers, and embedded card images in the `Card` column.
