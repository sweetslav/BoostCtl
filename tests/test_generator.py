import pytest

from yandex_boost.generator import InputFormatError, parse_campaign_input


def test_parse_semicolon_input():
    rows = parse_campaign_input("ABC#1;5\nXYZ#1;7.5\n")
    assert rows == [
        {"sku": "ABC#1", "bid": 5.0},
        {"sku": "XYZ#1", "bid": 7.5},
    ]


def test_parse_decimal_comma():
    rows = parse_campaign_input("2529892/9П-7,5#1;7,5")
    assert rows[0]["sku"] == "2529892/9П-7,5#1"
    assert rows[0]["bid"] == 7.5


def test_parse_tab_from_excel():
    rows = parse_campaign_input("ABC#1\t5\nXYZ#1\t10")
    assert len(rows) == 2


def test_duplicate_sku_is_blocked():
    with pytest.raises(InputFormatError, match="дубль SKU"):
        parse_campaign_input("ABC#1;5\nABC#1;6")


def test_invalid_bid_is_blocked():
    with pytest.raises(InputFormatError, match="ставка"):
        parse_campaign_input("ABC#1;abc")
