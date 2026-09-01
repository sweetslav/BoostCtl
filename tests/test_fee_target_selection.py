import pytest

from yandex_boost.cli import fee_apply_summary, select_delete_targets, select_fee_targets
from yandex_boost.inventory import SalesInventoryRecord


def test_campaign_id_selects_only_exact_target_and_limit_remains_compatible():
    rows = [SalesInventoryRecord("1", "A", "A", "u"), SalesInventoryRecord("2", "B", "B", "u")]
    assert select_fee_targets(rows, "2", 1) == [rows[1]]
    assert select_fee_targets(rows, "", 1) == [rows[0]]


def test_unknown_or_duplicate_campaign_id_is_rejected():
    rows = [SalesInventoryRecord("1", "A", "A", "u"), SalesInventoryRecord("1", "B", "B", "u")]
    with pytest.raises(ValueError):
        select_fee_targets(rows, "missing", 0)
    with pytest.raises(ValueError):
        select_fee_targets(rows, "1", 0)


def test_fee_summary_reports_success_and_not_verified_separately():
    result = type("Result", (), {"state": type("State", (), {"value": "SUCCEEDED"})(), "verification": "NOT_VERIFIED"})()
    assert fee_apply_summary([result]) == {"successful": 1, "failed": 0, "unknown": 0, "verified": 0, "not_verified": 1}


def test_delete_campaign_id_selects_only_exact_target():
    rows = [SalesInventoryRecord("1", "A", "A", "u"), SalesInventoryRecord("2", "B", "B", "u")]
    assert select_delete_targets(rows, "2", ["1"])[0] == [rows[1]]
    with pytest.raises(ValueError):
        select_delete_targets(rows, "missing", [])
