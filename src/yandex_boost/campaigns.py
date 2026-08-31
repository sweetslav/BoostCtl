from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable


class CampaignType(str, Enum):
    SALES = "SALES"
    SHOWS = "SHOWS"


class CampaignSource(str, Enum):
    WEB = "WEB"
    LOCAL_REPORT = "LOCAL_REPORT"


@dataclass(frozen=True, slots=True)
class CampaignRecord:
    campaign_id: str | None
    campaign_type: CampaignType
    source: CampaignSource
    name: str | None = None
    status: str | None = None
    skus: tuple[str, ...] = ()
    bid: float | None = None
    daily_limit: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    observed_at: datetime | None = None
    raw_status: str | None = None


class CampaignInventory:
    @staticmethod
    def combine(*record_sets: Iterable[CampaignRecord]) -> list[CampaignRecord]:
        return [record for record_set in record_sets for record in record_set]
