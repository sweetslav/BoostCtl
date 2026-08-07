from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path.cwd()

MENU = {
    "1": ("Установить / обновить зависимости", "00_INSTALL.bat"),
    "2": ("Создать campaigns.json из списка SKU и ставок", "09_MAKE_CAMPAIGNS_JSON.bat"),
    "3": ("Проверить campaigns.json", "01_VALIDATE.bat"),
    "4": ("Предварительная проверка Яндекса", "02_PREFLIGHT.bat"),
    "5": ("Создать одну тестовую кампанию", "03_TEST_ONE.bat"),
    "6": ("Создать все новые кампании", "04_RUN_ALL.bat"),
    "7": ("Повторить только ошибки", "05_RETRY_ERRORS.bat"),
    "8": ("Выгрузить список кампаний из Яндекса", "06_EXPORT_CAMPAIGNS.bat"),
    "9": ("Проверить список кампаний на удаление", "07_DELETE_PREVIEW.bat"),
    "10": ("Удалить кампании из явного списка ID", "08_DELETE_CAMPAIGNS.bat"),
}


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_header() -> None:
    print("=" * 62)
    print("                         BoostCtl v1.3.1")
    print("                 Яндекс Маркет — Буст продаж")
    print("=" * 62)
    print()


def print_menu() -> None:
    print(" ПОДГОТОВКА")
    print("  [1] Установить / обновить зависимости")
    print("  [2] Подготовить campaigns.json")
    print("  [3] Проверить campaigns.json")
    print()
    print(" КАМПАНИИ")
    print("  [4] Предварительная проверка")
    print("  [5] Создать одну тестовую кампанию")
    print("  [6] Создать все новые кампании")
    print()
    print(" ОБСЛУЖИВАНИЕ")
    print("  [7] Повторить только ошибки")
    print("  [8] Выгрузить кампании")
    print("  [9] Проверить список на удаление")
    print(" [10] Удалить выбранные кампании")
    print()
    print("  [0] Выход")
    print()


def run_bat(filename: str, title: str) -> None:
    clear()
    print_header()
    print(title)
    print("-" * 62)
    print()
    result = subprocess.run(["cmd", "/c", filename], cwd=ROOT, check=False)
    print()
    print("-" * 62)
    print("ГОТОВО" if result.returncode == 0 else f"ЗАВЕРШЕНО С КОДОМ {result.returncode}")
    input("\nНажмите Enter, чтобы вернуться в меню...")


def main() -> int:
    while True:
        clear()
        print_header()
        print_menu()
        choice = input("Выберите действие: ").strip()

        if choice == "0":
            return 0

        item = MENU.get(choice)
        if item is None:
            print("\nНеизвестный пункт меню.")
            input("Нажмите Enter...")
            continue

        title, filename = item
        run_bat(filename, title)


if __name__ == "__main__":
    raise SystemExit(main())
