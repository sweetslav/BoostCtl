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
from .logging_setup import setup_logging
from .report import CsvReport


ROOT = Path.cwd()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yandex-boost",
        description="Create separate Yandex Market Sales Boost campaigns per SKU.",
    )
    parser.add_argument(
        "command",
        choices=["validate", "test", "run", "retry-errors"],
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
        return datetime.strptime(value, "%d.%m.%Y").replace(tzinfo=timezone.utc).strftime("%d.%m.%Y")
    except ValueError as exc:
        raise SystemExit("Date must use DD.MM.YYYY format.") from exc


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(ROOT / args.config)
    campaigns = load_campaigns(ROOT / args.campaigns)
    logger = setup_logging(ROOT / "logs", args.verbose)
    report = CsvReport(ROOT / "reports" / "api_report.csv")
    cache = OfferCache(ROOT / "data" / "offer_cache.json")
    run_date = resolve_date(args.date)

    if args.command == "validate":
        print(f"OK: {len(campaigns)} campaign rows are valid.")
        return 0

    selected = campaigns[args.start:]
    if args.limit > 0:
        selected = selected[:args.limit]
    if args.command == "test":
        selected = selected[:1]
    elif args.command == "retry-errors":
        failed = report.failed_skus()
        selected = [item for item in selected if item.sku in failed]

    if not selected:
        print("Nothing to process.")
        return 0

    print(f"Rows: {len(selected)}")
    print(f"Campaign date: {run_date}")
    print(f"Dry run: {'yes' if args.dry_run else 'no'}")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / "browser_profile"),
            headless=False,
            viewport={"width": 1400, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            token = capture_session_token(page, config)
            client = YandexBoostClient(page, config, token)
            created_names = report.created_names()

            for index, item in enumerate(selected, start=1):
                name = f"{item.sku} | {run_date}"
                logger.info("[%s/%s] %s; bid=%s", index, len(selected), name, item.bid)

                if name in created_names and not args.dry_run:
                    logger.info("SKIP: already created according to report")
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
                    created_names.add(name)
                    logger.info("CREATED: offerId=%s", offer_id)

                except Exception as exc:
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

            print("Done. See reports/api_report.csv and logs/.")
            input("Press Enter to close the browser... ")
            return 0
        finally:
            context.close()


if __name__ == "__main__":
    sys.exit(main())
