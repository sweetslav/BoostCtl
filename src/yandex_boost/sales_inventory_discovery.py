from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "local_data" / "reports" / "sales_boost_inventory_report.json"
DEFAULT_OUTPUT = ROOT / "local_data" / "reports" / "sales_inventory_discovery.json"
_FIELDS = {
    "id",
    "salesCampaignId",
    "strategyId",
    "name",
    "status",
    "active",
    "fee",
    "bid",
    "offerId",
    "skus",
}


def build_discovery(report: object) -> dict[str, object]:
    entries = report.get("entries", []) if isinstance(report, dict) else []
    classified = [_classify(entry) for entry in entries if isinstance(entry, dict)]
    inventory = [entry for entry in classified if entry["classification"] == "inventory_candidate"]
    return {
        "summary": {
            "total_entries_scanned": len(entries),
            "sales_related_entries": len(classified),
            "inventory_candidates": len(inventory),
            "detail_candidates": sum(e["classification"] == "campaign_detail" for e in classified),
            "supporting_candidates": sum(
                e["classification"] == "campaign_supporting" for e in classified
            ),
            "statistics_candidates": sum(e["classification"] == "statistics" for e in classified),
            "full_inventory_found": bool(inventory),
            "top_inventory_candidates": inventory[:10],
            "possible_collection_paths": sorted(
                {p["path"] for e in inventory for p in e["collections"]}
            ),
            "possible_pagination_endpoints": [
                e["index"] for e in inventory if e["pagination_fields"]
            ],
            "candidate_strategy_id_sources": [
                e["index"] for e in inventory if e["strategy_id_fields"]
            ],
            "next_capture_candidates": sorted(
                classified, key=lambda e: -int(e["confidence_score"])
            )[:10],
        },
        "entries": classified,
    }


def _classify(entry: dict[str, object]) -> dict[str, object]:
    response = entry.get("response_json")
    path = str(entry.get("pathname", ""))
    resolver = next(
        (
            p.get("value")
            for p in entry.get("query_params", [])
            if isinstance(p, dict) and p.get("name") == "r"
        ),
        None,
    )
    collections = _collections(response)
    request = entry.get("request_post_data")
    request_keys = sorted(_keys(request))
    response_keys = sorted(response) if isinstance(response, dict) else []
    text = f"{path} {resolver or ''}".casefold()
    statistic = "statisticswidget" in str(request).casefold()
    detail = (
        isinstance(response, dict)
        and isinstance(response.get("page"), dict)
        and "salescampaigninfo" in str(response).casefold()
    )
    confirmed = (
        "salesboost" in text or "salescampaign" in text or "sales boost" in str(request).casefold()
    )
    valid = [
        c
        for c in collections
        if c["count"]
        and (
            "salesCampaignId" in c["fields"]
            or "strategyId" in c["fields"]
            or (confirmed and "id" in c["fields"])
        )
    ]
    classification = (
        "inventory_candidate"
        if confirmed and valid and not statistic and not detail
        else "campaign_detail"
        if detail
        else "statistics"
        if statistic
        else "campaign_supporting"
        if "salescampaign" in text
        else "unrelated"
    )
    reasons = (
        ["confirmed_sales_boost_list_context", "collection_has_strategy_identifier"]
        if classification == "inventory_candidate"
        else [classification]
    )
    return {
        "index": entry.get("index"),
        "method": entry.get("method"),
        "endpoint": path,
        "resolver": resolver,
        "classification": classification,
        "request_keys": request_keys,
        "response_top_level_keys": response_keys,
        "collections": valid if classification == "inventory_candidate" else collections,
        "pagination_fields": sorted(
            _find_fields(request, {"pageSize", "pageToken", "offset", "limit", "total", "count"})
        ),
        "strategy_id_fields": sorted(_find_fields(response, {"salesCampaignId", "strategyId"})),
        "confidence_score": 10
        if classification == "inventory_candidate"
        else 6
        if detail
        else 3
        if classification == "campaign_supporting"
        else 0,
        "reasons": reasons,
    }


def _collections(value: object, path: str = "response_json") -> list[dict[str, object]]:
    found = []
    if isinstance(value, list):
        fields = (
            set().union(*(_keys(item) for item in value if isinstance(item, dict)))
            if value
            else set()
        )
        found.append({"path": path, "count": len(value), "fields": sorted(fields & _FIELDS)})
        for i, item in enumerate(value):
            found.extend(_collections(item, f"{path}[{i}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(_collections(item, f"{path}.{key}"))
    return found


def _keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return {str(k) for k in value}
    return set()


def _find_fields(value: object, wanted: set[str]) -> set[str]:
    if isinstance(value, dict):
        return ({str(k) for k in value} & wanted) | set().union(
            *(_find_fields(v, wanted) for v in value.values())
        )
    if isinstance(value, list):
        return set().union(*(_find_fields(v, wanted) for v in value)) if value else set()
    return set()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover Sales Boost inventory endpoints from a sanitized HAR report."
    )
    parser.add_argument("input_file", type=Path, nargs="?", default=DEFAULT_INPUT)
    parser.add_argument("output_file", type=Path, nargs="?", default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.output_file.exists() and not args.force:
            raise ValueError(f"Output file already exists: {args.output_file}. Use --force.")
        report = json.loads(args.input_file.read_text(encoding="utf-8"))
        result = build_discovery(report)
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Sales inventory discovery written to: {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
