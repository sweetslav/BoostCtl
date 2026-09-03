from types import SimpleNamespace
import json

from yandex_boost import product_cli
from yandex_boost.journal import OperationJournal
from yandex_boost.inventory import SalesInventoryRecord


def test_history_lists_recovery_and_exports_csv(tmp_path, monkeypatch, capsys):
    database = tmp_path / "boostctl.db"
    journal = OperationJournal(database)
    journal.start_run("run", "sales.create", [])
    journal.connection.execute("INSERT INTO operations VALUES ('op', 'run', 'CREATE_SALES', '{}', '{}', 'UNKNOWN', 'UNKNOWN_RESULT', 0, 'now', 'now')")
    journal.connection.commit()
    journal.close()
    monkeypatch.setattr(product_cli, "DB", database)
    monkeypatch.setattr(product_cli, "ROOT", tmp_path)
    product_cli.history()
    assert "Автоматический повтор заблокирован" in capsys.readouterr().out
    product_cli.history(export=True)
    export = tmp_path / "local_data" / "reports" / "operation_history.csv"
    assert export.exists()
    assert len(export.read_text(encoding="utf-8-sig").splitlines()[1].split(";")) == 8


def test_history_renders_sku_and_campaign_id(tmp_path, monkeypatch, capsys):
    database = tmp_path / "boostctl.db"
    journal = OperationJournal(database)
    journal.start_run("run", "sales.delete", [])
    journal.connection.execute(
        "INSERT INTO operations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("op", "run", "DELETE_SALES", json.dumps({"sku": "A", "campaign_id": "17"}), "{}", "UI_OBSERVED", "SUCCEEDED", 1, "now", "now"),
    )
    journal.connection.commit()
    journal.close()
    monkeypatch.setattr(product_cli, "DB", database)
    product_cli.history()
    output = capsys.readouterr().out
    assert "SKU: A" in output and "campaign_id: 17" in output


def test_inventory_summary_and_search_are_read_only(capsys):
    rows = [
        SalesInventoryRecord("1", "A | 01.01.2026", "A", "url-1"),
        SalesInventoryRecord("2", "A | 02.01.2026", "A", "url-2"),
        SalesInventoryRecord("3", "B | 01.01.2026", "B", "url-3"),
    ]
    product_cli.render_inventory(rows, "A", "")
    output = capsys.readouterr().out
    assert "3" in output and "2" in output and "1" in output
    assert "url-1" in output and "url-2" in output


def test_wrong_confirmation_never_applies_sales_mutation(monkeypatch, tmp_path, capsys):
    journal = SimpleNamespace(close=lambda: None)
    plan = [SimpleNamespace(
        executable=True, target={"sku": "A"}, intent={"fee": 10},
        disposition=SimpleNamespace(value="CREATE"), warnings=(),
        operation_type=SimpleNamespace(value="CREATE_SALES"), source_quality=SimpleNamespace(value="UI_OBSERVED"),
    )]
    session = SimpleNamespace(page=object(), config=object(), sales_client=object(), journal_path=tmp_path / "db.sqlite")
    monkeypatch.setattr(product_cli, "sales_create_preview", lambda *_: (journal, plan))
    applied = []
    monkeypatch.setattr(product_cli, "apply_sales_create", lambda *args, **kwargs: applied.append(args) or [])
    monkeypatch.setattr("builtins.input", lambda _: "no")
    product_cli.run_sales_create(session, ["A"], 10)
    assert applied == []
    assert "Операция отменена" in capsys.readouterr().out


def test_fee_ambiguous_sku_does_not_apply(monkeypatch, tmp_path, capsys):
    rows = [
        SalesInventoryRecord("1", "A | 01.01.2026", "A", "url-1"),
        SalesInventoryRecord("2", "A | 02.01.2026", "A", "url-2"),
    ]
    session = SimpleNamespace(page=object(), config=object(), sales_client=object(), journal_path=tmp_path / "db.sqlite")
    monkeypatch.setattr(product_cli, "fetch_campaign_inventory", lambda *_: rows)
    applied = []
    monkeypatch.setattr(product_cli, "apply_fee_plan", lambda *args: applied.append(args))
    product_cli.run_fee_update(session, "A", 10)
    assert applied == []
    assert "REVIEW" in capsys.readouterr().out


def _create_plan():
    return [SimpleNamespace(
        executable=True, target={"sku": "A"}, intent={"fee": 10, "offer_id": "offer-A"},
        disposition=SimpleNamespace(value="CREATE"), warnings=(),
        operation_type=SimpleNamespace(value="CREATE_SALES"), source_quality=SimpleNamespace(value="UI_OBSERVED"),
    )]


def test_preview_cancel_requires_no_typed_confirmation_and_does_not_apply(monkeypatch, tmp_path, capsys):
    journal = SimpleNamespace(close=lambda: None)
    session = SimpleNamespace(page=object(), config=object(), sales_client=object(), journal_path=tmp_path / "db.sqlite")
    monkeypatch.setattr(product_cli, "sales_create_preview", lambda *_: (journal, _create_plan()))
    applied = []
    monkeypatch.setattr(product_cli, "apply_sales_create", lambda *args, **kwargs: applied.append(args))
    prompts = []
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "2")
    product_cli.run_sales_create(session, ["A"], 10)
    assert applied == []
    assert len(prompts) == 1 and "Выполнить" in capsys.readouterr().out


def test_apply_requires_explicit_choice_then_typed_confirmation(monkeypatch, tmp_path):
    journal = SimpleNamespace(close=lambda: None)
    session = SimpleNamespace(page=object(), config=object(), sales_client=object(), journal_path=tmp_path / "db.sqlite")
    monkeypatch.setattr(product_cli, "sales_create_preview", lambda *_: (journal, _create_plan()))
    applied = []
    monkeypatch.setattr(product_cli, "apply_sales_create", lambda *args, **kwargs: applied.append(args) or [])
    answers = iter(["1", "CREATE 1"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    product_cli.run_sales_create(session, ["A"], 10)
    assert len(applied) == 1


def test_fee_presentation_is_update_fee_not_create(capsys):
    operation = SimpleNamespace(
        target={"campaign_id": "17", "sku": "A"}, intent={"requested_fee": 7, "current_fee": None},
        disposition=SimpleNamespace(value="CREATE"), warnings=(),
        operation_type=SimpleNamespace(value="UPDATE_SALES_FEE"), source_quality=SimpleNamespace(value="UI_OBSERVED"),
    )
    product_cli.render_preview([operation])
    output = capsys.readouterr().out
    assert "UPDATE_FEE" in output and "CREATE" not in output


def test_sales_preview_contains_offer_id_and_fee(capsys):
    product_cli.render_preview(_create_plan())
    output = capsys.readouterr().out
    assert "offerId: offer-A" in output and "ставка: 10" in output


def test_sales_apply_renders_result_and_batch_summary(capsys):
    result = SimpleNamespace(
        operation=_create_plan()[0], state=SimpleNamespace(value="SUCCEEDED"),
        verification="NOT_VERIFIED", campaign_id="17", error=None,
    )
    product_cli.render_results([result])
    output = capsys.readouterr().out
    assert "SKU: A" in output and "Execution: SUCCEEDED" in output
    assert "campaign_id: 17" in output and "Итог:" in output


def test_inventory_without_filter_does_not_print_campaign_rows(capsys):
    rows = [SalesInventoryRecord("1", "A | 01.01.2026", "A", "url-1")]
    product_cli.render_inventory(rows)
    assert "url-1" not in capsys.readouterr().out


def test_history_hides_empty_runs_and_normalizes_legacy_verification(tmp_path, monkeypatch, capsys):
    database = tmp_path / "boostctl.db"
    journal = OperationJournal(database)
    journal.start_run("empty", "sales.create", [])
    journal.start_run("real", "sales.create", [])
    journal.connection.execute("INSERT INTO operations VALUES ('op', 'real', 'CREATE_SALES', '{\"sku\": \"A\"}', '{}', 'UI_OBSERVED', 'SUCCEEDED', 0, 'now', 'now')")
    journal.connection.execute("INSERT INTO verifications VALUES ('op', 'SUCCEEDED', 'NOT_VERIFIED', '{}', 'now')")
    journal.connection.commit()
    journal.close()
    monkeypatch.setattr(product_cli, "DB", database)
    product_cli.history()
    output = capsys.readouterr().out
    assert "SKU: -" not in output
    assert "Verification: NOT_VERIFIED" in output
    assert "Verification: SUCCEEDED" not in output
