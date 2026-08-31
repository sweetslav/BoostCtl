from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from .auth import capture_session_token
from .client import YandexBoostClient
from .config import load_campaigns, load_config
from .generator import InputFormatError, build_campaigns_json
from .inventory import (
    duplicate_skus,
    fetch_campaign_inventory,
    inventory_skus,
    write_inventory_csv,
)
from .report import CsvReport
from .v2_workflows import apply_sales_create, has_apply_failure, plan_sales_create
from .create_services import SalesService
from .journal import OperationJournal
from uuid import uuid4


ROOT = Path.cwd()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="boostctl",
        description="Создание отдельных кампаний «Буст продаж» по SKU.",
    )
    parser.add_argument(
        "command",
        choices=[
            "validate", "preflight", "test", "run", "retry-errors", "export",
            "delete-preview", "delete", "make-json", "update-bids-preview", "update-bids",
        ],
    )
    parser.add_argument("--campaigns", default="data/campaigns.json")
    parser.add_argument("--delete-file", default="data/campaigns_to_delete.json")
    parser.add_argument("--input-list", default="data/campaigns_input.txt")
    parser.add_argument("--fee", type=float, default=None)
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--date", default="")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser


def resolve_date(value: str) -> str:
    if not value:
        return datetime.now().astimezone().strftime("%d.%m.%Y")
    try:
        parsed = datetime.strptime(value, "%d.%m.%Y").replace(tzinfo=timezone.utc)
        return parsed.strftime("%d.%m.%Y")
    except ValueError as exc:
        raise SystemExit("Дата должна быть в формате ДД.ММ.ГГГГ.") from exc


def _select_campaigns(args, campaigns, report: CsvReport):
    selected = campaigns[args.start :]
    if args.limit > 0:
        selected = selected[: args.limit]
    if args.command == "retry-errors":
        failed = report.failed_skus()
        selected = [item for item in selected if item.sku in failed]
    return selected


def _print_preflight(selected, existing_skus: set[str], duplicates_count: int) -> list:
    already_exists = [item for item in selected if item.sku in existing_skus]
    new_items = [item for item in selected if item.sku not in existing_skus]

    print()
    print("ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА")
    print(f"Входных SKU: {len(selected)}")
    print(f"Уникальных SKU в текущих кампаниях Яндекса: {len(existing_skus)}")
    print(f"SKU-дублей уже в Яндексе: {duplicates_count}")
    print(f"Уже существуют и будут пропущены: {len(already_exists)}")
    print(f"Будут созданы: {len(new_items)}")

    if already_exists:
        print("\nПропускаемые SKU:")
        for item in already_exists:
            print(f"  SKIP {item.sku}")

    return new_items



def _load_delete_ids(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"Не найден файл удаления: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("Файл удаления должен содержать JSON-массив campaign_id.")

    ids = [str(value).strip() for value in raw]
    if not ids or any(not value.isdigit() for value in ids):
        raise SystemExit("Все campaign_id должны быть непустыми числовыми значениями.")
    if len(ids) != len(set(ids)):
        raise SystemExit("В файле удаления есть повторяющиеся campaign_id.")
    return ids


def _print_delete_preview(delete_ids: list[str], inventory) -> tuple[list, list[str]]:
    by_id = {row.campaign_id: row for row in inventory}
    found = [by_id[campaign_id] for campaign_id in delete_ids if campaign_id in by_id]
    missing = [campaign_id for campaign_id in delete_ids if campaign_id not in by_id]

    print()
    print("ПРОВЕРКА УДАЛЕНИЯ")
    print(f"ID в файле: {len(delete_ids)}")
    print(f"Найдено в Яндексе: {len(found)}")
    print(f"Не найдено: {len(missing)}")

    for row in found:
        print(f"  {row.campaign_id} | {row.sku} | {row.campaign_name}")

    if missing:
        print("\nНЕ НАЙДЕНЫ:")
        for campaign_id in missing:
            print(f"  {campaign_id}")

    return found, missing

def main() -> int:
    args = build_parser().parse_args()

    if args.command == "make-json":
        input_path = ROOT / args.input_list
        output_path = ROOT / args.campaigns
        try:
            campaigns = build_campaigns_json(input_path, output_path)
        except (FileNotFoundError, InputFormatError) as exc:
            print(f"ОШИБКА: {exc}")
            return 2

        print()
        print("CAMPAIGNS.JSON СОЗДАН")
        print(f"Источник: {input_path}")
        print(f"Результат: {output_path}")
        print(f"Кампаний: {len(campaigns)}")
        print()
        print("Первые строки:")
        for item in campaigns[:10]:
            print(f"  {item['sku']} | ставка {item['bid']:g}%")
        if len(campaigns) > 10:
            print(f"  ... ещё {len(campaigns) - 10}")
        print()
        print("Следующий безопасный шаг: 01_VALIDATE.bat")
        return 0

    config = load_config(ROOT / args.config)
    report = CsvReport(ROOT / "reports" / "api_report.csv")
    run_date = resolve_date(args.date)

    campaigns = []
    selected = []
    if args.command not in {"export", "delete-preview", "delete", "update-bids-preview", "update-bids"}:
        campaigns = load_campaigns(ROOT / args.campaigns)

    if args.command == "validate":
        print(f"OK: {len(campaigns)} строк, дублей SKU во входном файле нет.")
        return 0

    if campaigns:
        selected = _select_campaigns(args, campaigns, report)

    if not selected and args.command not in {"export", "delete-preview", "delete", "update-bids-preview", "update-bids"}:
        print("Нет строк для обработки.")
        return 0

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / "browser_profile"),
            headless=False,
            viewport={"width": 1400, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            token = capture_session_token(page, config)
            print("\nСканирую текущие кампании Яндекса...", flush=True)
            inventory = fetch_campaign_inventory(page, config)
            inventory_path = ROOT / "reports" / "campaigns_from_yandex.csv"
            write_inventory_csv(inventory, inventory_path)
            existing_skus = inventory_skus(inventory)
            duplicates = duplicate_skus(inventory)

            print(f"Фактических кампаний в Яндексе: {len(inventory)}")
            print(f"Уникальных SKU: {len(existing_skus)}")
            print(f"SKU с дублями: {len(duplicates)}")
            print(f"Снимок сохранён: {inventory_path}")

            if args.command in {"update-bids-preview", "update-bids"}:
                if args.fee is None or not 0 < args.fee <= 100:
                    print("ОШИБКА: укажите ставку от 0 до 100 через --fee.")
                    return 2
                target = inventory[: args.limit] if args.limit else inventory
                journal = OperationJournal(ROOT / "local_data" / "boostctl.db")
                run_id = str(uuid4())
                journal.start_run(run_id, "sales.fee_update", [])
                client = YandexBoostClient(page, config, token)
                service = SalesService(journal, client)
                plan = service.plan_fee_update([{"campaign_id": row.campaign_id, "sku": row.sku, "name": row.campaign_name} for row in target], args.fee, run_id=run_id)
                for operation in plan:
                    print(f"{operation.disposition.value} {operation.target['campaign_id']} -> {args.fee:g}% | {'; '.join(operation.warnings)}")
                if args.command == "update-bids-preview":
                    journal.close()
                    return 0
                expected = f"UPDATE {sum(item.executable for item in plan)}"
                if input(f"Type {expected} to continue: ").strip() != expected:
                    journal.close()
                    return 0
                results = service.apply_fee_update_plan(plan)
                journal.close()
                return 1 if has_apply_failure(results) else 0

            if args.command in {"delete-preview", "delete"}:
                delete_ids = _load_delete_ids(ROOT / args.delete_file)
                found, missing = _print_delete_preview(delete_ids, inventory)

                journal = OperationJournal(ROOT / "local_data" / "boostctl.db")
                run_id = str(uuid4())
                journal.start_run(run_id, "sales.delete", [])
                client = YandexBoostClient(page, config, token)
                service = SalesService(journal, client)
                plan = service.plan_delete([{"campaign_id": row.campaign_id, "sku": row.sku, "name": row.campaign_name} for row in found], run_id=run_id)
                for operation in plan:
                    print(f"{operation.disposition.value} DELETE {operation.target['campaign_id']} | {'; '.join(operation.warnings)}")
                if args.command == "delete-preview" or missing:
                    journal.close()
                    return 0 if not missing else 2
                expected = f"DELETE {sum(item.executable for item in plan)}"
                if input(f"Type {expected} to continue: ").strip() != expected:
                    journal.close()
                    return 0
                results = service.apply_delete_plan(plan)
                journal.close()
                return 1 if has_apply_failure(results) else 0


            if args.command == "export":
                return 0

            # The V2 planner is the sole Sales create mutation path.
            v2_items = selected[:1] if args.command == "test" else selected
            client = YandexBoostClient(page, config, token)
            input_rows = [{"sku": item.sku, "fee": item.bid} for item in v2_items]
            journal, plan = plan_sales_create(
                client, ROOT / "local_data" / "boostctl.db", input_rows, existing_skus, run_date,
            )
            for operation in plan:
                print(f"{operation.disposition.value} {operation.target['sku']} | {operation.intent.get('offer_id', '')} | {operation.source_quality.value} | {'; '.join(operation.warnings)}")
            if args.command == "preflight" or args.dry_run:
                for operation in plan:
                    report.append(sku=str(operation.target["sku"]), bid=float(operation.intent.get("fee") or 0), campaign_name=str(operation.intent["campaign_name"]), offer_id=str(operation.intent.get("offer_id", "")), status=operation.disposition.value, details="; ".join(operation.warnings) or "V2 dry-run", operation_id=operation.operation_id, execution_state="PLANNED", verification="NOT_APPLIED")
                journal.close()
                return 0

            def verify(operation):
                refreshed = fetch_campaign_inventory(page, config)
                present = str(operation.target["sku"]) in inventory_skus(refreshed)
                return present, {"sku": operation.target["sku"], "present": present}

            results = apply_sales_create(journal, client, plan, verify, allow_failed_retry=args.command == "retry-errors")
            journal.close()
            for result in results:
                operation = result.operation
                report.append(sku=str(operation.target["sku"]), bid=float(operation.intent.get("fee") or 0), campaign_name=str(operation.intent["campaign_name"]), offer_id=str(operation.intent.get("offer_id", "")), status=(result.state.value if result.state else operation.disposition.value), details="; ".join(value for value in (result.verification, result.error, *operation.warnings) if value), operation_id=operation.operation_id, execution_state=result.state.value if result.state else "", verification=result.verification, campaign_id=result.campaign_id or "")
            return 1 if has_apply_failure(results) else 0

        finally:
            context.close()


if __name__ == "__main__":
    sys.exit(main())
