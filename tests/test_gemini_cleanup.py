from app.llm.gemini_client import clean_structured_fields, structure_card_text_deterministic


def test_grid_ai_contacts_are_cleaned_to_excel_format() -> None:
    fields = clean_structured_fields(
        {
            "business": "East Coast O&G Metal Works",
            "country": "Malaysia",
            "email1": " kelvin@ecom.net.my ",
            "email2": "team@ecom.net.my",
            "website": "www.ecom.net.my",
            "contact1": "+60 13-358 1918",
            "contact2": "(+60) 9-859 1918",
            "contact3": "Fax +60 9-859 1919",
            "front_text": "\n".join(
                [
                    "East Coast O&G Metal Works",
                    "kelvin@ecom.net.my",
                    "team@ecom.net.my",
                    "www.ecom.net.my",
                    "M +60 13-358 1918",
                    "T (+60) 9-859 1918",
                    "Fax +60 9-859 1919",
                ]
            ),
        }
    )

    assert fields["business"] == "East Coast O&G Metal Works"
    assert fields["email1"] == "kelvin@ecom.net.my"
    assert fields["email2"] == "team@ecom.net.my"
    assert fields["email"] == "kelvin@ecom.net.my"
    assert fields["website"] == "https://www.ecom.net.my"
    assert fields["contact1"] == "60133581918"
    assert fields["contact2"] == "6098591918"
    assert fields["contact3"] == "6098591919"
    assert fields["phone_primary"] == "+60133581918"


def test_digit_contacts_with_country_code_are_not_prefixed_twice() -> None:
    fields = clean_structured_fields(
        {
            "country": "Malaysia",
            "country_code": "+60",
            "contact1": "60133581918",
            "contact2": "6098591918",
            "front_text": "M 60133581918\nT 6098591918",
        }
    )

    assert fields["contact1"] == "60133581918"
    assert fields["contact2"] == "6098591918"
    assert fields["phone_primary"] == "+60133581918"


def test_indonesia_contacts_are_not_prefixed_twice() -> None:
    fields = clean_structured_fields(
        {
            "country": "Indonesia",
            "country_code": "+62",
            "contact1": "6281236678953",
            "contact2": "622129770999",
            "phone_primary": "6281236678953",
            "front_text": "M 6281236678953\nT 622129770999",
        }
    )

    assert fields["contact1"] == "6281236678953"
    assert fields["contact2"] == "622129770999"
    assert fields["phone_primary"] == "+6281236678953"
    assert fields["mobile_number"] == "6281236678953"
    assert fields["country"] == "Indonesia"


def test_country_is_inferred_from_phone_code_when_not_printed() -> None:
    fields = clean_structured_fields(
        {
            "business": "Petrosea",
            "front_text": "Petrosea\nM +62 812 3667 8953\nE ahmad.ajitama@petrosea.com",
        }
    )

    assert fields["country_code"] == "+62"
    assert fields["country"] == "Indonesia"
    assert fields["contact1"] == "6281236678953"


def test_indonesia_local_mobile_uses_address_country_code() -> None:
    fields = clean_structured_fields(
        {
            "front_text": "\n".join(
                [
                    "ASR PT. AIR SURYA RADIATOR",
                    "Mobile : 08212307 8763",
                    "Bekasi 17156",
                ]
            ),
        }
    )

    assert fields["country_code"] == "+62"
    assert fields["country"] == "Indonesia"
    assert fields["contact1"] == "6282123078763"


def test_model_business_not_supported_by_transcript_is_dropped() -> None:
    fields = clean_structured_fields(
        {
            "business": "Fake Hallucinated Company",
            "front_text": "ALPHA INDUSTRIAL\nRavi Kumar\nSales Manager\nravi@alpha.example",
        }
    )

    assert fields["business"] is None
    assert fields["company"] is None
    assert fields["email1"] == "ravi@alpha.example"


def test_spaced_ocr_email_is_captured() -> None:
    fields = clean_structured_fields(
        {
            "front_text": "E info @ tritorc . com\nsales (at) tritorc (dot) com",
        }
    )

    assert fields["email1"] == "info@tritorc.com"
    assert fields["email2"] == "sales@tritorc.com"


def test_website_prefers_company_matching_domain() -> None:
    fields = clean_structured_fields(
        {
            "business": "Petrosea",
            "front_text": "\n".join(
                [
                    "Petrosea",
                    "E contact@randomvendor.com",
                    "W www.petrosea.com",
                    "www.unrelated-example.com",
                ]
            ),
        }
    )

    assert fields["website"] == "https://www.petrosea.com"


def test_email_domain_can_fill_website_when_it_matches_company() -> None:
    fields = clean_structured_fields(
        {
            "business": "Tritorc",
            "front_text": "Tritorc\nE info@tritorc.com",
        }
    )

    assert fields["website"] == "https://tritorc.com"


def test_email_local_part_is_not_used_as_website() -> None:
    fields = clean_structured_fields(
        {
            "business": "Petrosea",
            "front_text": "Petrosea\nE Ahmad.Ajitama@petrosea.com",
        }
    )

    assert fields["website"] == "https://petrosea.com"


def test_deterministic_text_structuring_fills_fields_without_llm() -> None:
    fields = structure_card_text_deterministic(
        front_text="\n".join(
            [
                "TOKKI",
                "FITRI ALFIANA",
                "Procurement Officer",
                "+62 877-7190-3337",
                "fia@tef.co.id",
                "Indonesia 42443",
            ]
        ),
        candidate_hints=[
            {"field": "name", "value": "FITRI ALFIANA", "confidence": 0.8, "source": "front"},
            {"field": "designation", "value": "Procurement Officer", "confidence": 0.8, "source": "front"},
            {"field": "company", "value": "TOKKI", "confidence": 0.75, "source": "front"},
            {"field": "email", "value": "fia@tef.co.id", "confidence": 0.95, "source": "rule"},
            {"field": "mobile", "value": "+62 877-7190-3337", "confidence": 0.9, "source": "rule"},
        ],
    )

    assert fields["name"] == "FITRI ALFIANA"
    assert fields["designation"] == "Procurement Officer"
    assert fields["business"] == "TOKKI"
    assert fields["email1"] == "fia@tef.co.id"
    assert fields["contact1"] == "6287771903337"
    assert fields["country"] == "Indonesia"


def test_deterministic_text_structuring_infers_top_brand_and_address() -> None:
    fields = structure_card_text_deterministic(
        front_text="\n".join(
            [
                "ASR PT. AIR SURYA RADIATOR",
                "DESIGN & FABRICATION",
                "BUDI SANTOSO",
                "Marketing",
                "Mobile : 08212307 8763",
                "E-mail : bsantoso69.ptasr@gmail.com",
                "Jl. Mawar No. 88 Rt. 04/02 Padurenan, Mustika Jaya - Bekasi 17156",
                "Website: http://www.ptasr.co.id; e-mail: marketing@ptasr.co.id",
            ]
        ),
        candidate_hints=[
            {"field": "email", "value": "bsantoso69.ptasr@gmail.com", "confidence": 0.95},
            {"field": "email", "value": "marketing@ptasr.co.id", "confidence": 0.95},
            {"field": "mobile", "value": "08212307 8763", "confidence": 0.9},
            {"field": "website", "value": "http://www.ptasr.co.id", "confidence": 0.8},
        ],
    )

    assert fields["business"] == "ASR PT. AIR SURYA RADIATOR"
    assert fields["name"] == "BUDI SANTOSO"
    assert fields["designation"] == "Marketing"
    assert "Bekasi" in fields["address"]
    assert fields["zip_code"] == "17156"
    assert fields["website"] == "http://www.ptasr.co.id"


def test_cleanup_replaces_company_name_misclassified_as_person_name() -> None:
    fields = clean_structured_fields(
        {
            "front_text": "\n".join(
                [
                    "TOKKI",
                    "FITRI ALFIANA",
                    "Procurement Officer",
                    "+62 877-7190-3337",
                    "fia@tef.co.id",
                ]
            ),
            "name": "TOKKI",
            "business": "TOKKI",
            "designation": "Procurement Officer",
            "contact1": "+62 877-7190-3337",
            "email1": "fia@tef.co.id",
        }
    )

    assert fields["business"] == "TOKKI"
    assert fields["company"] == "TOKKI"
    assert fields["name"] == "FITRI ALFIANA"


def test_cleanup_rejects_legal_entity_as_person_name() -> None:
    fields = clean_structured_fields(
        {
            "front_text": "\n".join(
                [
                    "ASR PT. AIR SURYA RADIATOR",
                    "DESIGN & FABRICATION",
                    "BUDI SANTOSO",
                    "Marketing",
                    "Mobile : 08212307 8763",
                ]
            ),
            "name": "ASR PT. AIR SURYA RADIATOR",
            "business": "ASR PT. AIR SURYA RADIATOR",
            "designation": "Marketing",
            "contact1": "08212307 8763",
        }
    )

    assert fields["business"] == "ASR PT. AIR SURYA RADIATOR"
    assert fields["name"] == "BUDI SANTOSO"


def test_deterministic_fallback_finds_name_below_top_brand_logo() -> None:
    # Regression: AALBORG card — a real card where OCR merged the top brand
    # across several lines and the person's name/designation sit well below
    # it. The old top-front-line heuristic picked the brand as the "name".
    fields = structure_card_text_deterministic(
        front_text="\n".join(
            [
                "AALBORG INDUSTRI",
                "INDONESIA",
                "NS Group",
                "Budhi Kristyo Wibowo",
                "Technical Director",
                "Email: budikris@aalborgindo.com",
                "Mobile: +62 811-2140-234",
                "PT. AALBORG INDUSTRI INDONESIA",
                "Jl. Rawa Sumur II, Blok III, Kav. CC 6-7",
                "Jakarta Timur, Indonesia 13930",
            ]
        ),
        candidate_hints=[
            {"field": "name", "value": "AALBORG INDUSTRI", "confidence": 0.9, "evidence": "top_front_line"},
            {"field": "company", "value": "INDONESIA", "confidence": 0.9, "evidence": "top_front_brand"},
            {"field": "designation", "value": "Technical Director", "confidence": 0.72, "evidence": "title_keyword"},
        ],
    )

    assert fields["name"] == "Budhi Kristyo Wibowo"
    assert fields["business"] == "PT. AALBORG INDUSTRI INDONESIA"
    assert fields["designation"] == "Technical Director"


def test_deterministic_fallback_rejects_field_label_words_as_name() -> None:
    # Regression: bare OCR label words ("Phone", "Email", "Address") sitting
    # on their own line, with the actual value on a different line, must
    # never become the extracted name.
    fields = structure_card_text_deterministic(
        front_text="\n".join(
            [
                "Office",
                "Phone",
                "M. Phone",
                "Email",
                "PT. ENERTECH ENGINEERING",
                "RICHARD ADOLF VHW",
                "Director",
                ": 021 2105 1245",
                ": richard.mytwins@gmail.com",
            ]
        ),
        candidate_hints=[
            {"field": "name", "value": "Email", "confidence": 0.9, "evidence": "top_front_line"},
            {"field": "company", "value": "Phone", "confidence": 0.72, "evidence": "company_keyword"},
            {"field": "designation", "value": "Director", "confidence": 0.72, "evidence": "title_keyword"},
        ],
    )

    assert fields["name"] == "RICHARD ADOLF VHW"
    assert fields["business"] == "PT. ENERTECH ENGINEERING"
    assert fields["name"] not in {"Phone", "Email", "Address", "Office"}


def test_deterministic_fallback_keeps_designation_hint_outside_narrow_keyword_list() -> None:
    # Regression: DESIGNATION_RE's keyword list is narrower than the
    # TITLE_KEYWORDS vocabulary that produces designation hints (e.g. CEO,
    # Founder, Partner aren't in DESIGNATION_RE). A hint that merely fails
    # that narrower keyword match must not be discarded.
    fields = structure_card_text_deterministic(
        front_text="ACME CORP\nJohn Doe\nCEO\nEmail: john@acme.com",
        candidate_hints=[
            {"field": "name", "value": "John Doe", "confidence": 0.8, "evidence": "top_front_line"},
            {"field": "designation", "value": "CEO", "confidence": 0.72, "evidence": "title_keyword"},
            {"field": "company", "value": "ACME CORP", "confidence": 0.82, "evidence": "top_front_company"},
        ],
    )

    assert fields["designation"] == "CEO"


def test_deterministic_fallback_does_not_use_back_side_branch_name_as_business() -> None:
    # Regression: _infer_business's whole-card scan must stay front-side
    # only — a back-side branch/office line must never win over (or replace
    # with nothing) a legitimate front-side company name.
    fields = structure_card_text_deterministic(
        front_text="xyz\nJohn Doe\nSales Manager",
        back_text="XYZ SERVICE CENTER BRANCH OFFICE",
    )

    assert fields["business"] != "XYZ SERVICE CENTER BRANCH OFFICE"


def test_deterministic_fallback_finds_legal_entity_past_wrapped_address() -> None:
    # Regression: a multi-line wrapped address pushed the real "PT. ..."
    # company line past the old first-8-lines cutoff in _infer_business.
    fields = structure_card_text_deterministic(
        front_text="\n".join(
            [
                "Sahat Siahaan",
                "Director",
                "0859-2532-5999",
                "info@mechaeltra.com",
                "www.mechaelta.com",
                "Jl. Pinang Raya Blok F16 No. 21,",
                "Kawasan Delta Silicon 3, Lippo",
                "Cikarang, Kabupaten Bekasi.",
                "Jawa Barat 17530",
                "PT. Mechatronic Transtec Indonesia",
            ]
        ),
    )

    assert fields["business"] == "PT. Mechatronic Transtec Indonesia"
    assert fields["name"] == "Sahat Siahaan"
