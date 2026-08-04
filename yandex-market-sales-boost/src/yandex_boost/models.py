from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CampaignInput:
    sku: str
    bid: float


@dataclass(frozen=True, slots=True)
class AppConfig:
    business_id: int = 950637
    source_type: str = "BUSINESS"
    cost_model: str = "CPA"
    offer_service: str = "MARKET"
    request_delay_seconds: float = 0.8
    max_retries: int = 3
