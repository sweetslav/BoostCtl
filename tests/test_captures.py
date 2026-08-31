import pytest

from yandex_boost.captures import (
    UnsupportedCaptureFormat,
    parse_sales_inventory_response,
    parse_shows_inventory_response,
    sanitize_capture,
)


def test_sanitize_capture_redacts_secret_values_without_removing_structure():
    capture = {
        "request": {
            "Authorization": "Bearer secret",
            "x-csrf-token": "csrf-secret",
            "Set-Cookie": "cookie-secret",
            "safe": "kept",
            "sku": "ABC#1",
            "skus": ["ABC#1", "XYZ#1"],
            "risk": "low",
            "task": "capture",
            "mask_name": "public",
        },
        "response": [{
            "session_id": "session-secret",
            "session_token": "session-token-secret",
            "access_token": "token-secret",
            "sku": "ABC#1",
        }],
        "sk": "session-key",
    }

    sanitized = sanitize_capture(capture)

    assert sanitized == {
        "request": {
            "Authorization": "<REDACTED>",
            "x-csrf-token": "<REDACTED>",
            "Set-Cookie": "<REDACTED>",
            "safe": "kept",
            "sku": "ABC#1",
            "skus": ["ABC#1", "XYZ#1"],
            "risk": "low",
            "task": "capture",
            "mask_name": "public",
        },
        "response": [{
            "session_id": "<REDACTED>",
            "session_token": "<REDACTED>",
            "access_token": "<REDACTED>",
            "sku": "ABC#1",
        }],
        "sk": "<REDACTED>",
    }
    assert capture["request"]["Authorization"] == "Bearer secret"
    assert capture["response"][0]["session_token"] == "session-token-secret"


@pytest.mark.parametrize(
    "parser",
    [parse_sales_inventory_response, parse_shows_inventory_response],
)
def test_inventory_parsers_reject_unconfirmed_capture_schema(parser):
    with pytest.raises(UnsupportedCaptureFormat, match="not confirmed"):
        parser({"campaigns": []})
