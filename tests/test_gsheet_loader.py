from gsheet_loader import extract_gid_from_url, extract_sheet_id, get_sheet_csv_url


def test_google_sheet_identifiers_and_gid_are_parsed():
    url = "https://docs.google.com/spreadsheets/d/abc_123/edit#gid=42"
    assert extract_sheet_id(url) == "abc_123"
    assert extract_gid_from_url(url) == "42"
    assert get_sheet_csv_url("abc_123", "42").endswith("export?format=csv&gid=42")


def test_plain_sheet_ids_are_supported():
    assert extract_sheet_id("abc-123") == "abc-123"
