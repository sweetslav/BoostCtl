from datetime import datetime, timezone

import pytest

from yandex_boost.campaigns import CampaignInventory, CampaignRecord, CampaignSource, CampaignType


def test_campaign_record_keeps_only_observed_values():
    observed_at = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)

    record = CampaignRecord(
        campaign_id="123",
        campaign_type=CampaignType.SALES,
        source=CampaignSource.WEB,
        name="ABC#1 | 31.08.2026",
        skus=("ABC#1", "XYZ#1"),
        observed_at=observed_at,
    )

    assert record.campaign_id == "123"
    assert record.skus == ("ABC#1", "XYZ#1")
    assert record.status is None
    assert record.bid is None
    assert record.daily_limit is None
    assert record.created_at is None
    assert record.updated_at is None
    assert record.raw_status is None

    with pytest.raises(AttributeError):
        record.name = "changed"


def test_campaign_inventory_combines_records_without_deduplication():
    sales_record = CampaignRecord(
        campaign_id="123",
        campaign_type=CampaignType.SALES,
        source=CampaignSource.WEB,
        skus=("ABC#1",),
    )
    shows_record = CampaignRecord(
        campaign_id=None,
        campaign_type=CampaignType.SHOWS,
        source=CampaignSource.LOCAL_REPORT,
        skus=("ABC#1",),
    )

    inventory = CampaignInventory.combine([sales_record], [shows_record])

    assert inventory == [sales_record, shows_record]
