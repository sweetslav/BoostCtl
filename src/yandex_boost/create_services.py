from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Callable, Protocol
from uuid import uuid4

from .client import AmbiguousMutationResult, RemoteRejectedError
from .journal import OperationJournal
from .operations import (
    OperationState,
    OperationType,
    PlanDisposition,
    PlannedOperation,
    SourceQuality,
    operation_id,
)


class CreateClient(Protocol):
    def find_offer_id(self, sku: str) -> str: ...

    def create_campaign(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    operation: PlannedOperation
    state: OperationState | None
    verification: str
    campaign_id: str | None = None
    error: str | None = None


def _campaign_id(response: object) -> str | None:
    """Return only an explicitly labelled identifier, never a generic numeric id."""
    if isinstance(response, dict):
        for key in ("salesCampaignId", "strategyId", "campaignId"):
            value = response.get(key)
            if value is not None:
                return str(value)
        for value in response.values():
            found = _campaign_id(value)
            if found:
                return found
    if isinstance(response, list):
        for value in response:
            found = _campaign_id(value)
            if found:
                return found
    return None


class _CreateService:
    operation_type: OperationType
    intent_key: str

    def __init__(self, journal: OperationJournal, client: CreateClient) -> None:
        self.journal = journal
        self.client = client

    def _plan(
        self,
        items: list[dict[str, object]],
        observed_skus: set[str],
        quality: SourceQuality,
        *,
        run_id: str | None = None,
        date: str,
    ) -> list[PlannedOperation]:
        run_id = run_id or str(uuid4())
        plan: list[PlannedOperation] = []
        seen: set[str] = set()
        for item in items:
            sku = str(item.get("sku", "")).strip()
            value = item.get(self.intent_key)
            target = {"sku": sku}
            intent = {"sku": sku, self.intent_key: value, "campaign_name": f"{sku} | {date}"}
            warnings: list[str] = []
            disposition = PlanDisposition.CREATE
            source_quality = SourceQuality.UNKNOWN
            if not sku or value is None:
                disposition = PlanDisposition.REVIEW
                warnings.append("Invalid campaign input")
            elif sku in seen:
                disposition = PlanDisposition.SKIP
                warnings.append("Duplicate SKU in input")
            elif sku in observed_skus:
                disposition = PlanDisposition.SKIP
                source_quality = quality
                warnings.append(f"Duplicate observation from {quality.value}; not factual inventory")
            else:
                try:
                    offer_id = self.client.find_offer_id(sku)
                    intent["offer_id"] = offer_id
                except Exception as exc:  # resolver errors require explicit review
                    disposition = PlanDisposition.REVIEW
                    warnings.append(f"Offer resolution failed: {type(exc).__name__}: {exc}")
            seen.add(sku)
            plan.append(
                PlannedOperation(
                    operation_id(self.operation_type, target, intent), run_id, self.operation_type,
                    target, intent, source_quality, disposition, tuple(warnings),
                )
            )
        return plan

    def apply_create_plan(
        self,
        plan: list[PlannedOperation],
        *,
        verify: Callable[[PlannedOperation], tuple[bool, object]] | None = None,
        allow_failed_retry: bool = False,
    ) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        for operation in plan:
            self.journal.persist_plan(operation)
            existing = self.journal.state(operation.operation_id)
            if not operation.executable:
                results.append(ExecutionResult(operation, existing, "NOT_APPLICABLE", error="; ".join(operation.warnings)))
                continue
            if existing in {OperationState.SUCCEEDED, OperationState.VERIFIED}:
                results.append(ExecutionResult(operation, existing, "ALREADY_SUCCEEDED", error="Operation already completed"))
                continue
            if existing in {OperationState.APPLYING, OperationState.UNKNOWN_RESULT, OperationState.VERIFY_REQUIRED}:
                results.append(ExecutionResult(operation, existing, "BLOCKED", error="Existing unfinished or ambiguous operation"))
                continue
            if existing is OperationState.FAILED and not allow_failed_retry:
                results.append(ExecutionResult(operation, existing, "BLOCKED", error="Failed operation requires explicit retry approval"))
                continue
            self.journal.transition(operation.operation_id, OperationState.APPLYING)
            try:
                response = self._create(operation)
            except AmbiguousMutationResult as exc:
                self.journal.transition(operation.operation_id, OperationState.UNKNOWN_RESULT, str(exc))
                self.journal.record_verification(operation.operation_id, OperationState.VERIFY_REQUIRED, "NONE", {})
                results.append(ExecutionResult(operation, OperationState.UNKNOWN_RESULT, "VERIFY_REQUIRED", error=str(exc)))
                continue
            except RemoteRejectedError as exc:
                self.journal.transition(operation.operation_id, OperationState.FAILED, str(exc))
                results.append(ExecutionResult(operation, OperationState.FAILED, "NOT_VERIFIED", error=str(exc)))
                continue
            except Exception as exc:  # a client runtime failure has unknown delivery semantics
                self.journal.transition(operation.operation_id, OperationState.UNKNOWN_RESULT, f"{type(exc).__name__}: {exc}")
                self.journal.record_verification(operation.operation_id, OperationState.VERIFY_REQUIRED, "NONE", {})
                results.append(ExecutionResult(operation, OperationState.UNKNOWN_RESULT, "VERIFY_REQUIRED", error=str(exc)))
                continue
            self.journal.transition(operation.operation_id, OperationState.SUCCEEDED, response=response)
            campaign_id = _campaign_id(response)
            if verify is None:
                self.journal.record_verification(operation.operation_id, OperationState.SUCCEEDED, "NOT_VERIFIED", {})
                results.append(ExecutionResult(operation, OperationState.SUCCEEDED, "NOT_VERIFIED", campaign_id))
                continue
            try:
                verified, observed = verify(operation)
            except Exception as exc:
                self.journal.record_verification(operation.operation_id, OperationState.VERIFY_REQUIRED, "VERIFY_ERROR", {"error": str(exc)})
                results.append(ExecutionResult(operation, OperationState.SUCCEEDED, "VERIFY_REQUIRED", campaign_id, str(exc)))
                continue
            verification_state = OperationState.VERIFIED if verified else OperationState.VERIFY_REQUIRED
            self.journal.record_verification(operation.operation_id, verification_state, "UI_OBSERVED", observed)
            if verified:
                self.journal.transition(operation.operation_id, OperationState.VERIFIED)
            results.append(ExecutionResult(operation, verification_state if verified else OperationState.SUCCEEDED, "VERIFIED" if verified else "VERIFY_REQUIRED", campaign_id))
        return results


class SalesService(_CreateService):
    operation_type = OperationType.CREATE_SALES
    intent_key = "fee"

    def plan_create(self, items: list[dict[str, object]], observed_skus: set[str], *, run_id: str | None = None, date: str) -> list[PlannedOperation]:
        return self._plan(items, observed_skus, SourceQuality.UI_OBSERVED, run_id=run_id, date=date)

    def _create(self, operation: PlannedOperation) -> dict[str, Any]:
        return self.client.create_campaign(
            campaign_name=str(operation.intent["campaign_name"]), offer_id=str(operation.intent["offer_id"]), bid=float(operation.intent["fee"]),
        )

    def plan_fee_update(self, records: list[dict[str, object]], fee: float, *, run_id: str | None = None) -> list[PlannedOperation]:
        run_id = run_id or str(uuid4())
        plan: list[PlannedOperation] = []
        seen: set[str] = set()
        for record in records:
            campaign_id = str(record.get("campaign_id", "")).strip()
            current = record.get("fee")
            target = {"campaign_id": campaign_id, "sku": record.get("sku"), "name": record.get("name")}
            intent = {"campaign_id": campaign_id, "requested_fee": fee, "current_fee": current}
            warnings = ["Campaign identity is UI_OBSERVED, not factual."]
            disposition = PlanDisposition.CREATE
            if not campaign_id or not 0 < fee <= 100:
                disposition, warnings = PlanDisposition.REVIEW, ["Invalid campaign ID or requested fee"]
            elif campaign_id in seen:
                disposition, warnings = PlanDisposition.SKIP, ["Duplicate campaign ID in input"]
            elif current is not None and float(current) == fee:
                disposition, warnings = PlanDisposition.SKIP, ["Observed fee already equals requested fee"]
            seen.add(campaign_id)
            plan.append(PlannedOperation(operation_id(OperationType.UPDATE_SALES_FEE, target, intent), run_id, OperationType.UPDATE_SALES_FEE, target, intent, SourceQuality.UI_OBSERVED, disposition, tuple(warnings)))
        return plan

    def plan_delete(self, records: list[dict[str, object]], *, run_id: str | None = None) -> list[PlannedOperation]:
        run_id = run_id or str(uuid4())
        seen: set[str] = set()
        plan = []
        for record in records:
            campaign_id = str(record.get("campaign_id", "")).strip()
            target = {"campaign_id": campaign_id, "sku": record.get("sku"), "name": record.get("name")}
            disposition = PlanDisposition.CREATE if campaign_id and campaign_id not in seen else PlanDisposition.REVIEW
            warnings = ("Campaign identity is UI_OBSERVED, not factual.",) if disposition is PlanDisposition.CREATE else ("Missing or duplicate campaign ID",)
            seen.add(campaign_id)
            plan.append(PlannedOperation(operation_id(OperationType.DELETE_SALES, target, {}), run_id, OperationType.DELETE_SALES, target, {}, SourceQuality.UI_OBSERVED, disposition, warnings, True))
        return plan

    def apply_fee_update_plan(self, plan: list[PlannedOperation], *, verify=None) -> list[ExecutionResult]:
        return self._apply_mutations(plan, lambda op: self.client.update_campaign_fee(str(op.target["campaign_id"]), float(op.intent["requested_fee"])), verify)

    def apply_delete_plan(self, plan: list[PlannedOperation], *, verify=None) -> list[ExecutionResult]:
        return self._apply_mutations(plan, lambda op: self.client.delete_campaign(str(op.target["campaign_id"])), verify)

    def _apply_mutations(self, plan, request, verify):
        results = []
        for operation in plan:
            self.journal.persist_plan(operation)
            existing = self.journal.state(operation.operation_id)
            if not operation.executable or existing in {OperationState.VERIFIED, OperationState.SUCCEEDED, OperationState.APPLYING, OperationState.UNKNOWN_RESULT, OperationState.VERIFY_REQUIRED}:
                results.append(ExecutionResult(operation, existing, "BLOCKED" if operation.executable else "NOT_APPLICABLE", error="Recovery or non-executable plan"))
                continue
            self.journal.transition(operation.operation_id, OperationState.APPLYING)
            try:
                request(operation)
            except RemoteRejectedError as exc:
                self.journal.transition(operation.operation_id, OperationState.FAILED, str(exc))
                results.append(ExecutionResult(operation, OperationState.FAILED, "NOT_VERIFIED", error=str(exc)))
                continue
            except Exception as exc:
                self.journal.transition(operation.operation_id, OperationState.UNKNOWN_RESULT, str(exc))
                self.journal.record_verification(operation.operation_id, OperationState.VERIFY_REQUIRED, "NONE", {})
                results.append(ExecutionResult(operation, OperationState.UNKNOWN_RESULT, "VERIFY_REQUIRED", error=str(exc)))
                continue
            self.journal.transition(operation.operation_id, OperationState.SUCCEEDED)
            try:
                verified, observed = verify(operation) if verify else (False, {})
            except Exception as exc:
                verified, observed = False, {"error": str(exc)}
            state = OperationState.VERIFIED if verified else OperationState.VERIFY_REQUIRED
            self.journal.record_verification(operation.operation_id, state, "UI_OBSERVED" if verify else "NOT_VERIFIED", observed)
            if verified:
                self.journal.transition(operation.operation_id, state)
            results.append(ExecutionResult(operation, state if verified else OperationState.SUCCEEDED, "VERIFIED" if verified else "NOT_VERIFIED"))
        return results


class ShowsService(_CreateService):
    operation_type = OperationType.CREATE_SHOWS
    intent_key = "daily_limit"

    def plan_create(self, items: list[dict[str, object]], history_skus: set[str], *, run_id: str | None = None, date: str) -> list[PlannedOperation]:
        return self._plan(items, history_skus, SourceQuality.LOCAL_HISTORY, run_id=run_id, date=date)

    def plan_create_from_inventory(self, items, records, *, run_id: str | None = None, date: str):
        from .shows_inventory import shows_duplicate_disposition

        plan = self._plan(items, set(), SourceQuality.UI_OBSERVED, run_id=run_id, date=date)
        result = []
        for operation in plan:
            disposition, status = shows_duplicate_disposition(records, str(operation.target["sku"]))
            if operation.disposition is not PlanDisposition.CREATE:
                result.append(operation)
                continue
            if disposition == "CREATE":
                result.append(operation)
            elif disposition == "SKIP":
                result.append(replace(operation, disposition=PlanDisposition.SKIP, warnings=(f"Active Shows campaign: {status}",)))
            else:
                result.append(replace(operation, disposition=PlanDisposition.REVIEW, warnings=(f"Shows campaign status requires review: {status or 'ambiguous'}",)))
        return result

    def _create(self, operation: PlannedOperation) -> dict[str, Any]:
        return self.client.create_campaign(
            campaign_name=str(operation.intent["campaign_name"]), offer_id=str(operation.intent["offer_id"]), daily_limit=int(operation.intent["daily_limit"]),
        )
