import pytest

from yandex_boost.inventory import SalesInventoryRecord
from yandex_boost.product_cli import parse_skus, select_campaign_by_target


def test_parse_skus_accepts_single_comma_and_lines_without_changing_symbols():
    assert parse_skus(" A#1, B#2\nA#1 ") == ["A#1", "B#2"]


def test_select_campaign_by_sku_or_id_requires_exact_match():
    rows = [SalesInventoryRecord("1", "A", "A", "u"), SalesInventoryRecord("2", "B", "B", "u")]
    assert select_campaign_by_target(rows, "A") == rows[0]
    assert select_campaign_by_target(rows, "2") == rows[1]
    with pytest.raises(ValueError, match="не найден"):
        select_campaign_by_target(rows, "missing")
    with pytest.raises(ValueError, match="REVIEW"):
        select_campaign_by_target(rows + [SalesInventoryRecord("3", "A2", "A", "u")], "A")
