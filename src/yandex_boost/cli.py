from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from .auth import capture_session_token
from .cache import OfferCache
from .client import YandexBoostClient
from .config import load_campaigns, load_config
from .inventory import (
    duplicate_skus,
    fetch_campaign_inventory,
    inventory_skus,
    write_inventory_csv,
)
from .logging_setup import setup_logging
from .report import CsvReport


ROOT = Path.cwd()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="boostctl",
        description="Создание отдельных кампаний «Буст продаж» по SKU.",
    )
    parser.add_argument(
        "command",
        choices=["validate", "preflight", "test", "run", "retry-errors", "export"],
    )
    parser.add_argument("--campaigns", default="data/campaigns.json")
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


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(ROOT / args.config)
    campaigns = load_campaigns(ROOT / args.campaigns)
    logger = setup_logging(ROOT / "logs", args.verbose)
    report = CsvReport(ROOT / "reports" / "api_report.csv")
    cache = OfferCache(ROOT / "data" / "offer_cache.json")
    run_date = resolve_date(args.date)

    if args.command == "validate":
        print(f"OK: {len(campaigns)} строк, дублей SKU во входном файле нет.")
        return 0

    selected = _select_campaigns(args, campaigns, report)
    if not selected and args.command != "export":
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
            inventory = fetch_campaign_inventory(page, config)
            inventory_path = ROOT / "reports" / "campaigns_from_yandex.csv"
            write_inventory_csv(inventory, inventory_path)
            existing_skus = inventory_skus(inventory)
            duplicates = duplicate_skus(inventory)

            print(f"Фактических кампаний в Яндексе: {len(inventory)}")
            print(f"Уникальных SKU: {len(existing_skus)}")
            print(f"SKU с дублями: {len(duplicates)}")
            print(f"Снимок сохранён: {inventory_path}")

            if args.command == "export":
                return 0

            new_items = _print_preflight(selected, existing_skus, len(duplicates))
            if args.command == "preflight":
                return 0

            if args.command == "test":
                new_items = new_items[:1]

            if not new_items:
                print("Создавать нечего: все SKU уже используются в кампаниях.")
                return 0

            print(f"Дата в названиях: {run_date}")
            print(f"Режим без создания: {'да' if args.dry_run else 'нет'}")

            client = YandexBoostClient(page, config, token)

            for index, item in enumerate(new_items, start=1):
                name = f"{item.sku} | {run_date}"
                logger.info("[%s/%s] %s; bid=%s", index, len(new_items), name, item.bid)

                if item.sku in existing_skus:
                    logger.info("SKIP: SKU уже присутствует в кампании Яндекса")
                    report.append(
                        sku=item.sku,
                        bid=item.bid,
                        campaign_name=name,
                        offer_id="",
                        status="SKIPPED_EXISTS",
                        details="SKU already exists in Yandex campaigns.",
                    )
                    continue

                offer_id = ""
                try:
                    if not args.no_cache:
                        offer_id = cache.get(item.sku) or ""
                    if not offer_id:
                        offer_id = client.find_offer_id(item.sku)
                        cache.set(item.sku, offer_id)

                    if args.dry_run:
                        logger.info("VALID: offerId=%s", offer_id)
                        report.append(
                            sku=item.sku,
                            bid=item.bid,
                            campaign_name=name,
                            offer_id=offer_id,
                            status="VALID",
                            details="Dry run; campaign was not created.",
                        )
                        continue

                    response = client.create_campaign(
                        campaign_name=name,
                        offer_id=offer_id,
                        bid=item.bid,
                    )
                    report.append(
                        sku=item.sku,
                        bid=item.bid,
                        campaign_name=name,
                        offer_id=offer_id,
                        status="CREATED",
                        details=json.dumps(response, ensure_ascii=False),
                    )
                    existing_skus.add(item.sku)
                    logger.info("CREATED: offerId=%s", offer_id)

                except Exception as exc:  # noqa: BLE001
                    report.append(
                        sku=item.sku,
                        bid=item.bid,
                        campaign_name=name,
                        offer_id=offer_id,
                        status="ERROR",
                        details=f"{type(exc).__name__}: {exc}",
                    )
                    logger.exception("ERROR for SKU %s", item.sku)
                    if args.command == "test":
                        return 1

                time.sleep(config.request_delay_seconds)

            print("Готово. См. reports/api_report.csv и reports/campaigns_from_yandex.csv.")
            return 0
        finally:
            context.close()


if __name__ == "__main__":
    sys.exit(main())
