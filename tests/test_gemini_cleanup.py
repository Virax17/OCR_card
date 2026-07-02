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
