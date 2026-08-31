from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path


FIELDS = [
    "timestamp",
    "sku",
    "bid",
    "campaign_name",
    "offer_id",
    "status",
    "details",
    "operation_id",
    "execution_state",
    "verification",
    "campaign_id",
]


class CsvReport:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def rows(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8-sig", newline="") as file:
            return list(csv.DictReader(file, delimiter=";"))

    def append(
        self,
        *,
        sku: str,
        bid: float,
        campaign_name: str,
        offer_id: str,
        status: str,
        details: str,
        operation_id: str = "",
        execution_state: str = "",
        verification: str = "",
        campaign_id: str = "",
    ) -> None:
        exists = self.path.exists()
        with self.path.open("a", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS, delimiter=";")
            if not exists:
                writer.writeheader()
            writer.writerow(
                {
                    "timestamp": datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M:%S"),
                    "sku": sku,
                    "bid": bid,
                    "campaign_name": campaign_name,
                    "offer_id": offer_id,
                    "status": status,
                    "details": details,
                    "operation_id": operation_id,
                    "execution_state": execution_state,
                    "verification": verification,
                    "campaign_id": campaign_id,
                }
            )

    def created_names(self) -> set[str]:
        return {
            row["campaign_name"]
            for row in self.rows()
            if row.get("status") == "CREATED"
        }

    def failed_skus(self) -> set[str]:
        latest: dict[str, str] = {}
        for row in self.rows():
            latest[row.get("sku", "")] = row.get("status", "")
        return {sku for sku, status in latest.items() if sku and status == "ERROR"}
