from __future__ import annotations

from typing import Any, Callable
from uuid import uuid4

from .create_services import ExecutionResult, SalesService, ShowsService
from .journal import OperationJournal
from .operations import OperationState, PlannedOperation


def start_journal(path: Any, command: str, items: list[dict[str, object]]) -> tuple[OperationJournal, str]:
    run_id = str(uuid4())
    journal = OperationJournal(path)
    journal.start_run(run_id, command, items)
    return journal, run_id


def plan_sales_create(client: Any, journal_path: Any, items: list[dict[str, object]], observed_skus: set[str], date: str) -> tuple[OperationJournal, list[PlannedOperation]]:
    journal, run_id = start_journal(journal_path, "sales.create", items)
    return journal, SalesService(journal, client).plan_create(items, observed_skus, run_id=run_id, date=date)


def plan_shows_create(client: Any, journal_path: Any, items: list[dict[str, object]], history_skus: set[str], date: str) -> tuple[OperationJournal, list[PlannedOperation]]:
    journal, run_id = start_journal(journal_path, "shows.create", items)
    return journal, ShowsService(journal, client).plan_create(items, history_skus, run_id=run_id, date=date)


def apply_sales_create(journal: OperationJournal, client: Any, plan: list[PlannedOperation], verify: Callable[[PlannedOperation], tuple[bool, object]] | None, *, allow_failed_retry: bool = False) -> list[ExecutionResult]:
    return SalesService(journal, client).apply_create_plan(plan, verify=verify, allow_failed_retry=allow_failed_retry)


def apply_shows_create(journal: OperationJournal, client: Any, plan: list[PlannedOperation]) -> list[ExecutionResult]:
    return ShowsService(journal, client).apply_create_plan(plan)


def has_apply_failure(results: list[ExecutionResult]) -> bool:
    return any(result.state in {OperationState.FAILED, OperationState.UNKNOWN_RESULT} for result in results)
