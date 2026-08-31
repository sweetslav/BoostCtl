from __future__ import annotations

import json
import time
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from .models import AppConfig


class AmbiguousMutationResult(RuntimeError):
    """A create request may have reached Yandex; verification is required."""


class RemoteRejectedError(RuntimeError):
    """Yandex returned a definite rejection; the create request did not succeed."""


class TransportError(RuntimeError):
    """The request outcome could not be established locally."""


class YandexBoostClient:
    def __init__(self, page: Page, config: AppConfig, sk: str) -> None:
        self.page = page
        self.config = config
        self.sk = sk

    @property
    def edit_path(self) -> str:
        return (
            f"/business/{self.config.business_id}/sales-boost/draft/edit"
            f"?sourceType={self.config.source_type}"
            f"&costModel={self.config.cost_model}"
        )

    def _fetch(self, endpoint: str, body: dict[str, Any], *, retry: bool = True) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(1, (self.config.max_retries if retry else 1) + 1):
            try:
                result = self.page.evaluate(
                    """async ({endpoint, sk, body}) => {
                        const response = await fetch(endpoint, {
                            method: "POST",
                            credentials: "include",
                            headers: {
                                "accept": "*/*",
                                "content-type": "application/json",
                                "x-requested-with": "XMLHttpRequest",
                                "x-market-apphost-target": "WEB",
                                "x-market-core-service": "<UNKNOWN>",
                                "x-market-page-id": "sales-boost-campaign-edit",
                                "sk": sk
                            },
                            body: JSON.stringify(body)
                        });
                        const text = await response.text();
                        let json = null;
                        try { json = JSON.parse(text); } catch (_) {}
                        return {
                            ok: response.ok,
                            status: response.status,
                            statusText: response.statusText,
                            text,
                            json
                        };
                    }""",
                    {"endpoint": endpoint, "sk": self.sk, "body": body},
                )

                if not result["ok"]:
                    raise RemoteRejectedError(
                        f"HTTP {result['status']} {result['statusText']}: "
                        f"{result['text'][:1000]}"
                    )
                if result["json"] is None:
                    raise RemoteRejectedError(
                        f"Server returned non-JSON: {result['text'][:1000]}"
                    )

                self._raise_api_error(result["json"])
                return result["json"]

            except PlaywrightError as exc:
                last_error = TransportError(str(exc))
                if attempt >= (self.config.max_retries if retry else 1):
                    break
                time.sleep(min(2 ** attempt, 8))
            except RemoteRejectedError:
                raise
            except RuntimeError as exc:
                last_error = TransportError(str(exc))
                if attempt >= (self.config.max_retries if retry else 1):
                    break
                time.sleep(min(2 ** attempt, 8))

        assert last_error is not None
        raise last_error

    @staticmethod
    def _raise_api_error(payload: Any) -> None:
        if not isinstance(payload, dict):
            raise RemoteRejectedError("API response is not a JSON object.")

        results = payload.get("results")
        if not isinstance(results, list) or not results:
            raise RemoteRejectedError("API response has no results.")

        for result in results:
            if not isinstance(result, dict):
                continue
            error = result.get("error")
            if error:
                raise RemoteRejectedError(json.dumps(error, ensure_ascii=False))
            data = result.get("data")
            if isinstance(data, dict) and data.get("error"):
                raise RemoteRejectedError(json.dumps(data["error"], ensure_ascii=False))

    def update_campaign_fee(self, campaign_id: str, fee: float) -> None:
        endpoint = (
            "https://partner.market.yandex.ru/api/web/monetization/"
            "putSalesCampaignFee"
            f"?businessId={self.config.business_id}"
            f"&sourceType={self.config.source_type}"
            f"&salesCampaignId={campaign_id}"
        )
        result = self.page.evaluate(
            """async ({endpoint, sk, fee}) => {
                const response = await fetch(endpoint, {
                    method: "PUT",
                    credentials: "include",
                    headers: {
                        "accept": "*/*",
                        "content-type": "application/json",
                        "x-requested-with": "XMLHttpRequest",
                        "sk": sk
                    },
                    body: JSON.stringify({fee})
                });
                return {ok: response.ok, status: response.status,
                        statusText: response.statusText, text: await response.text()};
            }""",
            {"endpoint": endpoint, "sk": self.sk, "fee": fee},
        )
        if not result["ok"]:
            raise RuntimeError(
                f"UPDATE fee campaign {campaign_id}: HTTP {result['status']} "
                f"{result['statusText']}: {result['text'][:1000]}"
            )

    def delete_campaign(self, campaign_id: str) -> None:
        endpoint = (
            "https://partner.market.yandex.ru/api/web/monetization/"
            "deleteSalesCampaignCpa"
            f"?businessId={self.config.business_id}"
            f"&sourceType={self.config.source_type}"
            f"&salesCampaignId={campaign_id}"
        )

        result = self.page.evaluate(
            """async ({endpoint, sk}) => {
                const response = await fetch(endpoint, {
                    method: "DELETE",
                    credentials: "include",
                    headers: {
                        "accept": "*/*",
                        "x-requested-with": "XMLHttpRequest",
                        "sk": sk
                    }
                });
                const text = await response.text();
                return {
                    ok: response.ok,
                    status: response.status,
                    statusText: response.statusText,
                    text
                };
            }""",
            {"endpoint": endpoint, "sk": self.sk},
        )

        if not result["ok"]:
            raise RuntimeError(
                f"DELETE campaign {campaign_id}: "
                f"HTTP {result['status']} {result['statusText']}: "
                f"{result['text'][:1000]}"
            )

    def find_offer_id(self, sku: str) -> str:
        endpoint = (
            "https://partner.market.yandex.ru/monetization/api/resolve/"
            "?r=dataCampWhite/resolveOffersForModels:resolveOffersForModels"
        )
        body = {
            "params": [
                {
                    "businessId": self.config.business_id,
                    "pageSize": 25,
                    "categoryIds": [],
                    "brandNames": [],
                    "text": sku,
                    "searchAllOffers": True,
                    "withPrices": True,
                    "withStocks": False,
                    "withDisabledForPromo": False,
                }
            ],
            "path": self.edit_path,
        }
        payload = self._fetch(endpoint, body)

        try:
            inner = payload["results"][0]["data"]["data"]
            offers = inner["entities"]["dataCampOffers"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Unexpected offer-search response structure.") from exc

        exact = [
            offer_id
            for offer_id, offer in offers.items()
            if isinstance(offer, dict) and offer.get("article") == sku
        ]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            raise RuntimeError(f"Several exact offers found for SKU {sku}: {exact}")
        raise RuntimeError(f"Exact offer was not found for SKU {sku}")

    def create_campaign(
        self,
        *,
        campaign_name: str,
        offer_id: str,
        bid: float,
    ) -> dict[str, Any]:
        endpoint = (
            "https://partner.market.yandex.ru/monetization/api/resolve/"
            "?r=monetizationService:resolvePutSalesCampaign"
        )
        body = {
            "params": [
                {
                    "query": {
                        "sourceId": self.config.business_id,
                        "sourceType": self.config.source_type,
                    },
                    "body": {
                        "name": campaign_name,
                        "data": {
                            "type": "SKU",
                            "skus": [{"offerId": offer_id, "fee": bid}],
                        },
                        "subsidyType": "FEE",
                        "partners": [],
                        "costModel": self.config.cost_model,
                        "isAutostrategy": False,
                        "offerService": self.config.offer_service,
                        "lavkaShowPages": [],
                    },
                }
            ],
            "path": self.edit_path,
        }
        try:
            return self._fetch(endpoint, body, retry=False)
        except TransportError as exc:
            raise AmbiguousMutationResult("Sales create result is unknown; verify before retrying.") from exc
