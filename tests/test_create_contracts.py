from yandex_boost.client import YandexBoostClient
from yandex_boost.models import AppConfig
from yandex_boost.shows_client import YandexShowsBoostClient


class RecordingPage:
    def __init__(self):
        self.arguments = None

    def evaluate(self, _script, arguments):
        self.script = _script
        self.arguments = arguments
        return {"ok": True, "status": 200, "statusText": "OK", "text": '{"results":[{"data":{}}]}', "json": {"results": [{"data": {}}]}}


def test_sales_create_request_contract_is_preserved():
    page = RecordingPage()
    client = YandexBoostClient(page, AppConfig(business_id=7, source_type="BUSINESS", cost_model="CPA"), "secret")
    client.create_campaign(campaign_name="SKU | date", offer_id="offer-1", bid=15)
    assert "monetizationService:resolvePutSalesCampaign" in page.arguments["endpoint"]
    body = page.arguments["body"]["params"][0]["body"]
    assert body["name"] == "SKU | date"
    assert body["data"]["skus"] == [{"offerId": "offer-1", "fee": 15}]
    assert body["subsidyType"] == "FEE" and body["costModel"] == "CPA"
    assert body["isAutostrategy"] is False


def test_shows_create_request_contract_is_preserved():
    page = RecordingPage()
    client = YandexShowsBoostClient(page, AppConfig(business_id=7, source_type="BUSINESS"), "secret")
    client.create_campaign(campaign_name="SKU | date", offer_id="offer-1", daily_limit=300)
    assert "monetizationService:resolvePutSalesCampaignCpm" in page.arguments["endpoint"]
    body = page.arguments["body"]["params"][0]
    assert body["query"] == {"sourceId": 7, "sourceType": "BUSINESS"}
    assert body["body"]["data"]["skus"] == [{"offerId": "offer-1"}]
    assert body["body"]["dailyLimit"] == 300
    assert body["body"]["costModel"] == "CPM" and body["body"]["isAutostrategy"] is True


def test_sales_fee_update_request_contract_is_preserved():
    page = RecordingPage()
    client = YandexBoostClient(page, AppConfig(business_id=7, source_type="BUSINESS"), "secret")
    client.update_campaign_fee("123", 15.5)
    assert "method: \"PUT\"" in page.script
    assert "/api/web/monetization/putSalesCampaignFee" in page.arguments["endpoint"]
    assert "businessId=7" in page.arguments["endpoint"]
    assert "sourceType=BUSINESS" in page.arguments["endpoint"]
    assert "salesCampaignId=123" in page.arguments["endpoint"]
    assert page.arguments["fee"] == 15.5


def test_sales_delete_request_contract_is_preserved():
    page = RecordingPage()
    client = YandexBoostClient(page, AppConfig(business_id=7, source_type="BUSINESS"), "secret")
    client.delete_campaign("123")
    assert "method: \"DELETE\"" in page.script
    assert "/api/web/monetization/deleteSalesCampaignCpa" in page.arguments["endpoint"]
    assert "businessId=7" in page.arguments["endpoint"]
    assert "sourceType=BUSINESS" in page.arguments["endpoint"]
    assert "salesCampaignId=123" in page.arguments["endpoint"]
