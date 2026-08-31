from yandex_boost.sales_inventory_discovery import build_discovery


def test_discovers_confirmed_paginated_sales_campaign_list():
    report = {"entries": [{"index": 1, "method": "POST", "pathname": "/monetization/api/resolve/", "query_params": [{"name": "r", "value": "salesBoostCampaign/listStrategies"}], "request_post_data": {"pageSize": 50}, "response_json": {"results": [{"salesCampaignId": 1, "name": "A", "status": "ACTIVE"}]}}]}
    result = build_discovery(report)
    assert result["summary"]["full_inventory_found"] is True
    assert result["summary"]["inventory_candidates"] == 1


def test_detail_statistics_and_generic_collection_are_not_inventory():
    report = {"entries": [
        {"index": 1, "pathname": "/salesBoostCampaign/detail", "response_json": {"page": {"salesCampaignInfo": {}}}},
        {"index": 2, "pathname": "/salesBoostCampaign/list", "request_post_data": {"widgetNames": ["statisticsWidget"]}, "response_json": {"items": [{"id": 1}]}},
        {"index": 3, "pathname": "/monetization/collection", "response_json": {"items": [{"id": 1}]}}]}
    result = build_discovery(report)
    assert result["summary"]["inventory_candidates"] == 0
    assert [entry["classification"] for entry in result["entries"]] == ["campaign_detail", "statistics", "unrelated"]
