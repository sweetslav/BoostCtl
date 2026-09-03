from __future__ import annotations

from yandex_boost.client import AmbiguousMutationResult, RemoteRejectedError
from yandex_boost.create_services import SalesService, ShowsService
from yandex_boost.journal import OperationJournal
from yandex_boost.operations import OperationState, PlanDisposition, SourceQuality
from yandex_boost.shows_inventory import ShowsInventoryRecord


class FakeClient:
    def __init__(self, offers=None, outcome=None, journal=None):
        self.offers = offers or {"A": "offer-A", "B": "offer-B"}
        self.outcome = outcome
        self.journal = journal
        self.calls: list[dict[str, object]] = []

    def find_offer_id(self, sku):
        value = self.offers.get(sku)
        if isinstance(value, Exception):
            raise value
        if value is None:
            raise RuntimeError("not found")
        return value

    def create_campaign(self, **kwargs):
        self.calls.append(kwargs)
        if self.journal:
            assert self.journal.state(kwargs["operation_id"]) is OperationState.APPLYING
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome or {"salesCampaignId": "123"}


def sales_plan(tmp_path, items, observed=(), offers=None):
    journal = OperationJournal(tmp_path / "boostctl.db")
    client = FakeClient(offers)
    return journal, client, SalesService(journal, client).plan_create(items, set(observed), run_id="run", date="01.01.2026")


def test_sales_plan_classifies_duplicates_observations_and_resolution(tmp_path):
    journal, _, plan = sales_plan(tmp_path, [{"sku": "A", "fee": 15}, {"sku": "A", "fee": 15}, {"sku": "B", "fee": 20}, {"sku": "X", "fee": 10}], ["B"])
    assert [operation.disposition for operation in plan] == [PlanDisposition.CREATE, PlanDisposition.SKIP, PlanDisposition.SKIP, PlanDisposition.REVIEW]
    assert plan[0].intent["offer_id"] == "offer-A"
    assert plan[2].source_quality is SourceQuality.UI_OBSERVED
    journal.close()


def test_sales_apply_persists_before_call_and_verifies(tmp_path):
    journal = OperationJournal(tmp_path / "boostctl.db")
    client = FakeClient(journal=journal)
    service = SalesService(journal, client)
    plan = service.plan_create([{"sku": "A", "fee": 15}], set(), run_id="run", date="01.01.2026")
    original = client.create_campaign

    def create_campaign(**kwargs):
        kwargs["operation_id"] = plan[0].operation_id
        return original(**kwargs)

    client.create_campaign = create_campaign
    results = service.apply_create_plan(plan, verify=lambda _: (True, {"present": True}))
    assert client.calls and results[0].verification == "VERIFIED"
    assert journal.state(plan[0].operation_id) is OperationState.VERIFIED
    journal.close()


def test_skip_and_review_never_call_create(tmp_path):
    journal, client, plan = sales_plan(tmp_path, [{"sku": "A", "fee": 15}, {"sku": "X", "fee": 15}], ["A"])
    SalesService(journal, client).apply_create_plan(plan)
    assert client.calls == []
    journal.close()


def test_ambiguous_operation_blocks_repeated_create_after_reopen(tmp_path):
    journal, client, plan = sales_plan(tmp_path, [{"sku": "A", "fee": 15}])
    client.outcome = AmbiguousMutationResult("lost")
    first = SalesService(journal, client).apply_create_plan(plan)
    assert first[0].state is OperationState.UNKNOWN_RESULT
    journal.close()
    reopened = OperationJournal(tmp_path / "boostctl.db")
    second_client = FakeClient()
    second = SalesService(reopened, second_client).apply_create_plan(plan)
    assert second[0].verification == "BLOCKED"
    assert second_client.calls == []
    reopened.close()


def test_remote_rejection_is_failed_and_requires_explicit_retry(tmp_path):
    journal, client, plan = sales_plan(tmp_path, [{"sku": "A", "fee": 15}])
    client.outcome = RemoteRejectedError("rejected")
    assert SalesService(journal, client).apply_create_plan(plan)[0].state is OperationState.FAILED
    client.outcome = {"salesCampaignId": "2"}
    assert SalesService(journal, client).apply_create_plan(plan)[0].verification == "BLOCKED"
    journal.close()


def test_partial_batch_and_shows_history_are_safe(tmp_path):
    journal = OperationJournal(tmp_path / "boostctl.db")
    client = FakeClient()
    service = ShowsService(journal, client)
    plan = service.plan_create([{"sku": "A", "daily_limit": 300}, {"sku": "B", "daily_limit": 500}], {"A"}, run_id="run", date="01.01.2026")
    results = service.apply_create_plan(plan)
    assert plan[0].source_quality is SourceQuality.LOCAL_HISTORY
    assert plan[0].disposition is PlanDisposition.SKIP
    assert plan[1].intent["daily_limit"] == 500
    assert len(client.calls) == 1 and results[1].state is OperationState.SUCCEEDED
    journal.close()


def test_shows_current_inventory_controls_duplicate_protection(tmp_path):
    journal = OperationJournal(tmp_path / "boostctl.db")
    client = FakeClient()
    service = ShowsService(journal, client)
    active = [ShowsInventoryRecord("1", "A", "A", "ACTIVE", None, None, "url", "DOM")]
    stopped = [ShowsInventoryRecord("1", "A", "A", "STOPPED", None, None, "url", "DOM")]
    unknown = [ShowsInventoryRecord("1", "A", "A", "PAUSED", None, None, "url", "DOM")]
    assert service.plan_create_from_inventory([{"sku": "A", "daily_limit": 300}], active, run_id="run", date="01.01.2026")[0].disposition is PlanDisposition.SKIP
    assert service.plan_create_from_inventory([{"sku": "A", "daily_limit": 300}], stopped, run_id="run", date="01.01.2026")[0].disposition is PlanDisposition.CREATE
    assert service.plan_create_from_inventory([{"sku": "A", "daily_limit": 300}], unknown, run_id="run", date="01.01.2026")[0].disposition is PlanDisposition.REVIEW
    journal.close()


def test_fee_and_delete_plans_are_non_mutating_and_recoverable(tmp_path):
    journal = OperationJournal(tmp_path / "boostctl.db")
    client = FakeClient()
    client.update_campaign_fee = lambda *_: None
    client.delete_campaign = lambda *_: None
    service = SalesService(journal, client)
    fee = service.plan_fee_update([{"campaign_id": "1", "fee": 10}, {"campaign_id": "1"}], 15, run_id="run")
    deletion = service.plan_delete([{"campaign_id": "2"}], run_id="run")
    assert fee[0].disposition is PlanDisposition.CREATE and fee[1].disposition is PlanDisposition.SKIP
    assert deletion[0].destructive and deletion[0].executable
    assert service.apply_fee_update_plan(fee, verify=lambda _: (True, {}))[0].verification == "VERIFIED"
    assert service.apply_delete_plan(deletion, verify=lambda _: (True, {}))[0].verification == "VERIFIED"
    journal.close()
