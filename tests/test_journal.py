from yandex_boost.journal import OperationJournal
from yandex_boost.operations import OperationState, OperationType, PlannedOperation, SourceQuality


def test_journal_persists_plan_before_mutation_and_recovers_unfinished(tmp_path):
    journal = OperationJournal(tmp_path / "boostctl.db")
    journal.start_run("run", "sales.create", [])
    journal.persist_plan(PlannedOperation("op", "run", OperationType.CREATE_SALES, {"sku": "A"}, {"fee": 15}, SourceQuality.UNKNOWN))
    journal.transition("op", OperationState.APPLYING)
    journal.close()
    reopened = OperationJournal(tmp_path / "boostctl.db")
    assert reopened.unfinished() == ["op"]


def test_journal_retains_fee_and_delete_intent_state_and_verification(tmp_path):
    journal = OperationJournal(tmp_path / "boostctl.db")
    fee = PlannedOperation("fee", "run", OperationType.UPDATE_SALES_FEE, {"campaign_id": "1"}, {"requested_fee": 15}, SourceQuality.UI_OBSERVED)
    deletion = PlannedOperation("delete", "run", OperationType.DELETE_SALES, {"campaign_id": "2"}, {}, SourceQuality.UI_OBSERVED, destructive=True)
    for operation in (fee, deletion):
        journal.persist_plan(operation)
        journal.transition(operation.operation_id, OperationState.SUCCEEDED)
        journal.record_verification(operation.operation_id, OperationState.VERIFIED, "UI_OBSERVED", {"verified": True})
    rows = journal.connection.execute("SELECT operation_id, state, target_json, intent_json FROM operations ORDER BY operation_id").fetchall()
    assert rows[0][0] == "delete" and '"campaign_id": "2"' in rows[0][2]
    assert rows[1][0] == "fee" and '"requested_fee": 15' in rows[1][3]
    assert journal.connection.execute("SELECT COUNT(*) FROM verifications").fetchone()[0] == 2
