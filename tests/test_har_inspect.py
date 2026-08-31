import json
from pathlib import Path

import pytest

from yandex_boost.captures import contains_unredacted_secret_values
from yandex_boost.har_inspect import HarInspectionError, build_har_report, inspect_har


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "har" / "sales_boost_inspector.har"


def _fixture_har() -> object:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_build_har_report_discovers_sales_boost_candidates_and_scores_inventory():
    report = build_har_report(_fixture_har())

    assert report["summary"]["total_har_entries"] == 6
    assert report["summary"]["candidate_sales_boost_entries"] == 5
    assert report["summary"]["get_count"] == 3
    assert report["summary"]["post_count"] == 2
    assert report["summary"]["entries_containing_statistics_widget"] == [1]
    assert report["summary"]["entries_containing_candidate_campaign_ids"] == []
    assert report["summary"]["entries_containing_names"] == [2, 3, 4]
    assert report["summary"]["entries_containing_sku_or_offer_id"] == [2, 3]
    assert report["summary"]["entries_containing_fee_bid_or_status"] == [2, 3, 4]
    assert report["summary"]["top_factual_inventory_candidates"][0]["index"] == 3
    assert report["summary"]["top_factual_inventory_candidates"][0]["score"] >= 3


def test_har_report_sanitizes_headers_query_and_nested_request_data():
    report = build_har_report(_fixture_har())
    serialized = json.dumps(report)
    base64_entry = next(entry for entry in report["entries"] if entry["index"] == 4)

    assert base64_entry["url"].endswith("access_token=%3CREDACTED%3E&sku=SAFE-2")
    assert base64_entry["query_params"] == [
        {"name": "access_token", "value": "<REDACTED>"},
        {"name": "sku", "value": "SAFE-2"},
    ]
    polling_entry = next(entry for entry in report["entries"] if entry["index"] == 1)
    assert polling_entry["request_post_data"]["sk"] == "<REDACTED>"
    assert not contains_unredacted_secret_values(report)
    assert "fixture-cookie" not in serialized
    assert "fixture-set-cookie" not in serialized
    assert "fixture-session" not in serialized
    assert "fixture-token" not in serialized
    assert "fixture-sk" not in serialized


def test_har_report_decodes_base64_json_and_marks_statistics_ids_as_unconfirmed():
    report = build_har_report(_fixture_har())
    polling_entry = next(entry for entry in report["entries"] if entry["index"] == 1)
    base64_entry = next(entry for entry in report["entries"] if entry["index"] == 4)

    assert base64_entry["response_json"]["campaignId"] == "303"
    assert polling_entry["evidence"]["numeric_candidate_ids"] == ["123"]
    assert polling_entry["evidence"]["campaign_ids"] == []
    assert polling_entry["evidence"]["reasons"] == []


def test_har_report_excludes_seller_and_business_ids_from_sales_boost_campaign_ids():
    har = _fixture_har()
    har["log"]["entries"].append(
        {
            "request": {"method": "POST", "url": "https://example.test/sales-boost/detail"},
            "response": {
                "status": 200,
                "content": {
                    "mimeType": "application/json",
                    "text": '{"businessId":950637,"shopId":1,"partnerId":2,"campaignId":21930651,"salesCampaignId":10958486}',
                },
            },
        }
    )

    report = build_har_report(har)
    evidence = next(entry["evidence"] for entry in report["entries"] if entry["index"] == 6)

    assert evidence["campaign_ids"] == ["10958486"]


def test_har_report_keeps_malformed_response_as_safe_metadata():
    report = build_har_report(_fixture_har())
    broken_entry = next(entry for entry in report["entries"] if entry["index"] == 5)

    assert broken_entry["response_json"] is None
    assert broken_entry["response_parse_error"] == "invalid_json"
    assert "response_preview" not in broken_entry


def test_inspect_har_refuses_invalid_har_without_creating_output(tmp_path):
    input_path = tmp_path / "invalid.har"
    output_path = tmp_path / "report.json"
    input_path.write_text("{not-json}", encoding="utf-8")

    with pytest.raises(HarInspectionError, match="Invalid HAR JSON"):
        inspect_har(input_path, output_path)

    assert not output_path.exists()


def test_inspect_har_refuses_existing_output_unless_force(tmp_path):
    output_path = tmp_path / "report.json"
    output_path.write_text('{"existing": true}', encoding="utf-8")

    with pytest.raises(HarInspectionError, match="already exists"):
        inspect_har(FIXTURE_PATH, output_path)

    assert output_path.read_text(encoding="utf-8") == '{"existing": true}'
    inspect_har(FIXTURE_PATH, output_path, force=True)
    assert json.loads(output_path.read_text(encoding="utf-8"))["summary"]["total_har_entries"] == 6
