from yandex_boost.inventory import CampaignRecord, duplicate_skus, extract_sku_from_campaign_name


def test_extract_sku_from_campaign_name():
    assert extract_sku_from_campaign_name("2020488/1#1 | 07.08.2026") == "2020488/1#1"


def test_extract_sku_returns_empty_for_unknown_format():
    assert extract_sku_from_campaign_name("ручная кампания") == ""


def test_duplicate_skus():
    rows = [
        CampaignRecord("1", "ABC#1 | 01.08.2026", "ABC#1", "u1"),
        CampaignRecord("2", "ABC#1 | 07.08.2026", "ABC#1", "u2"),
        CampaignRecord("3", "XYZ#1 | 07.08.2026", "XYZ#1", "u3"),
    ]
    duplicates = duplicate_skus(rows)
    assert set(duplicates) == {"ABC#1"}
    assert len(duplicates["ABC#1"]) == 2
