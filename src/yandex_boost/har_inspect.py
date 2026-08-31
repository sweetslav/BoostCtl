from __future__ import annotations

import argparse
import base64
import binascii
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .captures import REDACTED, contains_unredacted_secret_values, is_secret_key, sanitize_capture

_RELATED_PATH_PARTS = ("sales-boost", "salesboost", "monetization", "salescampaign")
_FIELD_ALIASES = {
    "campaignid": "seller_page_campaign_id",
    "salescampaignid": "sales_campaign_id",
    "strategyid": "strategy_id",
    "name": "name",
    "status": "status",
    "state": "state",
    "sku": "sku",
    "skus": "skus",
    "offerid": "offer_id",
    "offerids": "offer_ids",
    "fee": "fee",
    "bid": "bid",
    "costmodel": "cost_model",
    "dailylimit": "daily_limit",
    "sourceid": "source_id",
    "sourcetype": "source_type",
    "widgetnames": "widget_names",
    "statisticswidget": "statistics_widget",
    "id": "id",
}


class HarInspectionError(ValueError):
    pass


def inspect_har(input_path: Path, output_path: Path, *, force: bool = False) -> None:
    har = _load_har(input_path)
    report = build_har_report(har)
    _write_report(report, output_path, force=force)


def build_har_report(har: object) -> dict[str, object]:
    entries = _har_entries(har)
    inspected_entries = [
        _inspect_entry(index, entry)
        for index, entry in enumerate(entries)
        if isinstance(entry, dict) and _is_related_entry(entry)
    ]
    summary = _build_summary(entries, inspected_entries)
    return {"summary": summary, "entries": inspected_entries}


def _har_entries(har: object) -> list[object]:
    if not isinstance(har, dict):
        raise HarInspectionError("Malformed HAR: root must be an object.")
    log = har.get("log")
    if not isinstance(log, dict) or not isinstance(log.get("entries"), list):
        raise HarInspectionError("Malformed HAR: log.entries must be a list.")
    return log["entries"]


def _is_related_entry(entry: dict[object, object]) -> bool:
    request = entry.get("request")
    if not isinstance(request, dict):
        return False
    url = request.get("url")
    if not isinstance(url, str):
        return False
    normalized = url.casefold()
    if any(part in normalized for part in _RELATED_PATH_PARTS):
        return True
    return ("campaign" in normalized or "strategy" in normalized) and _contains_sales_boost_context(entry)


def _contains_sales_boost_context(value: object) -> bool:
    if isinstance(value, dict):
        return any(_contains_sales_boost_context(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_sales_boost_context(item) for item in value)
    return isinstance(value, str) and any(part in value.casefold() for part in _RELATED_PATH_PARTS)


def _inspect_entry(index: int, entry: dict[object, object]) -> dict[str, object]:
    request = entry.get("request")
    request = request if isinstance(request, dict) else {}
    response = entry.get("response")
    response = response if isinstance(response, dict) else {}
    url = request.get("url") if isinstance(request.get("url"), str) else ""
    safe_url, query_params, pathname = _sanitize_url(url)
    request_data, request_error = _parse_post_data(request.get("postData"))
    response_json, response_error, content_type, body_size = _parse_response(response)
    evidence = _collect_evidence(request_data, response_json)
    inspected: dict[str, object] = {
        "ordinal": index + 1,
        "index": index,
        "method": request.get("method") if isinstance(request.get("method"), str) else "",
        "url": safe_url,
        "pathname": pathname,
        "query_params": query_params,
        "request_post_data": request_data,
        "response_status": response.get("status") if isinstance(response.get("status"), int) else None,
        "response_content_type": content_type,
        "response_json": response_json,
        "response_body_size": body_size,
        "detected_fields": evidence["detected_fields"],
        "evidence": evidence,
    }
    if request_error is not None:
        inspected["request_parse_error"] = request_error
    if response_error is not None:
        inspected["response_parse_error"] = response_error
    return inspected


def _sanitize_url(url: str) -> tuple[str, list[dict[str, str]], str]:
    parts = urlsplit(url)
    query_params = [
        {"name": key, "value": REDACTED if is_secret_key(key) else value}
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    query = urlencode([(item["name"], item["value"]) for item in query_params])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, "")), query_params, parts.path


def _parse_post_data(post_data: object) -> tuple[object | None, str | None]:
    if not isinstance(post_data, dict):
        return None, None
    text = post_data.get("text")
    if not isinstance(text, str):
        return None, None
    try:
        return sanitize_capture(json.loads(text)), None
    except json.JSONDecodeError:
        return None, "invalid_json"


def _parse_response(response: dict[object, object]) -> tuple[object | None, str | None, str | None, int | None]:
    content = response.get("content")
    if not isinstance(content, dict):
        return None, None, None, None
    content_type = content.get("mimeType") if isinstance(content.get("mimeType"), str) else None
    body_size = content.get("size") if isinstance(content.get("size"), int) else None
    text = content.get("text")
    if not isinstance(text, str):
        return None, None, content_type, body_size
    if content.get("encoding") == "base64":
        try:
            text = base64.b64decode(text, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None, "invalid_base64", content_type, body_size
    try:
        return sanitize_capture(json.loads(text)), None, content_type, body_size
    except json.JSONDecodeError:
        return None, "invalid_json", content_type, body_size


def _collect_evidence(*values: object) -> dict[str, object]:
    fields: set[str] = set()
    campaign_ids: set[str] = set()
    numeric_candidate_ids: set[str] = set()
    widget_names: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                key_text = str(key)
                normalized = "".join(char for char in key_text.casefold() if char.isalnum())
                alias = _FIELD_ALIASES.get(normalized)
                if alias is not None:
                    fields.add(alias)
                    if alias in {"sales_campaign_id", "strategy_id"} and isinstance(item, (str, int)):
                        campaign_ids.add(str(item))
                    if alias == "widget_names":
                        widget_names.update(_string_values(item))
                if key_text.isdigit():
                    numeric_candidate_ids.add(key_text)
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    for value in values:
        visit(value)

    has_product = bool({"sku", "skus", "offer_id", "offer_ids"} & fields)
    has_pricing = bool({"fee", "bid"} & fields)
    has_status = bool({"status", "state"} & fields)
    reasons: list[str] = []
    score = 0
    if campaign_ids and "name" in fields:
        reasons.append("campaign_id_and_name")
        score += 3
    if campaign_ids and has_status:
        reasons.append("campaign_id_and_status")
        score += 3
    if "name" in fields and has_product:
        reasons.append("name_and_sku_or_offer_id")
        score += 3
    if has_product and has_pricing:
        reasons.append("sku_or_offer_id_and_fee_or_bid")
        score += 4
    if numeric_candidate_ids and {"sales_campaign_id", "strategy_id"} & fields:
        reasons.append("numeric_ids_with_campaign_structure")
        score += 2
    return {
        "campaign_ids": sorted(campaign_ids),
        "numeric_candidate_ids": sorted(numeric_candidate_ids),
        "widget_names": sorted(widget_names),
        "reasons": reasons,
        "score": score,
        "detected_fields": sorted(fields),
    }


def _string_values(value: object) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str)}
    return set()


def _build_summary(all_entries: list[object], entries: list[dict[str, object]]) -> dict[str, object]:
    get_entries = [entry for entry in entries if entry["method"] == "GET"]
    post_entries = [entry for entry in entries if entry["method"] == "POST"]
    evidence_entries = [(entry["index"], entry["evidence"]) for entry in entries]
    top_entries = sorted(
        (entry for entry in entries if int(entry["evidence"]["score"]) > 0),
        key=lambda entry: (-int(entry["evidence"]["score"]), int(entry["index"])),
    )[:10]
    return {
        "total_har_entries": len(all_entries),
        "candidate_sales_boost_entries": len(entries),
        "get_count": len(get_entries),
        "post_count": len(post_entries),
        "unique_endpoint_paths": sorted({str(entry["pathname"]) for entry in entries}),
        "widget_names_variants": sorted(
            {name for _, evidence in evidence_entries for name in evidence["widget_names"]}
        ),
        "entries_containing_statistics_widget": [
            index for index, evidence in evidence_entries if "statistics_widget" in evidence["detected_fields"]
        ],
        "entries_containing_candidate_campaign_ids": [
            index for index, evidence in evidence_entries if evidence["campaign_ids"]
        ],
        "entries_containing_names": [
            index for index, evidence in evidence_entries if "name" in evidence["detected_fields"]
        ],
        "entries_containing_sku_or_offer_id": [
            index
            for index, evidence in evidence_entries
            if {"sku", "skus", "offer_id", "offer_ids"} & set(evidence["detected_fields"])
        ],
        "entries_containing_fee_bid_or_status": [
            index
            for index, evidence in evidence_entries
            if {"fee", "bid", "status", "state"} & set(evidence["detected_fields"])
        ],
        "top_factual_inventory_candidates": [
            {
                "index": entry["index"],
                "method": entry["method"],
                "pathname": entry["pathname"],
                "score": entry["evidence"]["score"],
                "reasons": entry["evidence"]["reasons"],
            }
            for entry in top_entries
        ],
    }


def _load_har(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise HarInspectionError(f"Invalid HAR JSON: {path}") from exc
    except OSError as exc:
        raise HarInspectionError(f"Could not read HAR input: {path}") from exc


def _write_report(report: dict[str, object], output_path: Path, *, force: bool) -> None:
    if output_path.exists() and not force:
        raise HarInspectionError(f"Output file already exists: {output_path}. Use --force to overwrite it.")
    safe_report = sanitize_capture(report)
    if contains_unredacted_secret_values(safe_report):
        raise HarInspectionError("Internal error: sanitizer left unredacted secret values.")
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
            json.dump(safe_report, file, ensure_ascii=False, indent=2)
            file.write("\n")
            temp_path = Path(file.name)
        temp_path.replace(output_path)
    except OSError as exc:
        raise HarInspectionError(f"Could not write output file: {output_path}") from exc
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect a local HAR for Sales Boost inventory candidates.")
    parser.add_argument("input_file", type=Path)
    parser.add_argument("output_file", type=Path)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inspect_har(args.input_file, args.output_file, force=args.force)
    except HarInspectionError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"HAR inspection report written to: {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
