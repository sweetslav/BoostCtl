# ruff: noqa: E701
from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright

from .auth import capture_session_token
from .client import YandexBoostClient
from .config import load_config
from .create_services import SalesService
from .inventory import duplicate_skus, fetch_campaign_inventory, inventory_skus, write_inventory_csv
from .operator_workflows import delete_preview, fee_preview, sales_create_preview, shows_create_preview
from .presentation import presentation_action
from .shows_client import YandexShowsBoostClient
from .shows_inventory import fetch_shows_campaign_inventory, shows_summary
from .v2_workflows import apply_sales_create, apply_shows_create


ROOT = Path.cwd()
DB = ROOT / "local_data" / "boostctl.db"


def parse_skus(value: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for sku in value.replace(",", "\n").splitlines():
        sku = sku.strip()
        if sku and sku not in seen:
            seen.add(sku)
            result.append(sku)
    return result


def select_campaign_by_target(records, target: str):
    matches = [row for row in records if row.campaign_id == target or row.sku == target]
    if not matches:
        raise ValueError("Кампания не найдена в интерфейсе Яндекса.")
    if len(matches) > 1:
        ids = ", ".join(row.campaign_id for row in matches)
        raise ValueError(f"REVIEW: найдено несколько кампаний: {ids}")
    return matches[0]


@dataclass(slots=True)
class OperatorSession:
    page: object
    config: object
    sales_client: object
    shows_client: object
    journal_path: Path


@contextmanager
def operator_session():
    config = load_config(ROOT / "config.json")
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / "browser_profile"), headless=False,
            viewport={"width": 1400, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            token = capture_session_token(page, config)
            yield OperatorSession(
                page, config, YandexBoostClient(page, config, token),
                YandexShowsBoostClient(page, config, token), DB,
            )
        finally:
            context.close()


def _choose(prompt: str) -> str:
    return input(prompt).strip()


def render_preview(plan) -> None:
    for operation in plan:
        target = operation.target
        fields = [presentation_action(operation), f"SKU: {target.get('sku', '')}"]
        if "campaign_id" in target:
            fields.append(f"campaign_id: {target['campaign_id']}")
        if "offer_id" in operation.intent:
            fields.append(f"offerId: {operation.intent['offer_id']}")
        if "fee" in operation.intent:
            fields.append(f"ставка: {operation.intent['fee']:g}")
        if "requested_fee" in operation.intent:
            fields.append(f"requested fee: {operation.intent['requested_fee']:g}")
            if operation.intent.get("current_fee") is not None:
                fields.append(f"current fee: {operation.intent['current_fee']:g}")
        if "daily_limit" in operation.intent:
            fields.append(f"daily limit: {operation.intent['daily_limit']}")
        fields.append(f"source quality: {operation.source_quality.value}")
        if operation.warnings:
            fields.append(f"причина: {'; '.join(operation.warnings)}")
        print(" | ".join(fields))


def _confirmed(action: str, plan) -> bool:
    count = sum(operation.executable for operation in plan)
    if not count:
        print("Нет операций для выполнения. Изменений не выполнено.")
        return False
    print("\n1. Выполнить\n2. Отмена")
    if _choose("> ") != "1":
        print("Операция отменена. Изменений не выполнено.")
        return False
    if _choose(f"Для продолжения введите {action} {count}: ") == f"{action} {count}":
        return True
    print("Операция отменена. Изменений не выполнено.")
    return False


def _verify_sales(session: OperatorSession, operation) -> tuple[bool, object]:
    inventory = fetch_campaign_inventory(session.page, session.config)
    present = str(operation.target["sku"]) in inventory_skus(inventory)
    return present, {"sku": operation.target["sku"], "present": present}


def render_results(results) -> None:
    counts = {"successful": 0, "failed": 0, "unknown": 0}
    for result in results:
        state = result.state.value if result.state else "-"
        if state in {"SUCCEEDED", "VERIFIED"}:
            counts["successful"] += 1
        elif state == "FAILED":
            counts["failed"] += 1
        elif state == "UNKNOWN_RESULT":
            counts["unknown"] += 1
        fields = [
            f"SKU: {result.operation.target.get('sku', '-')}",
            f"Execution: {state}",
            f"Verification: {result.verification}",
        ]
        if result.campaign_id:
            fields.append(f"campaign_id: {result.campaign_id}")
        if result.error:
            fields.append(f"error: {result.error}")
        print(" | ".join(fields))
    print(
        f"Итог: успешно {counts['successful']} | ошибок {counts['failed']} | "
        f"неопределённых {counts['unknown']} | всего {len(results)}"
    )


def run_sales_create(session: OperatorSession, skus: list[str], fee: float) -> None:
    journal, plan = sales_create_preview(
        session.page, session.config, session.sales_client,
        [{"sku": sku, "fee": fee} for sku in skus], session.journal_path,
    )
    try:
        render_preview(plan)
        if _confirmed("CREATE", plan):
            render_results(apply_sales_create(journal, session.sales_client, plan, lambda op: _verify_sales(session, op)))
    finally:
        journal.close()


def run_shows_create(session: OperatorSession, skus: list[str], daily_limit: int) -> None:
    journal, plan, _ = shows_create_preview(
        session.page, session.config, session.shows_client,
        [{"sku": sku, "daily_limit": daily_limit} for sku in skus], session.journal_path,
    )
    try:
        render_preview(plan)
        if _confirmed("CREATE", plan):
            render_results(apply_shows_create(journal, session.shows_client, plan))
    finally:
        journal.close()


def apply_fee_plan(journal, client, plan):
    return SalesService(journal, client).apply_fee_update_plan(plan)


def apply_delete_plan(journal, client, plan):
    return SalesService(journal, client).apply_delete_plan(plan)


def run_fee_update(session: OperatorSession, target_value: str, fee: float) -> None:
    inventory = fetch_campaign_inventory(session.page, session.config)
    try:
        target = select_campaign_by_target(inventory, target_value)
    except ValueError as exc:
        print(exc)
        return
    journal, plan, _ = fee_preview(
        session.page, session.config, session.sales_client, target, fee, session.journal_path,
    )
    try:
        render_preview(plan)
        if plan[0].intent.get("current_fee") is None:
            print("Текущая ставка не получена из UI inventory.")
        if _confirmed("UPDATE", plan):
            render_results(apply_fee_plan(journal, session.sales_client, plan))
    finally:
        journal.close()


def run_delete(session: OperatorSession, target_value: str) -> None:
    inventory = fetch_campaign_inventory(session.page, session.config)
    try:
        target = select_campaign_by_target(inventory, target_value)
    except ValueError as exc:
        print(exc)
        return
    journal, plan, _ = delete_preview(
        session.page, session.config, session.sales_client, target, session.journal_path,
    )
    try:
        render_preview(plan)
        if _confirmed("DELETE", plan):
            render_results(apply_delete_plan(journal, session.sales_client, plan))
    finally:
        journal.close()


def render_inventory(records, sku: str = "", campaign_id: str = "", *, show_all: bool = False) -> None:
    duplicates = duplicate_skus(records)
    print(f"Кампаний, наблюдаемых в интерфейсе Яндекса: {len(records)}")
    print(f"Уникальных SKU: {len(inventory_skus(records))}")
    print(f"SKU с дублями: {len(duplicates)}")
    selected = [] if not (sku or campaign_id or show_all) else records
    if sku:
        selected = [row for row in selected if row.sku == sku]
    if campaign_id:
        selected = [row for row in selected if row.campaign_id == campaign_id]
    for row in selected:
        print(f"{row.campaign_id} | {row.sku} | {row.campaign_name} | {row.url}")


def run_inventory(session: OperatorSession, sku: str = "", campaign_id: str = "", *, show_all: bool = False) -> None:
    records = fetch_campaign_inventory(session.page, session.config)
    snapshot = ROOT / "reports" / "campaigns_from_yandex.csv"
    write_inventory_csv(records, snapshot)
    render_inventory(records, sku, campaign_id, show_all=show_all)
    print(f"Снимок: {snapshot}")


def inventory_menu(session: OperatorSession) -> None:
    records = fetch_campaign_inventory(session.page, session.config)
    snapshot = ROOT / "reports" / "campaigns_from_yandex.csv"
    write_inventory_csv(records, snapshot)
    render_inventory(records)
    print(f"Снимок: {snapshot}")
    while True:
        print("\n1. Буст продаж\n2. Буст показов\n3. Все кампании\n0. Назад")
        choice = _choose("> ")
        if choice == "1":
            render_inventory(records, show_all=True)
        elif choice == "2":
            shows_records = fetch_shows_campaign_inventory(session.page, session.config)
            summary = shows_summary(shows_records)
            print(f"Всего кампаний: {summary['total']}\nАктивных: {summary['active']}\nОстановленных/закрытых: {summary['stopped_or_closed']}\nНеизвестный статус: {summary['unknown']}")
            for record in shows_records:
                print(f"{record.campaign_id} | {record.sku or '-'} | {record.name} | {record.raw_status or '-'} | {record.daily_limit or '-'} | {record.url}")
        elif choice == "3":
            render_inventory(records, show_all=True)
            shows_records = fetch_shows_campaign_inventory(session.page, session.config)
            for record in shows_records:
                print(f"SHOWS | {record.campaign_id} | {record.sku or '-'} | {record.name} | {record.raw_status or '-'}")
        elif choice == "0":
            return


def _presentation_verification(state: str | None, source: str | None) -> str:
    if state == "VERIFIED":
        return "VERIFIED"
    if state == "VERIFY_REQUIRED":
        return "VERIFY_REQUIRED"
    if source == "NOT_VERIFIED":
        return "NOT_VERIFIED"
    return "NOT_APPLICABLE"


def history(export: bool = False) -> None:
    if not DB.exists():
        print("История операций пока пуста.")
        return
    connection = sqlite3.connect(DB)
    rows = connection.execute(
        """SELECT r.command, r.started_at, o.target_json, o.operation_id,
                  o.state, v.state, v.source, a.error
           FROM operations o LEFT JOIN runs r ON r.run_id = o.run_id
           LEFT JOIN verifications v ON v.operation_id = o.operation_id
           LEFT JOIN attempts a ON a.operation_id = o.operation_id
           ORDER BY o.updated_at DESC LIMIT 20"""
    ).fetchall()
    if export:
        output = ROOT / "local_data" / "reports" / "operation_history.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(["run_id", "command", "started_at", "status", "operation_id", "state", "target", "intent"])
            runs = connection.execute(
                "SELECT run_id, command, started_at, status FROM runs ORDER BY started_at DESC LIMIT 20"
            ).fetchall()
            for run in runs:
                for operation in connection.execute("SELECT operation_id, state, target_json, intent_json FROM operations WHERE run_id=?", (run[0],)):
                    writer.writerow([*run, *operation])
        print(f"Экспорт: {output}")
    else:
        for row in rows:
            target = json.loads(row[2]) if row[2] else {}
            verification = _presentation_verification(row[5], row[6])
            print(
                f"{row[1] or '-'} | {row[0] or '-'} | SKU: {target.get('sku', '-')} | "
                f"campaign_id: {target.get('campaign_id', '-')} | operation_id: {row[3]} | "
                f"Execution: {row[4]} | Verification: {verification} | error: {row[7] or '-'}"
            )
        recovery = connection.execute("SELECT operation_id, type, state, updated_at FROM operations WHERE state IN ('APPLYING','UNKNOWN_RESULT','VERIFY_REQUIRED')").fetchall()
        for row in recovery:
            print(f"ТРЕБУЕТ ПРОВЕРКИ: {row[1]} {row[0]} ({row[2]}, {row[3]}). Автоматический повтор заблокирован.")
    connection.close()


def main() -> int:
    while True:
        print(
            "\nBoostCtl\n"
            "1. Создать Буст продаж\n"
            "2. Создать Буст показов\n"
            "3. Изменить ставку Буста продаж\n"
            "4. Удалить Буст продаж\n"
            "5. Посмотреть кампании Яндекса\n"
            "6. История операций\n"
            "7. Диагностика\n"
            "0. Выход"
        )
        choice = _choose("> ")
        if choice == "1":
            skus = parse_skus(_choose("SKU (через запятую или с новой строки): "))
            fee = float(_choose("Ставка: "))
            with operator_session() as session:
                run_sales_create(session, skus, fee)
        elif choice == "2":
            skus = parse_skus(_choose("SKU (через запятую или с новой строки): "))
            daily_limit = int(_choose("Дневной лимит: "))
            with operator_session() as session:
                run_shows_create(session, skus, daily_limit)
        elif choice == "3":
            target = _choose("SKU или campaign_id: ")
            fee = float(_choose("Новая ставка: "))
            with operator_session() as session:
                run_fee_update(session, target, fee)
        elif choice == "4":
            target = _choose("SKU или campaign_id: ")
            with operator_session() as session:
                run_delete(session, target)
        elif choice == "5":
            with operator_session() as session:
                inventory_menu(session)
        elif choice == "6":
            history()
        elif choice == "7":
            print("Расширенная диагностика: запустите RUN_SALES_DIAGNOSTICS.bat из папки проекта.")
        elif choice == "0":
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
