import json

import pytest

from yandex_boost.config import load_campaigns


def test_load_campaigns(tmp_path):
    path = tmp_path / "campaigns.json"
    path.write_text(
        json.dumps([{"sku": "ABC#1", "bid": 18}]),
        encoding="utf-8",
    )
    campaigns = load_campaigns(path)
    assert campaigns[0].sku == "ABC#1"
    assert campaigns[0].bid == 18


def test_duplicate_sku_rejected(tmp_path):
    path = tmp_path / "campaigns.json"
    path.write_text(
        json.dumps([
            {"sku": "ABC#1", "bid": 18},
            {"sku": "ABC#1", "bid": 19},
        ]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate SKU"):
        load_campaigns(path)
