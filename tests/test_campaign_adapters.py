from datetime import datetime, timezone

from yandex_boost.campaigns import CampaignSource, CampaignType
from yandex_boost.inventory import SalesInventoryRecord, sales_inventory_to_campaign_records
from yandex_boost.shows_create import load_shows_report_observations


def test_sales_inventory_records_convert_without_unobserved_fields():
    observed_at = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    sales_records = [
        SalesInventoryRecord("123", "ABC#1 | 31.08.2026", "ABC#1", "https://example.test/123"),
        SalesInventoryRecord("124", "ручная кампания", "", "https://example.test/124"),
    ]

    records = sales_inventory_to_campaign_records(sales_records, observed_at=observed_at)

    assert [(record.campaign_id, record.skus) for record in records] == [
        ("123", ("ABC#1",)),
        ("124", ()),
    ]
    assert all(record.campaign_type is CampaignType.SALES for record in records)
    assert all(record.source is CampaignSource.WEB for record in records)
    assert all(record.status is None for record in records)
    assert all(record.bid is None for record in records)
    assert all(record.created_at is None for record in records)
    assert all(record.observed_at == observed_at for record in records)


def test_shows_report_observations_keep_only_usable_created_rows(tmp_path):
    report_path = tmp_path / "shows_create_report.csv"
    report_path.write_text(
        "timestamp;sku;daily_limit;campaign_name;status\n"
        "31.08.2026 12:00:00;ABC#1;300;ABC#1 | 31.08.2026;CREATED\n"
        "31.08.2026 12:01:00;BAD#1;not-a-number;BAD#1 | 31.08.2026;CREATED\n"
        "31.08.2026 12:02:00;;300;missing SKU;CREATED\n"
        "31.08.2026 12:03:00;DRY#1;300;DRY#1 | 31.08.2026;DRY_RUN\n",
        encoding="utf-8-sig",
    )

    records = load_shows_report_observations(report_path)

    assert [(record.name, record.skus, record.daily_limit) for record in records] == [
        ("ABC#1 | 31.08.2026", ("ABC#1",), 300),
        ("BAD#1 | 31.08.2026", ("BAD#1",), None),
    ]
    assert all(record.campaign_id is None for record in records)
    assert all(record.campaign_type is CampaignType.SHOWS for record in records)
    assert all(record.source is CampaignSource.LOCAL_REPORT for record in records)
    assert all(record.status is None for record in records)
    assert all(record.raw_status is None for record in records)
