from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .campaigns import CampaignRecord, CampaignSource, CampaignType

ROOT = Path.cwd()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--config", default="config.json")
    result.add_argument("--campaigns", default="data/shows_campaigns.json")
    result.add_argument("--limit", type=int, default=None)
    result.add_argument("--start", type=int, default=0)
    result.add_argument("--dry-run", action="store_true")
    return result


def load_items(path: Path) -> list[dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise SystemExit("shows_campaigns.json must contain a non-empty JSON array.")
    items: list[dict[str, object]] = []
    for index, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            raise SystemExit(f"Row {index}: expected an object.")
        sku = str(row.get("sku", "")).strip()
        try:
            daily_limit = int(row.get("daily_limit", 300))
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"Row {index}: invalid daily_limit.") from exc
        if not sku:
            raise SystemExit(f"Row {index}: empty SKU.")
        if daily_limit < 300:
            raise SystemExit(f"Row {index}: daily_limit is less than 300.")
        items.append({"sku": sku, "daily_limit": daily_limit})
    return items


def load_created_skus(path: Path) -> set[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as report_file:
            return {row["sku"].strip() for row in csv.DictReader(report_file, delimiter=";") if row.get("status") == "CREATED" and row.get("sku")}
    except OSError:
        return set()


def load_shows_report_observations(path: Path) -> list[CampaignRecord]:
    """Read local Shows operation history; it is not factual Yandex inventory."""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as report_file:
            records: list[CampaignRecord] = []
            for row in csv.DictReader(report_file, delimiter=";"):
                sku = (row.get("sku") or "").strip()
                if row.get("status") != "CREATED" or not sku:
                    continue
                try:
                    daily_limit = int(row["daily_limit"])
                except (KeyError, TypeError, ValueError):
                    daily_limit = None
                records.append(CampaignRecord(campaign_id=None, campaign_type=CampaignType.SHOWS, source=CampaignSource.LOCAL_REPORT, name=(row.get("campaign_name") or "").strip() or None, skus=(sku,), daily_limit=daily_limit))
            return records
    except OSError:
        return []


def main() -> int:
    from .shows_v2 import main as v2_main

    return v2_main()


if __name__ == "__main__":
    raise SystemExit(main())
