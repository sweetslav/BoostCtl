from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Page
from playwright.sync_api import Error as PlaywrightError

from .auth import safe_goto
from .campaigns import CampaignRecord, CampaignSource, CampaignType
from .models import AppConfig


def _progress(message: str) -> None:
    print(message, flush=True)


CAMPAIGN_NAME_RE = re.compile(r"^(?P<sku>.+?)\s*\|\s*\d{2}\.\d{2}\.\d{4}$")


@dataclass(frozen=True, slots=True)
class SalesInventoryRecord:
    campaign_id: str
    campaign_name: str
    sku: str
    url: str


def extract_sku_from_campaign_name(name: str) -> str:
    match = CAMPAIGN_NAME_RE.match(name.strip())
    return match.group("sku").strip() if match else ""


def _campaign_url(config: AppConfig) -> str:
    return (
        "https://partner.market.yandex.ru/business/"
        f"{config.business_id}/sales-boost?sourceType={config.source_type}"
    )


def _collect_visible(
    page: Page,
    config: AppConfig,
    records: dict[str, SalesInventoryRecord],
) -> int:
    added = 0
    prefix = f"/business/{config.business_id}/sales-boost/"
    snapshot = None
    for attempt in range(3):
        try:
            snapshot = page.locator("a[href*='/sales-boost/']").evaluate_all(
                "links => links.map(link => ({href: link.getAttribute('href') || '', text: (link.innerText || '').trim()}))"
            )
            break
        except PlaywrightError as exc:
            if attempt == 2:
                raise RuntimeError("Campaign inventory DOM remained unstable after 3 snapshots.") from exc
            page.wait_for_timeout(200)
    assert snapshot is not None

    for link in snapshot:
        href = str(link.get("href", ""))
        text = str(link.get("text", "")).strip()
        if not href or not text or prefix not in href:
            continue

        clean_href = href.split("?", 1)[0].rstrip("/")
        campaign_id = clean_href.rsplit("/", 1)[-1]
        if not campaign_id.isdigit() or campaign_id in records:
            continue

        full_url = href if href.startswith("http") else "https://partner.market.yandex.ru" + href
        records[campaign_id] = SalesInventoryRecord(
            campaign_id=campaign_id,
            campaign_name=text,
            sku=extract_sku_from_campaign_name(text),
            url=full_url,
        )
        added += 1

    return added


def _find_next_button(page: Page):
    patterns = [re.compile("Следующ", re.I), re.compile("Впер[её]д", re.I)]
    for pattern in patterns:
        locator = page.get_by_role("button", name=pattern)
        if locator.count() and locator.first.is_visible():
            return locator.first

    for selector in ["button[aria-label*='next' i]", "a[aria-label*='next' i]"]:
        locator = page.locator(selector)
        if locator.count() and locator.first.is_visible():
            return locator.first
    return None


def fetch_campaign_inventory(page: Page, config: AppConfig) -> list[SalesInventoryRecord]:
    safe_goto(page, _campaign_url(config))
    records: dict[str, SalesInventoryRecord] = {}
    page_number = 1

    while page_number <= 20:
        stable_rounds = 0
        previous_count = -1

        for _ in range(80):
            _collect_visible(page, config, records)
            current_count = len(records)
            if current_count == previous_count:
                stable_rounds += 1
            else:
                stable_rounds = 0
                previous_count = current_count

            if stable_rounds >= 5:
                break

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(400)

        next_button = _find_next_button(page)
        if next_button is None:
            break

        try:
            if next_button.is_disabled():
                break
        except AttributeError:
            pass

        before_url = page.url
        next_button.click(force=True)
        page.wait_for_timeout(1_200)
        page.evaluate("window.scrollTo(0, 0)")

        if page.url == before_url and _collect_visible(page, config, records) == 0:
            break
        page_number += 1

    _collect_visible(page, config, records)
    return sorted(records.values(), key=lambda row: int(row.campaign_id))


def inventory_skus(records: list[SalesInventoryRecord]) -> set[str]:
    return {record.sku for record in records if record.sku}


def duplicate_skus(records: list[SalesInventoryRecord]) -> dict[str, list[SalesInventoryRecord]]:
    grouped: dict[str, list[SalesInventoryRecord]] = {}
    for record in records:
        if record.sku:
            grouped.setdefault(record.sku, []).append(record)
    return {sku: rows for sku, rows in grouped.items() if len(rows) > 1}


def write_inventory_csv(records: list[SalesInventoryRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["campaign_id", "campaign_name", "sku", "url"],
            delimiter=";",
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "campaign_id": record.campaign_id,
                    "campaign_name": record.campaign_name,
                    "sku": record.sku,
                    "url": record.url,
                }
            )


def sales_inventory_to_campaign_records(
    records: list[SalesInventoryRecord],
    *,
    observed_at: datetime | None = None,
) -> list[CampaignRecord]:
    """Normalize legacy read-only Sales WEB/UI observations.

    SKU is derived from the campaign name. This fallback is not factual lifecycle
    inventory, so unavailable status, bid, and dates remain unset.
    """
    return [
        CampaignRecord(
            campaign_id=record.campaign_id or None,
            campaign_type=CampaignType.SALES,
            source=CampaignSource.WEB,
            name=record.campaign_name or None,
            skus=(record.sku,) if record.sku else (),
            observed_at=observed_at,
        )
        for record in records
    ]
