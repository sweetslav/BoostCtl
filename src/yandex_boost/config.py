from __future__ import annotations

import json
from pathlib import Path

from .models import AppConfig, CampaignInput


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        return AppConfig()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return AppConfig(**raw)


def load_campaigns(path: Path) -> list[CampaignInput]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError("Campaign file must contain a JSON array.")

    result: list[CampaignInput] = []
    seen: set[str] = set()

    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise TypeError(f"Row {index}: expected an object.")

        sku = str(item.get("sku", "")).strip()
        if not sku:
            raise ValueError(f"Row {index}: SKU is empty.")
        if sku in seen:
            raise ValueError(f"Row {index}: duplicate SKU {sku!r}.")

        try:
            bid = float(item["bid"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Row {index}: invalid bid.") from exc

        if not 0 < bid <= 100:
            raise ValueError(f"Row {index}: bid must be between 0 and 100.")

        seen.add(sku)
        result.append(CampaignInput(sku=sku, bid=bid))

    return result
