from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from .campaigns import CampaignRecord, CampaignSource, CampaignType


class UnsupportedFactualSalesBoostSchema(ValueError):
    pass


def load_factual_sales_boost_observations(report: object) -> list[CampaignRecord]:
    entries = _report_entries(report)
    records: list[CampaignRecord] = []
    recognized = False
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        request = _entry_context(entry)
        response = entry.get("response_json")
        if _is_empty_campaign_collection(response):
            recognized = True
        for detail in _campaign_detail_objects(response):
            recognized = True
            records.append(_record_from_detail(detail, request))
        nested = _nested_sales_campaign(response)
        if nested is not None:
            recognized = True
            detail = {**nested, "salesCampaignId": nested.get("id")}
            records.append(_record_from_detail(detail, request))
        supporting = _supporting_campaign_body(entry.get("request_post_data"), request)
        if supporting is not None:
            recognized = True
            records.append(_record_from_detail(supporting, request))
    if not recognized:
        raise UnsupportedFactualSalesBoostSchema("No supported factual Sales Boost campaign schema found.")
    return [_merge_records(group) for _, group in sorted(_group_by_sales_campaign(records).items())]


def _group_by_sales_campaign(records: list[CampaignRecord]) -> dict[str, list[CampaignRecord]]:
    grouped: dict[str, list[CampaignRecord]] = defaultdict(list)
    for record in records:
        if record.sales_campaign_id is not None:
            grouped[record.sales_campaign_id].append(record)
    return grouped


def _merge_records(records: list[CampaignRecord]) -> CampaignRecord:
    merged = records[0]
    for record in records[1:]:
        values = {name: getattr(merged, name) or getattr(record, name) for name in (
            "name", "status", "raw_status", "strategy_id", "business_id", "fee", "campaign_data_type",
            "subsidy_type", "is_autostrategy", "offer_service", "cost_model", "source_id", "source_type",
            "legacy_name_hint", "created_at", "updated_at"
        )}
        values["offer_ids"] = tuple(sorted(set(merged.offer_ids) | set(record.offer_ids)))
        merged = replace(merged, **values)
    return merged


def load_factual_sales_boost_report(path: Path) -> list[CampaignRecord]:
    try:
        with path.open("r", encoding="utf-8") as file:
            return load_factual_sales_boost_observations(json.load(file))
    except json.JSONDecodeError as exc:
        raise UnsupportedFactualSalesBoostSchema(f"Invalid factual inventory JSON: {path}") from exc
    except OSError as exc:
        raise UnsupportedFactualSalesBoostSchema(f"Could not read factual inventory input: {path}") from exc


def build_factual_inventory_diagnostic(records: list[CampaignRecord]) -> dict[str, object]:
    by_campaign: dict[str, list[CampaignRecord]] = defaultdict(list)
    offer_campaigns: dict[str, set[str]] = defaultdict(set)
    for record in records:
        if record.sales_campaign_id is not None:
            by_campaign[record.sales_campaign_id].append(record)
            for offer_id in record.offer_ids:
                offer_campaigns[offer_id].add(record.sales_campaign_id)
    campaigns = []
    conflicts = []
    for campaign_id, observations in sorted(by_campaign.items()):
        values = {
            "names": sorted({value for record in observations if (value := record.name) is not None}),
            "offer_ids": sorted({offer for record in observations for offer in record.offer_ids}),
            "fees": sorted({record.fee for record in observations if record.fee is not None}),
            "statuses": sorted({record.status for record in observations if record.status is not None}),
        }
        missing = [key for key, value in values.items() if not value]
        campaign = {"sales_campaign_id": campaign_id, **values, "missing_fields": missing, "source_quality": "factual_har"}
        campaigns.append(campaign)
        if len(values["names"]) > 1 or len(values["offer_ids"]) > 1:
            conflicts.append(campaign)
    return {
        "summary": {
            "unique_factual_campaigns": len(by_campaign),
            "unique_offer_ids": len(offer_campaigns),
            "campaign_ids_without_offer_id": [
                campaign["sales_campaign_id"] for campaign in campaigns if not campaign["offer_ids"]
            ],
        },
        "campaigns": campaigns,
        "conflicting_observations": conflicts,
        "offer_ids_in_multiple_campaigns": {
            offer: sorted(campaigns) for offer, campaigns in sorted(offer_campaigns.items()) if len(campaigns) > 1
        },
    }


def _report_entries(report: object) -> list[object]:
    if not isinstance(report, dict) or not isinstance(report.get("entries"), list):
        raise UnsupportedFactualSalesBoostSchema("Factual inventory report must contain an entries list.")
    return report["entries"]


def _campaign_detail_objects(value: object) -> list[dict[object, object]]:
    found: list[dict[object, object]] = []
    if isinstance(value, dict):
        if _identifier(value) is not None and isinstance(value.get("name"), str):
            found.append(value)
        for item in value.values():
            found.extend(_campaign_detail_objects(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_campaign_detail_objects(item))
    return found


def _record_from_detail(detail: dict[object, object], request: object) -> CampaignRecord:
    context = request if isinstance(request, dict) else {}
    sales_campaign_id = _identifier(detail)
    assert sales_campaign_id is not None
    name = _text(detail, "name")
    return CampaignRecord(
        campaign_id=None,
        campaign_type=CampaignType.SALES,
        source=CampaignSource.FACTUAL_HAR,
        name=name,
        status=_text(detail, "status") or _text(detail, "state"),
        created_at=_text(detail, "createdAt") or _text(detail, "created_at"),
        updated_at=_text(detail, "updatedAt") or _text(detail, "updated_at"),
        raw_status=_text(detail, "status") or _text(detail, "state"),
        sales_campaign_id=sales_campaign_id,
        strategy_id=_text(detail, "strategyId") or _text(context, "strategyId"),
        business_id=_text(context, "businessId") or _text(detail, "businessId"),
        offer_ids=_offer_ids(detail),
        fee=_number(detail.get("fee")) or _equal_fee(detail) or _sku_fee(detail),
        campaign_data_type=_text(detail, "type"),
        subsidy_type=_text(detail, "subsidyType"),
        is_autostrategy=detail.get("isAutostrategy") if isinstance(detail.get("isAutostrategy"), bool) else None,
        offer_service=_text(detail, "offerService"),
        cost_model=_text(detail, "costModel") or _text(context, "costModel"),
        source_id=_text(detail, "sourceId") or _text(context, "sourceId"),
        source_type=_text(detail, "sourceType") or _text(context, "sourceType"),
        legacy_name_hint=_legacy_name_hint(name),
    )


def _identifier(value: dict[object, object]) -> str | None:
    return _text(value, "salesCampaignId") or _text(value, "strategyId")


def _text(value: dict[object, object], key: str) -> str | None:
    item = value.get(key)
    return str(item) if isinstance(item, (str, int)) else None


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _offer_ids(value: dict[object, object]) -> tuple[str, ...]:
    direct = _text(value, "offerId")
    multiple = value.get("offerIds")
    if isinstance(multiple, list):
        return tuple(str(item) for item in multiple if isinstance(item, (str, int)))
    nested = value.get("data")
    if isinstance(nested, dict) and isinstance(nested.get("skus"), list):
        return tuple(
            str(item["offerId"])
            for item in nested["skus"]
            if isinstance(item, dict) and isinstance(item.get("offerId"), (str, int))
        )
    return (direct,) if direct is not None else ()


def _equal_fee(value: dict[object, object]) -> float | None:
    minimum = _number(value.get("minFee"))
    maximum = _number(value.get("maxFee"))
    return minimum if minimum is not None and minimum == maximum else None


def _sku_fee(value: dict[object, object]) -> float | None:
    data = value.get("data")
    if isinstance(data, dict) and isinstance(data.get("skus"), list):
        for item in data["skus"]:
            if isinstance(item, dict) and (fee := _number(item.get("fee"))) is not None:
                return fee
    return None


def _legacy_name_hint(name: str | None) -> str | None:
    return name.split("|", 1)[0].strip() if name is not None and "|" in name else None


def _is_empty_campaign_collection(value: object) -> bool:
    return isinstance(value, dict) and value.get("campaigns") == []


def _nested_sales_campaign(value: object) -> dict[object, object] | None:
    if not isinstance(value, dict):
        return None
    page = value.get("page")
    if not isinstance(page, dict):
        return None
    info = page.get("salesCampaignInfo")
    return info.get("salesCampaign") if isinstance(info, dict) and isinstance(info.get("salesCampaign"), dict) else None


def _entry_context(entry: dict[object, object]) -> dict[object, object]:
    context: dict[object, object] = {}
    for item in entry.get("query_params", []):
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            context[item["name"]] = item.get("value")
    request = entry.get("request_post_data")
    if isinstance(request, dict):
        context.update(request)
        for value in _walk_values(request):
            if isinstance(value, dict):
                context.update({key: item for key, item in value.items() if isinstance(key, str)})
    return context


def _supporting_campaign_body(value: object, context: dict[object, object]) -> dict[object, object] | None:
    campaign_id = _text(context, "salesCampaignId")
    if campaign_id is None:
        return None
    for item in _walk_values(value):
        if isinstance(item, dict) and isinstance(item.get("data"), dict) and isinstance(item.get("name"), str):
            detail = dict(item)
            detail["salesCampaignId"] = campaign_id
            return detail
    return None


def _walk_values(value: object):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_values(item)
