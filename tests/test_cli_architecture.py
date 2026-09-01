import ast
from pathlib import Path

from types import SimpleNamespace
from yandex_boost.cli import presentation_action


def test_presentation_action_hides_planner_create_for_fee_and_delete():
    create = SimpleNamespace(disposition=SimpleNamespace(value="CREATE"), operation_type=SimpleNamespace(value="CREATE_SALES"))
    fee = SimpleNamespace(disposition=SimpleNamespace(value="CREATE"), operation_type=SimpleNamespace(value="UPDATE_SALES_FEE"))
    delete = SimpleNamespace(disposition=SimpleNamespace(value="CREATE"), operation_type=SimpleNamespace(value="DELETE_SALES"))
    assert [presentation_action(item) for item in (create, fee, delete)] == ["CREATE", "UPDATE_FEE", "DELETE"]

def test_cli_does_not_call_low_level_mutations_directly():
    source = Path("src/yandex_boost/cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    assert "update_campaign_fee" not in calls
    assert "delete_campaign" not in calls
    assert "create_campaign" not in calls
