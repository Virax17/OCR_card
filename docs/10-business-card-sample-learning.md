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
