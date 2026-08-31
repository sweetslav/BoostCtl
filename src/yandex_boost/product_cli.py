# ruff: noqa: E701
from __future__ import annotations

import csv
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path.cwd()
DB = ROOT / "local_data" / "boostctl.db"


def _run(*args: str) -> int:
    return subprocess.call([sys.executable, "-m", *args], cwd=ROOT)


def _choose(prompt: str) -> str:
    return input(prompt).strip()


def history(export: bool = False) -> None:
    if not DB.exists():
        print("История операций пока пуста.")
        return
    connection = sqlite3.connect(DB)
    rows = connection.execute("SELECT run_id, command, started_at, status FROM runs ORDER BY started_at DESC LIMIT 20").fetchall()
    if export:
        output = ROOT / "local_data" / "reports" / "operation_history.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            writer.writerow(["run_id", "command", "started_at", "status", "operation_id", "state", "target", "intent"])
            for run in rows:
                for operation in connection.execute("SELECT operation_id, state, target_json, intent_json FROM operations WHERE run_id=?", (run[0],)):
                    writer.writerow([*run, *operation])
        print(f"Экспорт: {output}")
    else:
        for run in rows:
            counts = connection.execute("SELECT state, COUNT(*) FROM operations WHERE run_id=? GROUP BY state", (run[0],)).fetchall()
            print(f"{run[2]} | {run[1]} | {dict(counts)} | {run[0]}")
        recovery = connection.execute("SELECT operation_id, type, state, updated_at FROM operations WHERE state IN ('APPLYING','UNKNOWN_RESULT','VERIFY_REQUIRED')").fetchall()
        for row in recovery:
            print(f"ТРЕБУЕТ ПРОВЕРКИ: {row[1]} {row[0]} ({row[2]}, {row[3]}). Автоматический повтор заблокирован.")
    connection.close()


def sales_menu() -> None:
    while True:
        print("\nБуст продаж\n1. Проверить / подготовить\n2. Создать недостающие\n3. Изменить ставки\n4. Удалить кампании\n5. Выгрузить кампании\n0. Назад")
        choice = _choose("> ")
        if choice == "1": _run("yandex_boost", "preflight")
        elif choice == "2": _run("yandex_boost", "run", "--dry-run")
        elif choice == "3": _run("yandex_boost", "update-bids-preview", "--fee", _choose("Ставка: "))
        elif choice == "4": _run("yandex_boost", "delete-preview")
        elif choice == "5": _run("yandex_boost", "export")
        elif choice == "0": return


def shows_menu() -> None:
    while True:
        print("\nБуст показов\n1. Проверить / подготовить\n2. Создать кампании\n3. История созданий\n0. Назад")
        choice = _choose("> ")
        if choice == "1" or choice == "2": _run("yandex_boost.shows_create", "--dry-run")
        elif choice == "3": history()
        elif choice == "0": return


def main() -> int:
    while True:
        print("\nBoostCtl\n1. Буст продаж\n2. Буст показов\n3. История операций\n4. Диагностика\n0. Выход")
        choice = _choose("> ")
        if choice == "1": sales_menu()
        elif choice == "2": shows_menu()
        elif choice == "3": history(_choose("Экспорт CSV? [y/N]: ").lower() == "y")
        elif choice == "4": print("Диагностика: RUN_SALES_DIAGNOSTICS.bat (advanced/local only).")
        elif choice == "0": return 0


if __name__ == "__main__":
    raise SystemExit(main())
