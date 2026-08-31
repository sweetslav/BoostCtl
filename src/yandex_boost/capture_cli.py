from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from .captures import contains_unredacted_secret_values, sanitize_capture


class CaptureIngestionError(ValueError):
    pass


def ingest_capture(input_path: Path, output_path: Path, *, force: bool = False) -> None:
    raw_capture = _load_json(input_path)
    if _is_fixture_capture_path(input_path) and contains_unredacted_secret_values(raw_capture):
        raise CaptureIngestionError("Refusing unsanitized input from the capture fixture directory.")
    write_sanitized_capture(sanitize_capture(raw_capture), output_path, force=force)


def write_sanitized_capture(capture: object, output_path: Path, *, force: bool = False) -> None:
    if output_path.exists() and not force:
        raise CaptureIngestionError(f"Output file already exists: {output_path}. Use --force to overwrite it.")
    if contains_unredacted_secret_values(capture):
        raise CaptureIngestionError("Internal error: sanitizer left unredacted secret values.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            json.dump(capture, file, ensure_ascii=False, indent=2)
            file.write("\n")
            temp_path = Path(file.name)
        temp_path.replace(output_path)
    except OSError as exc:
        raise CaptureIngestionError(f"Could not write output file: {output_path}") from exc
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def _load_json(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise CaptureIngestionError(f"Invalid JSON input: {path}") from exc
    except OSError as exc:
        raise CaptureIngestionError(f"Could not read input file: {path}") from exc


def _is_fixture_capture_path(path: Path) -> bool:
    fixture_dir = Path("tests/fixtures/yandex_captures").resolve()
    return path.resolve().is_relative_to(fixture_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sanitize a local DevTools JSON capture.")
    parser.add_argument("input_file", type=Path)
    parser.add_argument("output_file", type=Path)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output fixture.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ingest_capture(args.input_file, args.output_file, force=args.force)
    except CaptureIngestionError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Sanitized capture written to: {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
