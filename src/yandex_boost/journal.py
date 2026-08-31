from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .operations import OperationState, PlannedOperation


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationJournal:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
        if self.connection.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0] == 0:
            self.connection.execute("INSERT INTO schema_version VALUES (1)")
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, command TEXT, status TEXT, started_at TEXT, finished_at TEXT, input_json TEXT);
        CREATE TABLE IF NOT EXISTS operations (operation_id TEXT PRIMARY KEY, run_id TEXT, type TEXT, target_json TEXT, intent_json TEXT, source_quality TEXT, state TEXT, destructive INTEGER, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS attempts (operation_id TEXT, number INTEGER, started_at TEXT, finished_at TEXT, outcome TEXT, error TEXT, response_json TEXT, PRIMARY KEY(operation_id, number));
        CREATE TABLE IF NOT EXISTS verifications (operation_id TEXT PRIMARY KEY, state TEXT, source TEXT, observed_json TEXT, observed_at TEXT);
        """)
        self.connection.commit()

    def start_run(self, run_id: str, command: str, input_snapshot: object) -> None:
        self.connection.execute("INSERT INTO runs VALUES (?, ?, 'RUNNING', ?, NULL, ?)", (run_id, command, _now(), json.dumps(input_snapshot)))
        self.connection.commit()

    def persist_plan(self, operation: PlannedOperation) -> None:
        now = _now()
        self.connection.execute("INSERT OR IGNORE INTO operations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (operation.operation_id, operation.run_id, operation.operation_type.value, json.dumps(operation.target), json.dumps(operation.intent), operation.source_quality.value, OperationState.PLANNED.value, int(operation.destructive), now, now))
        self.connection.commit()

    def state(self, operation_id: str) -> OperationState | None:
        row = self.connection.execute(
            "SELECT state FROM operations WHERE operation_id=?", (operation_id,)
        ).fetchone()
        return OperationState(row[0]) if row else None

    def transition(
        self, operation_id: str, state: OperationState, error: str | None = None,
        response: object | None = None,
    ) -> None:
        self.connection.execute("UPDATE operations SET state=?, updated_at=? WHERE operation_id=?", (state.value, _now(), operation_id))
        if error is not None or response is not None:
            row = self.connection.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM attempts WHERE operation_id=?", (operation_id,)).fetchone()
            self.connection.execute("INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?)", (operation_id, row[0], _now(), _now(), state.value, error, json.dumps(response)))
        self.connection.commit()

    def record_verification(
        self, operation_id: str, state: OperationState, source: str, observed: object,
    ) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO verifications VALUES (?, ?, ?, ?, ?)",
            (operation_id, state.value, source, json.dumps(observed), _now()),
        )
        self.connection.commit()

    def unfinished(self) -> list[str]:
        return [row[0] for row in self.connection.execute("SELECT operation_id FROM operations WHERE state IN ('APPLYING','UNKNOWN_RESULT','VERIFY_REQUIRED')")]

    def close(self) -> None:
        self.connection.close()
