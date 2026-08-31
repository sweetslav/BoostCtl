from __future__ import annotations

from uuid import uuid4

from .operations import OperationType, PlanDisposition, PlannedOperation, SourceQuality, operation_id


def plan_sales_create(items: list[dict[str, object]], observed_skus: set[str], run_id: str | None = None) -> list[PlannedOperation]:
    run_id = run_id or str(uuid4())
    operations: list[PlannedOperation] = []
    for item in items:
        sku = str(item["sku"])
        intent = {"sku": sku, "fee": item.get("bid")}
        warnings = ("UI observed duplicate protection",) if sku in observed_skus else ()
        target = {"sku": sku}
        operations.append(PlannedOperation(
            operation_id(OperationType.CREATE_SALES, target, intent), run_id,
            OperationType.CREATE_SALES, target, intent, SourceQuality.UI_OBSERVED,
            disposition=PlanDisposition.SKIP if warnings else PlanDisposition.CREATE,
            warnings=warnings,
        ))
    return operations
