from yandex_boost.report import CsvReport


def test_created_names(tmp_path):
    report = CsvReport(tmp_path / "report.csv")
    report.append(
        sku="ABC#1",
        bid=18,
        campaign_name="ABC#1 | 04.08.2026",
        offer_id="dcmp-1",
        status="CREATED",
        details="ok",
    )
    assert report.created_names() == {"ABC#1 | 04.08.2026"}
