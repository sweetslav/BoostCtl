import pytest

from yandex_boost.client import AmbiguousMutationResult, YandexBoostClient
from yandex_boost.models import AppConfig


class FailingPage:
    def __init__(self): self.calls = 0
    def evaluate(self, *_):
        self.calls += 1
        raise RuntimeError("transport lost")


def test_sales_create_does_not_retry_ambiguous_transport_failure():
    page = FailingPage()
    client = YandexBoostClient(page, AppConfig(max_retries=3), "secret")
    with pytest.raises(AmbiguousMutationResult):
        client.create_campaign(campaign_name="A", offer_id="offer", bid=15)
    assert page.calls == 1
