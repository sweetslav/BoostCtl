from types import SimpleNamespace

from yandex_boost.inventory import SalesInventoryRecord
from yandex_boost.operator_workflows import (
    delete_preview,
    fee_preview,
    sales_create_preview,
    shows_create_preview,
)


class Client:
    def find_offer_id(self, sku): return f"offer-{sku}"


def test_shows_operator_preview_uses_v2_planner_without_mutation(tmp_path):
    journal, plan = shows_create_preview(Client(), [{"sku": "A", "daily_limit": 300}], set(), tmp_path / "db.sqlite")
    assert plan[0].intent["offer_id"] == "offer-A"
    journal.close()


class Page:
    pass


def test_sales_operator_preview_uses_fresh_inventory_and_skips_duplicate(tmp_path, monkeypatch):
    inventory = [SalesInventoryRecord("1", "A | 01.01.2026", "A", "url")]
    monkeypatch.setattr("yandex_boost.operator_workflows.fetch_campaign_inventory", lambda *_: inventory)
    journal, plan = sales_create_preview(Page(), object(), Client(), [{"sku": "A", "fee": 10}], tmp_path / "db.sqlite")
    assert plan[0].disposition.value == "SKIP"
    assert plan[0].source_quality.value == "UI_OBSERVED"
    journal.close()


def test_fee_and_delete_previews_only_plan_selected_campaign(tmp_path, monkeypatch):
    target = SalesInventoryRecord("17", "A | 01.01.2026", "A", "url")
    monkeypatch.setattr("yandex_boost.operator_workflows.fetch_campaign_inventory", lambda *_: [target])
    client = SimpleNamespace()
    fee_journal, fee_plan, _ = fee_preview(Page(), object(), client, target, 15, tmp_path / "fee.sqlite")
    delete_journal, delete_plan, _ = delete_preview(Page(), object(), client, target, tmp_path / "delete.sqlite")
    assert fee_plan[0].target["campaign_id"] == "17"
    assert delete_plan[0].target["campaign_id"] == "17"
    fee_journal.close()
    delete_journal.close()


def test_fee_and_delete_previews_start_journal_runs(tmp_path, monkeypatch):
    target = SalesInventoryRecord("17", "A | 01.01.2026", "A", "url")
    monkeypatch.setattr("yandex_boost.operator_workflows.fetch_campaign_inventory", lambda *_: [target])
    fee_journal, _, _ = fee_preview(Page(), object(), SimpleNamespace(), target, 15, tmp_path / "fee.sqlite")
    delete_journal, _, _ = delete_preview(Page(), object(), SimpleNamespace(), target, tmp_path / "delete.sqlite")
    assert fee_journal.connection.execute("SELECT command FROM runs").fetchone()[0] == "sales.fee_update"
    assert delete_journal.connection.execute("SELECT command FROM runs").fetchone()[0] == "sales.delete"
    fee_journal.close()
    delete_journal.close()
