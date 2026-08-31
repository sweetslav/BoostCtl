from __future__ import annotations

from .campaigns import CampaignRecord

REDACTED = "<REDACTED>"
_SECRET_KEY_PARTS = ("authorization", "cookie", "csrf", "session", "token")


class UnsupportedCaptureFormat(ValueError):
    pass


def sanitize_capture(value: object) -> object:
    """Copy JSON-like capture data while redacting values of secret-like keys."""
    if isinstance(value, dict):
        return {
            key: REDACTED if _is_secret_key(key) else sanitize_capture(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_capture(item) for item in value]
    return value


def contains_unredacted_secret_values(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            (item != REDACTED if _is_secret_key(key) else contains_unredacted_secret_values(item))
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(contains_unredacted_secret_values(item) for item in value)
    return False


def _is_secret_key(key: object) -> bool:
    normalized = str(key).casefold()
    return normalized == "sk" or any(part in normalized for part in _SECRET_KEY_PARTS)


def parse_sales_inventory_response(response: object) -> list[CampaignRecord]:
    raise UnsupportedCaptureFormat("Sales factual inventory capture format is not confirmed.")


def parse_shows_inventory_response(response: object) -> list[CampaignRecord]:
    raise UnsupportedCaptureFormat("Shows factual inventory capture format is not confirmed.")
