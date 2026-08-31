import json

import pytest

from yandex_boost.shows_create import load_created_skus, load_items


def test_load_created_skus_uses_only_created_rows(tmp_path):
    report_path = tmp_path / "shows_create_report.csv"
    report_path.write_text(
        "timestamp;sku;status\n"
        "01.08.2026 10:00:00;ABC#1;CREATED\n"
        "01.08.2026 10:01:00;XYZ#1;DRY_RUN\n"
        "01.08.2026 10:02:00;ERR#1;ERROR\n"
        "01.08.2026 10:03:00;  SPACE#1  ;CREATED\n",
        encoding="utf-8-sig",
    )

    assert load_created_skus(report_path) == {"ABC#1", "SPACE#1"}


def test_load_items_rejects_duplicate_sku(tmp_path):
    campaigns_path = tmp_path / "shows_campaigns.json"
    campaigns_path.write_text(
        json.dumps([
            {"sku": "ABC#1", "daily_limit": 300},
            {"sku": "ABC#1", "daily_limit": 500},
        ]),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="дубль SKU"):
        load_items(campaigns_path)
