from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class OperationType(str, Enum):
    CREATE_SALES = "CREATE_SALES"
    CREATE_SHOWS = "CREATE_SHOWS"
    UPDATE_SALES_FEE = "UPDATE_SALES_FEE"
    DELETE_SALES = "DELETE_SALES"


class OperationState(str, Enum):
    PLANNED = "PLANNED"
    APPLYING = "APPLYING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"
    VERIFY_REQUIRED = "VERIFY_REQUIRED"
    VERIFIED = "VERIFIED"


class PlanDisposition(str, Enum):
    CREATE = "CREATE"
    SKIP = "SKIP"
    REVIEW = "REVIEW"


class SourceQuality(str, Enum):
    FACTUAL = "FACTUAL"
    UI_OBSERVED = "UI_OBSERVED"
    LOCAL_HISTORY = "LOCAL_HISTORY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class PlannedOperation:
    operation_id: str
    run_id: str
    operation_type: OperationType
    target: dict[str, Any]
    intent: dict[str, Any]
    source_quality: SourceQuality
    disposition: PlanDisposition = PlanDisposition.CREATE
    warnings: tuple[str, ...] = ()
    destructive: bool = False

    @property
    def executable(self) -> bool:
        return self.disposition is PlanDisposition.CREATE


def operation_id(operation_type: OperationType, target: dict[str, Any], intent: dict[str, Any]) -> str:
    canonical = json.dumps({"type": operation_type.value, "target": target, "intent": intent}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
