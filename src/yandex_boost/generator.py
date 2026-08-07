from __future__ import annotations

import json
from pathlib import Path


class InputFormatError(ValueError):
    pass


def _parse_bid(value: str, line_number: int) -> float:
    cleaned = value.strip().replace(",", ".")
    try:
        bid = float(cleaned)
    except ValueError as exc:
        raise InputFormatError(
            f"Строка {line_number}: ставка {value!r} не является числом."
        ) from exc

    if not 0 < bid <= 100:
        raise InputFormatError(
            f"Строка {line_number}: ставка должна быть больше 0 и не больше 100."
        )
    return bid


def parse_campaign_input(text: str) -> list[dict[str, object]]:
    campaigns: list[dict[str, object]] = []
    seen: dict[str, int] = {}

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        # Основной формат: SKU;СТАВКА
        # Также поддерживаем TAB, чтобы можно было вставлять прямо из Excel.
        if ";" in line:
            sku, bid_raw = line.rsplit(";", 1)
        elif "\t" in line:
            sku, bid_raw = line.rsplit("\t", 1)
        else:
            raise InputFormatError(
                f"Строка {line_number}: ожидается формат SKU;СТАВКА. "
                f"Например: 2020488/1#1;5"
            )

        sku = sku.strip()
        if not sku:
            raise InputFormatError(f"Строка {line_number}: пустой SKU.")

        if sku in seen:
            raise InputFormatError(
                f"Строка {line_number}: дубль SKU {sku!r}. "
                f"Первое вхождение — строка {seen[sku]}."
            )

        bid = _parse_bid(bid_raw, line_number)
        seen[sku] = line_number
        campaigns.append({"sku": sku, "bid": bid})

    if not campaigns:
        raise InputFormatError("Во входном файле нет ни одной кампании.")

    return campaigns


def build_campaigns_json(input_path: Path, output_path: Path) -> list[dict[str, object]]:
    if not input_path.exists():
        raise FileNotFoundError(f"Не найден входной файл: {input_path}")

    campaigns = parse_campaign_input(input_path.read_text(encoding="utf-8-sig"))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".json.tmp")

    temp_path.write_text(
        json.dumps(campaigns, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(output_path)
    return campaigns
