import pandas as pd
import pytest
import requests

from data_pipeline import DataValidationError, load_data
from gsheet_loader import extract_gid_from_url, extract_sheet_id, get_sheet_csv_url, load_gsheet_as_csv


SHEET_URL = "https://docs.google.com/spreadsheets/d/abc_123/edit#gid=42"


class StreamResponse:
    def __init__(self, chunks, content_type="text/csv", error=None):
        self.chunks = chunks
        self.headers = {"content-type": content_type}
        self.error = error
        self.closed = False
        self.read_chunks = 0

    def raise_for_status(self):
        if self.error:
            raise self.error

    @property
    def text(self):
        pytest.fail("Google Sheet downloads must be streamed")

    def iter_content(self, chunk_size):
        assert chunk_size <= 64 * 1024
        for chunk in self.chunks:
            self.read_chunks += 1
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    def close(self):
        self.closed = True


def mock_download(monkeypatch, response):
    def get(url, **kwargs):
        assert url == get_sheet_csv_url("abc_123", "42")
        assert kwargs == {"timeout": 30, "stream": True}
        return response

    monkeypatch.setattr("gsheet_loader.requests.get", get)


def test_google_sheet_identifiers_and_gid_are_parsed():
    url = "https://docs.google.com/spreadsheets/d/abc_123/edit#gid=42"
    assert extract_sheet_id(url) == "abc_123"
    assert extract_gid_from_url(url) == "42"
    assert get_sheet_csv_url("abc_123", "42").endswith("export?format=csv&gid=42")


def test_plain_sheet_ids_are_supported():
    assert extract_sheet_id("abc-123") == "abc-123"


def test_google_sheet_stream_shares_csv_inference_and_closes_response(monkeypatch):
    response = StreamResponse([b"amount,name\n9007199254740993,", b"Acme\n,Beta\n"])
    mock_download(monkeypatch, response)
    frame = load_gsheet_as_csv(SHEET_URL)
    assert pd.api.types.is_integer_dtype(frame["amount"])
    assert int(frame.loc[0, "amount"]) == 9007199254740993
    assert pd.isna(frame.loc[1, "amount"])
    assert response.closed


@pytest.mark.parametrize("content,message", [
    (b"sales,sales\n10,20\n", "Duplicate column"),
    (b"sales,name\n10,Acme,hidden\n", "3 fields"),
    (b"sales,\n10,Acme\n", "has no name"),
    (b"sales\n\xff\n", "UTF-8"),
])
def test_google_sheet_validates_raw_records_before_pandas(monkeypatch, content, message):
    response = StreamResponse([content])
    mock_download(monkeypatch, response)
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: pytest.fail("Invalid CSV reached pandas"))
    with pytest.raises(DataValidationError, match=message):
        load_data(SHEET_URL)
    assert response.closed


def test_google_sheet_byte_limit_stops_streaming_and_closes_response(monkeypatch):
    response = StreamResponse([b"name\n", b"Acme\n", b"must not read"])
    mock_download(monkeypatch, response)
    with pytest.raises(DataValidationError, match="safe limit"):
        load_data(SHEET_URL, max_bytes=5)
    assert response.read_chunks == 2
    assert response.closed


def test_google_sheet_row_limit_is_forwarded_before_dataframe_allocation(monkeypatch):
    response = StreamResponse([b"name\nAcme\nBeta\n"])
    mock_download(monkeypatch, response)
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: pytest.fail("Oversized CSV reached pandas"))
    with pytest.raises(DataValidationError, match="safe limit of 1 rows"):
        load_data(SHEET_URL, max_rows=1)
    assert response.closed


@pytest.mark.parametrize("response,message", [
    (StreamResponse([], content_type="Text/HTML; charset=UTF-8"), "publicly readable"),
    (StreamResponse([], error=requests.HTTPError("403 Forbidden")), "Error loading Google Sheet"),
    (StreamResponse([requests.Timeout()]), "Timeout while loading Google Sheet"),
    (StreamResponse([requests.ConnectionError("disconnected")]), "Error loading Google Sheet"),
])
def test_google_sheet_closes_response_after_failed_download(monkeypatch, response, message):
    mock_download(monkeypatch, response)
    with pytest.raises(ValueError, match=message):
        load_gsheet_as_csv(SHEET_URL)
    assert response.closed


def test_google_sheet_normalizes_connection_errors_before_response_exists(monkeypatch):
    def unavailable(*args, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr("gsheet_loader.requests.get", unavailable)
    with pytest.raises(ValueError, match="Timeout while loading Google Sheet"):
        load_gsheet_as_csv(SHEET_URL)
