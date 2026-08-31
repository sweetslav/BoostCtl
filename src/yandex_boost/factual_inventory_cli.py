from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

from .factual_inventory import (
    UnsupportedFactualSalesBoostSchema,
    build_factual_inventory_diagnostic,
    load_factual_sales_boost_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a factual Sales Boost inventory diagnostic locally.")
    parser.add_argument("input_report", type=Path)
    parser.add_argument("output_file", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        records = load_factual_sales_boost_report(args.input_report)
        _write_json(build_factual_inventory_diagnostic(records), args.output_file, args.force)
    except (OSError, UnsupportedFactualSalesBoostSchema, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Factual Sales Boost diagnostic written to: {args.output_file}")
    return 0


def _write_json(value: object, path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise ValueError(f"Output file already exists: {path}. Use --force to overwrite it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write("\n")
            temp_path = Path(file.name)
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
