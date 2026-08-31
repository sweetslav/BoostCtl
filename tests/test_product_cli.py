from yandex_boost import product_cli
from yandex_boost.journal import OperationJournal


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
    assert (tmp_path / "local_data" / "reports" / "operation_history.csv").exists()
