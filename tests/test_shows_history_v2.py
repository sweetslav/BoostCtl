from pathlib import Path

from yandex_boost.shows_create import load_created_skus, load_shows_report_observations


def _write_report(path: Path, rows: list[str]) -> None:
    path.write_text(
        "timestamp;sku;daily_limit;campaign_name;offer_id;status;details;operation_id;execution_state;verification;campaign_id\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8-sig",
    )


def test_v2_success_rows_are_used_as_local_created_history(tmp_path):
    report = tmp_path / "shows.csv"
    _write_report(
        report,
        [
            "01.09.2026 11:00:00;A;300;A | 01.09.2026;offer-A;SUCCEEDED;NOT_VERIFIED;op1;SUCCEEDED;NOT_VERIFIED;",
            "01.09.2026 11:01:00;B;300;B | 01.09.2026;offer-B;VERIFIED;VERIFIED;op2;VERIFIED;VERIFIED;123",
        ],
    )

    assert load_created_skus(report) == {"A", "B"}
    assert {record.skus[0] for record in load_shows_report_observations(report)} == {"A", "B"}


def test_legacy_created_rows_remain_supported(tmp_path):
    report = tmp_path / "shows.csv"
    _write_report(
        report,
        ["01.09.2026 10:00:00;LEGACY;300;LEGACY | 01.09.2026;offer-L;CREATED;;;;;"],
    )

    assert load_created_skus(report) == {"LEGACY"}


def test_dry_run_or_failed_rows_are_not_used_as_created_history(tmp_path):
    report = tmp_path / "shows.csv"
    _write_report(
        report,
        [
            "01.09.2026 10:00:00;DRY;300;DRY | 01.09.2026;offer-D;DRY_RUN;;op1;PLANNED;NOT_APPLIED;",
            "01.09.2026 10:01:00;FAILED;300;FAILED | 01.09.2026;offer-F;FAILED;;op2;FAILED;NOT_VERIFIED;",
        ],
    )

    assert load_created_skus(report) == set()
    assert load_shows_report_observations(report) == []
