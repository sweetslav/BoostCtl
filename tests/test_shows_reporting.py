from types import SimpleNamespace

from yandex_boost.shows_v2 import shows_apply_summary


def test_shows_summary_keeps_success_and_not_verified_separate():
    create = SimpleNamespace(executable=True, disposition=SimpleNamespace(value="CREATE"))
    skip = SimpleNamespace(executable=False, disposition=SimpleNamespace(value="REVIEW"))
    results = [
        SimpleNamespace(state=SimpleNamespace(value="SUCCEEDED"), verification="NOT_VERIFIED", operation=create),
        SimpleNamespace(state=SimpleNamespace(value="FAILED"), verification="NOT_VERIFIED", operation=create),
        SimpleNamespace(state=SimpleNamespace(value="UNKNOWN_RESULT"), verification="VERIFY_REQUIRED", operation=create),
        SimpleNamespace(state=SimpleNamespace(value="PLANNED"), verification="NOT_APPLICABLE", operation=skip),
    ]
    assert shows_apply_summary(results) == {"successful": 1, "failed": 1, "unknown": 1, "verified": 0, "not_verified": 2, "skipped": 1, "review": 1}
