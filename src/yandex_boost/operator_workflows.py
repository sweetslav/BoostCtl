from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .create_services import SalesService
from .inventory import fetch_campaign_inventory, inventory_skus
from .shows_inventory import fetch_shows_campaign_inventory
from .v2_workflows import plan_sales_create, start_journal


def sales_create_preview(page: Any, config: Any, client: Any, items: list[dict[str, object]], journal_path: Path):
    inventory = fetch_campaign_inventory(page, config)
    return plan_sales_create(client, journal_path, items, inventory_skus(inventory), datetime.now().astimezone().strftime("%d.%m.%Y"))


def shows_create_preview(page: Any, config: Any, client: Any, items: list[dict[str, object]], journal_path: Path):
    records = fetch_shows_campaign_inventory(page, config)
    journal, run_id = start_journal(journal_path, "shows.create", items)
    from .create_services import ShowsService
    plan = ShowsService(journal, client).plan_create_from_inventory(
        items, records, run_id=run_id, date=datetime.now().astimezone().strftime("%d.%m.%Y"),
    )
    return journal, plan, records


def fee_preview(page: Any, config: Any, client: Any, target: Any, fee: float, journal_path: Path):
    inventory = fetch_campaign_inventory(page, config)
    items = [{"campaign_id": target.campaign_id, "sku": target.sku, "name": target.campaign_name}]
    journal, run_id = start_journal(journal_path, "sales.fee_update", items)
    plan = SalesService(journal, client).plan_fee_update(items, fee, run_id=run_id)
    return journal, plan, inventory


def delete_preview(page: Any, config: Any, client: Any, target: Any, journal_path: Path):
    inventory = fetch_campaign_inventory(page, config)
    items = [{"campaign_id": target.campaign_id, "sku": target.sku, "name": target.campaign_name}]
    journal, run_id = start_journal(journal_path, "sales.delete", items)
    plan = SalesService(journal, client).plan_delete(items, run_id=run_id)
    return journal, plan, inventory
