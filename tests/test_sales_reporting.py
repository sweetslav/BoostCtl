from types import SimpleNamespace

from yandex_boost.cli import sales_apply_summary


def test_sales_apply_summary_keeps_execution_and_verification_separate():
    create = SimpleNamespace(executable=True, disposition=SimpleNamespace(value="CREATE"))
    skip = SimpleNamespace(executable=False, disposition=SimpleNamespace(value="REVIEW"))
    results = [
        SimpleNamespace(state=SimpleNamespace(value="VERIFIED"), verification="VERIFIED", operation=create),
        SimpleNamespace(state=SimpleNamespace(value="FAILED"), verification="NOT_VERIFIED", operation=create),
        SimpleNamespace(state=SimpleNamespace(value="UNKNOWN_RESULT"), verification="VERIFY_REQUIRED", operation=create),
        SimpleNamespace(state=SimpleNamespace(value="PLANNED"), verification="NOT_APPLICABLE", operation=skip),
    ]
    assert sales_apply_summary(results) == {"created": 1, "failed": 1, "unknown": 1, "verified": 1, "skipped": 1, "review": 1}
