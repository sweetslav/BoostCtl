from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .create_services import SalesService
from .inventory import fetch_campaign_inventory, inventory_skus
from .v2_workflows import plan_sales_create, plan_shows_create, start_journal


def sales_create_preview(page: Any, config: Any, client: Any, items: list[dict[str, object]], journal_path: Path):
    inventory = fetch_campaign_inventory(page, config)
    return plan_sales_create(client, journal_path, items, inventory_skus(inventory), datetime.now().astimezone().strftime("%d.%m.%Y"))


def shows_create_preview(client: Any, items: list[dict[str, object]], history_skus: set[str], journal_path: Path):
    return plan_shows_create(client, journal_path, items, history_skus, datetime.now().astimezone().strftime("%d.%m.%Y"))


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
