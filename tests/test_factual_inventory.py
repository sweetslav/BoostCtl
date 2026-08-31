import json
import subprocess
import sys
from pathlib import Path

import pytest

from yandex_boost.campaigns import CampaignSource
from yandex_boost.factual_inventory import (
    UnsupportedFactualSalesBoostSchema,
    build_factual_inventory_diagnostic,
    load_factual_sales_boost_observations,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "yandex_captures" / "factual_sales_boost_report.json"
REALISTIC_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "yandex_captures" / "realistic_sales_boost_report.json"


def _report() -> object:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_loader_extracts_only_confirmed_sales_boost_identifiers_and_offer_identity():
    records = load_factual_sales_boost_observations(_report())

    assert len(records) == 1
    record = records[0]
    assert record.sales_campaign_id == "10958486"
    assert record.strategy_id == "10958486"
    assert record.business_id == "950637"
    assert record.offer_ids == ("dcmp-13822103539493545641",)
    assert record.skus == ()
    assert record.legacy_name_hint == "2020488/1#1"
    assert record.campaign_id is None
    assert record.source is CampaignSource.FACTUAL_HAR


def test_loader_merges_realistic_detail_and_supporting_fee_observation():
    records = load_factual_sales_boost_observations(json.loads(REALISTIC_FIXTURE_PATH.read_text(encoding="utf-8")))

    assert len(records) == 1
    record = records[0]
    assert record.sales_campaign_id == "10958486"
    assert record.name == "2020488/1#1 | 04.08.2026"
    assert record.status == "ACTIVE"
    assert record.cost_model == "CPA"
    assert record.fee == 15
    assert record.offer_ids == ("dcmp-13822103539493545641",)
    assert record.business_id == "950637"
    assert record.created_at == "1785834358820"
    assert record.updated_at == "1786346001826"


def test_loader_rejects_unknown_schema_and_accepts_empty_known_campaign_collection():
    with pytest.raises(UnsupportedFactualSalesBoostSchema):
        load_factual_sales_boost_observations({"entries": [{"response_json": {"id": 1}}]})

    assert load_factual_sales_boost_observations({"entries": [{"response_json": {"campaigns": []}}]}) == []


def test_diagnostic_reports_missing_and_conflicting_observations():
    report = _report()
    report["entries"].append(
        {"response_json": {"salesCampaignId": 10958486, "name": "Other", "offerId": "dcmp-other"}}
    )
    diagnostic = build_factual_inventory_diagnostic(load_factual_sales_boost_observations(report))

    assert diagnostic["summary"]["unique_factual_campaigns"] == 1
    assert diagnostic["summary"]["unique_offer_ids"] == 2
    assert diagnostic["conflicting_observations"][0]["sales_campaign_id"] == "10958486"


def test_diagnostic_flags_offer_id_shared_by_multiple_campaigns():
    report = _report()
    report["entries"].append(
        {"response_json": {"salesCampaignId": 10958487, "name": "Second", "offerId": "dcmp-13822103539493545641"}}
    )
    diagnostic = build_factual_inventory_diagnostic(load_factual_sales_boost_observations(report))

    assert diagnostic["offer_ids_in_multiple_campaigns"] == {
        "dcmp-13822103539493545641": ["10958486", "10958487"]
    }


def test_module_entrypoint_shows_help_and_writes_diagnostic(tmp_path):
    help_result = subprocess.run(
        [sys.executable, "-m", "yandex_boost.factual_inventory_cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    output_path = tmp_path / "diagnostic.json"
    run_result = subprocess.run(
        [sys.executable, "-m", "yandex_boost.factual_inventory_cli", str(FIXTURE_PATH), str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert help_result.returncode == 0
    assert "usage:" in help_result.stdout
    assert run_result.returncode == 0
    assert str(output_path) in run_result.stdout
    assert json.loads(output_path.read_text(encoding="utf-8"))["summary"]["unique_factual_campaigns"] == 1


def test_module_entrypoint_reports_errors_to_stderr(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "yandex_boost.factual_inventory_cli", str(tmp_path / "missing.json"), str(tmp_path / "output.json")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "ERROR:" in result.stderr
    assert result.stdout == ""
