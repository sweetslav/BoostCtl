import json

import pytest

from yandex_boost.capture_cli import CaptureIngestionError, ingest_capture, write_sanitized_capture
from yandex_boost.captures import contains_unredacted_secret_values


def test_ingest_capture_writes_sanitized_json_without_changing_input(tmp_path):
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "fixture.json"
    capture = {
        "sku": "ABC#1",
        "skus": ["ABC#1", "XYZ#1"],
        "campaignId": "123",
        "businessId": "456",
        "sk": "secret",
        "nested": [{"session_token": "nested-secret"}],
        "note": "ordinary token-like text",
    }
    input_path.write_text(json.dumps(capture), encoding="utf-8")

    ingest_capture(input_path, output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "sku": "ABC#1",
        "skus": ["ABC#1", "XYZ#1"],
        "campaignId": "123",
        "businessId": "456",
        "sk": "<REDACTED>",
        "nested": [{"session_token": "<REDACTED>"}],
        "note": "ordinary token-like text",
    }
    assert json.loads(input_path.read_text(encoding="utf-8")) == capture


def test_ingest_capture_refuses_existing_output_without_force(tmp_path):
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "fixture.json"
    input_path.write_text('{"sk": "secret"}', encoding="utf-8")
    output_path.write_text('{"existing": true}', encoding="utf-8")

    with pytest.raises(CaptureIngestionError, match="already exists"):
        ingest_capture(input_path, output_path)

    assert output_path.read_text(encoding="utf-8") == '{"existing": true}'


def test_ingest_capture_force_overwrites_with_sanitized_content(tmp_path):
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "fixture.json"
    input_path.write_text('{"access_token": "secret", "sku": "ABC#1"}', encoding="utf-8")
    output_path.write_text('{"existing": true}', encoding="utf-8")

    ingest_capture(input_path, output_path, force=True)

    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "access_token": "<REDACTED>",
        "sku": "ABC#1",
    }


def test_ingest_capture_rejects_invalid_json_without_creating_output(tmp_path):
    input_path = tmp_path / "raw.json"
    output_path = tmp_path / "fixture.json"
    input_path.write_text("not json", encoding="utf-8")

    with pytest.raises(CaptureIngestionError, match="Invalid JSON"):
        ingest_capture(input_path, output_path)

    assert not output_path.exists()


def test_ingest_capture_rejects_unsanitized_fixture_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_path = tmp_path / "tests" / "fixtures" / "yandex_captures" / "raw.json"
    output_path = tmp_path / "output.json"
    input_path.parent.mkdir(parents=True)
    input_path.write_text('{"cookie": "secret"}', encoding="utf-8")

    with pytest.raises(CaptureIngestionError, match="fixture"):
        ingest_capture(input_path, output_path)

    assert not output_path.exists()


def test_secret_scan_checks_only_values_under_secret_keys():
    assert not contains_unredacted_secret_values({"sku": "ABC#1", "note": "token-looking text"})
    assert contains_unredacted_secret_values({"nested": [{"session": "secret"}]})


def test_write_sanitized_capture_refuses_unredacted_secret_value(tmp_path):
    output_path = tmp_path / "fixture.json"

    with pytest.raises(CaptureIngestionError, match="Internal error"):
        write_sanitized_capture({"sk": "secret"}, output_path)

    assert not output_path.exists()
