from __future__ import annotations

from dataclasses import dataclass

from .auth import safe_goto


ACTIVE_STATUSES = {"ACTIVE"}
INACTIVE_STATUSES = {"STOPPED", "CLOSED", "ARCHIVED"}


@dataclass(frozen=True, slots=True)
class ShowsInventoryRecord:
    campaign_id: str
    name: str
    sku: str | None
    raw_status: str | None
    daily_limit: int | None
    offer_id: str | None
    url: str
    identity_source: str


def shows_duplicate_disposition(records: list[ShowsInventoryRecord], sku: str) -> tuple[str, str | None]:
    matches = [record for record in records if record.sku == sku]
    if not matches:
        return "CREATE", None
    if len(matches) != 1:
        return "REVIEW", None
    status = matches[0].raw_status
    if status in ACTIVE_STATUSES:
        return "SKIP", status
    if status in INACTIVE_STATUSES:
        return "CREATE", status
    return "REVIEW", status


def shows_summary(records: list[ShowsInventoryRecord]) -> dict[str, int]:
    return {
        "total": len(records),
        "active": sum(record.raw_status in ACTIVE_STATUSES for record in records),
        "stopped_or_closed": sum(record.raw_status in INACTIVE_STATUSES for record in records),
        "unknown": sum(record.raw_status not in ACTIVE_STATUSES | INACTIVE_STATUSES for record in records),
    }


def fetch_shows_campaign_inventory(page, config) -> list[ShowsInventoryRecord]:
    url = f"https://partner.market.yandex.ru/business/{config.business_id}/shows-boost?sourceType={config.source_type}"
    safe_goto(page, url)
    snapshot = page.locator("a[href*='/shows-boost/']").evaluate_all(
        """links => links.map(link => { const row = link.closest('tr'); return {
            href: link.getAttribute('href') || '', name: (link.innerText || '').trim(),
            status: row && row.getAttribute('data-status'),
            sku: row && row.getAttribute('data-sku'), offerId: row && row.getAttribute('data-offer-id'),
            dailyLimit: row && row.getAttribute('data-daily-limit')
        }; })"""
    )
    records = []
    for row in snapshot:
        href = str(row.get("href", ""))
        campaign_id = href.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
        if not campaign_id.isdigit():
            continue
        daily_limit = row.get("dailyLimit")
        records.append(ShowsInventoryRecord(
            campaign_id, str(row.get("name", "")), str(row["sku"]).strip() if row.get("sku") else None,
            str(row["status"]).strip() if row.get("status") else None,
            int(daily_limit) if str(daily_limit or "").isdigit() else None,
            str(row["offerId"]).strip() if row.get("offerId") else None,
            href if href.startswith("http") else "https://partner.market.yandex.ru" + href, "DOM data-*",
        ))
    return sorted({record.campaign_id: record for record in records}.values(), key=lambda record: int(record.campaign_id))
