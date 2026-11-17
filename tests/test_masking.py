"""Readable copies never carry raw personal data: identifiers and the names printed beside them are masked."""
from libertas.interpres.india import mask_pii

SAMPLE = """sample:
name | mobile | aadhaar | city
Saranya P. | +91 58697 99322 | 1535 2118 6886 | Chennai
Senthil R. | +91 55003 68614 | 1072 6700 1024 | Tirunelveli
price $4500 btc only"""


def test_names_beside_identifiers_are_masked():
    out = mask_pii(SAMPLE)
    assert "Saranya" not in out and "Senthil" not in out
    assert "S****** P. | +91 XXXXXX9322 | XXXX XXXX 6886 | Chennai" in out
    assert "name | mobile | aadhaar | city" in out  # the header row is kept
    assert "price $4500 btc only" in out  # prose without identifiers is untouched


def test_organisations_and_prose_are_not_masked():
    text = "Marutham Co-operative Bank customer database, 50 lakh records. Contact Session ID 05ea1cea"
    assert mask_pii(text) == text


def test_name_column_found_by_header_and_email_rows():
    text = "id, email, full name\n17, ravi.k@example.in, Ravi Kumar"
    out = mask_pii(text)
    assert "Ravi Kumar" not in out and "R*** K****" in out and "r***@example.in" in out
