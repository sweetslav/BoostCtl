from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from .auth import capture_session_token
from .config import load_config
from .shows_client import YandexShowsBoostClient

ROOT = Path.cwd()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config.json")
    p.add_argument("--campaigns", default="data/shows_campaigns.json")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    return p


def load_items(path: Path) -> list[dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise SystemExit("shows_campaigns.json должен содержать непустой JSON-массив.")

    seen: set[str] = set()
    items: list[dict[str, object]] = []
    for i, row in enumerate(raw, start=1):
        if not isinstance(row, dict):
            raise SystemExit(f"Строка {i}: ожидался объект.")
        sku = str(row.get("sku", "")).strip()
        limit = int(row.get("daily_limit", 300))
        if not sku:
            raise SystemExit(f"Строка {i}: пустой SKU.")
        if sku in seen:
            raise SystemExit(f"Строка {i}: дубль SKU {sku}.")
        if limit < 300:
            raise SystemExit(f"Строка {i}: daily_limit меньше 300 ₽.")
        seen.add(sku)
        items.append({"sku": sku, "daily_limit": limit})
    return items


def load_created_skus(path: Path) -> set[str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as report_file:
            return {
                row["sku"].strip()
                for row in csv.DictReader(report_file, delimiter=";")
                if row.get("status") == "CREATED" and row.get("sku")
            }
    except Exception:
        return set()


def main() -> int:
    args = parser().parse_args()
    config = load_config(ROOT / args.config)
    items = load_items(ROOT / args.campaigns)

    if args.start < 0:
        raise SystemExit("--start не может быть отрицательным.")
    items = items[args.start :]
    if args.limit:
        items = items[: args.limit]

    existing_report = ROOT / "reports" / "shows_create_report.csv"
    created_skus = load_created_skus(existing_report) if existing_report.exists() else set()

    if created_skus:
        before = len(items)
        items = [item for item in items if str(item["sku"]) not in created_skus]
        skipped = before - len(items)
        if skipped:
            print(f"Локальная защита от дублей: пропущено CREATED из отчёта: {skipped}")

    print("БУСТ ПОКАЗОВ — СОЗДАНИЕ КАМПАНИЙ")
    print(f"Кампаний в пакете: {len(items)}")
    print("Бюджет: 300 ₽/день (если не задано иначе)")
    print()

    report_path = ROOT / "reports" / "shows_create_report.csv"
    report_path.parent.mkdir(exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / "browser_profile"),
            headless=False,
            viewport={"width": 1400, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            token = capture_session_token(page, config)
            client = YandexShowsBoostClient(page, config, token)

            write_header = not report_path.exists()
            with report_path.open("a", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "timestamp","sku","daily_limit","campaign_name",
                        "offer_id","status","details"
                    ],
                    delimiter=";",
                )
                if write_header:
                    writer.writeheader()

                for index, item in enumerate(items, start=1):
                    sku = str(item["sku"])
                    daily_limit = int(item["daily_limit"])
                    date = datetime.now().astimezone().strftime("%d.%m.%Y")
                    name = f"{sku} | {date}"

                    print(f"[{index}/{len(items)}] {name} | {daily_limit} ₽/день")

                    try:
                        offer_id = client.find_offer_id(sku)
                        print(f"  offerId: {offer_id}")

                        if args.dry_run:
                            status = "DRY_RUN"
                            details = ""
                        else:
                            payload = client.create_campaign(
                                campaign_name=name,
                                offer_id=offer_id,
                                daily_limit=daily_limit,
                            )
                            status = "CREATED"
                            details = json.dumps(payload, ensure_ascii=False)

                        writer.writerow({
                            "timestamp": datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S"),
                            "sku": sku,
                            "daily_limit": daily_limit,
                            "campaign_name": name,
                            "offer_id": offer_id,
                            "status": status,
                            "details": details,
                        })
                        print(f"  {status}")
                    except Exception as exc:
                        writer.writerow({
                            "timestamp": datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S"),
                            "sku": sku,
                            "daily_limit": daily_limit,
                            "campaign_name": name,
                            "offer_id": "",
                            "status": "ERROR",
                            "details": f"{type(exc).__name__}: {exc}",
                        })
                        print(f"  ERROR: {type(exc).__name__}: {exc}")

            print()
            print(f"Отчёт: {report_path}")
            return 0
        finally:
            context.close()


if __name__ == "__main__":
    raise SystemExit(main())
