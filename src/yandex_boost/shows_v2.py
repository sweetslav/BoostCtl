from __future__ import annotations

import csv
from datetime import datetime

from playwright.sync_api import sync_playwright

from .auth import capture_session_token
from .config import load_config
from .shows_client import YandexShowsBoostClient
from .shows_create import ROOT, load_items, parser
from .operator_workflows import shows_create_preview
from .v2_workflows import apply_shows_create, has_apply_failure


def shows_apply_summary(results) -> dict[str, int]:
    return {
        "successful": sum(result.state.value in ("SUCCEEDED", "VERIFIED") for result in results),
        "failed": sum(result.state.value == "FAILED" for result in results),
        "unknown": sum(result.state.value == "UNKNOWN_RESULT" for result in results),
        "verified": sum(result.verification == "VERIFIED" for result in results),
        "not_verified": sum(result.verification == "NOT_VERIFIED" for result in results),
        "skipped": sum(not result.operation.executable for result in results),
        "review": sum(result.operation.disposition.value == "REVIEW" for result in results),
    }


def main() -> int:
    args = parser().parse_args()
    if args.start < 0:
        raise SystemExit("--start must not be negative.")
    config = load_config(ROOT / args.config)
    items = load_items(ROOT / args.campaigns)[args.start :]
    if args.limit:
        items = items[: args.limit]
    report_path = ROOT / "reports" / "shows_create_report.csv"
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(user_data_dir=str(ROOT / "browser_profile"), headless=False, viewport={"width": 1400, "height": 900})
        page = context.pages[0] if context.pages else context.new_page()
        try:
            client = YandexShowsBoostClient(page, config, capture_session_token(page, config))
            journal, plan, _ = shows_create_preview(page, config, client, items, ROOT / "local_data" / "boostctl.db")
            for operation in plan:
                print(f"{operation.disposition.value} {operation.target['sku']} | {operation.intent.get('offer_id', '')} | {operation.source_quality.value} | {'; '.join(operation.warnings)}")
            results = [] if args.dry_run else apply_shows_create(journal, client, plan)
            if not args.dry_run:
                for result in results:
                    print(f"SKU: {result.operation.target['sku']} | Действие: CREATE | Результат: {result.state.value if result.state else result.operation.disposition.value} | Проверка: {result.verification} | Campaign ID: {result.campaign_id or 'неизвестен'}")
                    if result.error:
                        print(f"Ошибка: {result.error}")
                summary = shows_apply_summary(results)
                print(f"Итог: успешно {summary['successful']} | ошибок {summary['failed']} | неопределённых {summary['unknown']} | проверено {summary['verified']} | не проверено {summary['not_verified']} | пропущено {summary['skipped']} | требует проверки {summary['review']}")
            report_path.parent.mkdir(exist_ok=True)
            write_header = not report_path.exists()
            with report_path.open("a", encoding="utf-8-sig", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=["timestamp", "sku", "daily_limit", "campaign_name", "offer_id", "status", "details", "operation_id", "execution_state", "verification", "campaign_id"], delimiter=";")
                if write_header:
                    writer.writeheader()
                by_id = {result.operation.operation_id: result for result in results}
                for operation in plan:
                    result = by_id.get(operation.operation_id)
                    status = "DRY_RUN" if args.dry_run else (result.state.value if result and result.state else operation.disposition.value)
                    details = "; ".join(value for value in ((result.verification if result else ""), (result.error if result else ""), *operation.warnings) if value)
                    writer.writerow({"timestamp": datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S"), "sku": operation.target["sku"], "daily_limit": operation.intent.get("daily_limit", ""), "campaign_name": operation.intent["campaign_name"], "offer_id": operation.intent.get("offer_id", ""), "status": status, "details": details, "operation_id": operation.operation_id, "execution_state": result.state.value if result and result.state else "PLANNED", "verification": result.verification if result else "NOT_APPLIED", "campaign_id": result.campaign_id if result and result.campaign_id else ""})
            journal.close()
            print(f"Report: {report_path}")
            return 1 if has_apply_failure(results) else 0
        finally:
            context.close()
