from yandex_boost.shows_inventory import ShowsInventoryRecord, shows_duplicate_disposition, shows_summary


def record(sku: str, status: str | None) -> ShowsInventoryRecord:
    return ShowsInventoryRecord("1", "name", sku, status, None, None, "url", "DOM")


def test_active_shows_blocks_create_but_stopped_allows_it():
    assert shows_duplicate_disposition([record("A", "ACTIVE")], "A") == ("SKIP", "ACTIVE")
    assert shows_duplicate_disposition([record("A", "STOPPED")], "A") == ("CREATE", "STOPPED")


def test_missing_unknown_and_ambiguous_shows_are_safe():
    assert shows_duplicate_disposition([], "A") == ("CREATE", None)
    assert shows_duplicate_disposition([record("A", "PAUSED")], "A") == ("REVIEW", "PAUSED")
    assert shows_duplicate_disposition([record("A", "STOPPED"), record("A", "CLOSED")], "A") == ("REVIEW", None)


def test_shows_summary_keeps_raw_statuses_honest():
    summary = shows_summary([record("A", "ACTIVE"), record("B", "CLOSED"), record("C", "PAUSED")])
    assert summary == {"total": 3, "active": 1, "stopped_or_closed": 1, "unknown": 1}
