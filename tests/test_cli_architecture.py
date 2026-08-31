import ast
from pathlib import Path


def test_cli_does_not_call_low_level_fee_or_delete_mutations_directly():
    source = Path("src/yandex_boost/cli.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    assert "update_campaign_fee" not in calls
    assert "delete_campaign" not in calls
