# ruff: noqa: E701, E702
import pytest
from playwright.sync_api import Error as PlaywrightError

from yandex_boost.inventory import SalesInventoryRecord, _collect_visible, duplicate_skus, extract_sku_from_campaign_name
from yandex_boost.models import AppConfig


class SnapshotLocator:
    def __init__(self, values): self.values = values; self.calls = 0
    def evaluate_all(self, _):
        value = self.values[self.calls]; self.calls += 1
        if isinstance(value, Exception): raise value
        return value


class SnapshotPage:
    def __init__(self, values): self.snapshot = SnapshotLocator(values); self.waits = 0
    def locator(self, _): return self.snapshot
    def wait_for_timeout(self, _): self.waits += 1


def test_extract_sku_from_campaign_name():
    assert extract_sku_from_campaign_name("2020488/1#1 | 07.08.2026") == "2020488/1#1"


def test_extract_sku_returns_empty_for_unknown_format():
    assert extract_sku_from_campaign_name("ручная кампания") == ""


def test_extract_sku_accepts_spaces_around_separator():
    assert extract_sku_from_campaign_name("  ABC#1   |   07.08.2026  ") == "ABC#1"


def test_duplicate_skus():
    rows = [
        SalesInventoryRecord("1", "ABC#1 | 01.08.2026", "ABC#1", "u1"),
        SalesInventoryRecord("2", "ABC#1 | 07.08.2026", "ABC#1", "u2"),
        SalesInventoryRecord("3", "XYZ#1 | 07.08.2026", "XYZ#1", "u3"),
    ]
    duplicates = duplicate_skus(rows)
    assert set(duplicates) == {"ABC#1"}
    assert len(duplicates["ABC#1"]) == 2


def test_duplicate_skus_ignores_records_without_recognized_sku():
    rows = [
        SalesInventoryRecord("1", "ручная кампания", "", "u1"),
        SalesInventoryRecord("2", "другая ручная кампания", "", "u2"),
    ]

    assert duplicate_skus(rows) == {}


def test_collect_visible_retries_atomic_snapshot_without_duplicates():
    page = SnapshotPage([PlaywrightError("detached"), [{"href": "/business/1/sales-boost/12", "text": "A | 01.01.2026"}]])
    records = {}
    assert _collect_visible(page, AppConfig(business_id=1), records) == 1
    assert _collect_visible(SnapshotPage([[{"href": "/business/1/sales-boost/12", "text": "A | 01.01.2026"}]]), AppConfig(business_id=1), records) == 0


def test_collect_visible_fails_clearly_after_persistent_snapshot_race():
    with pytest.raises(RuntimeError, match="DOM remained unstable"):
        _collect_visible(SnapshotPage([PlaywrightError("x")] * 3), AppConfig(), {})
