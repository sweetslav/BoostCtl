from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_generated_report_bat_scripts_use_force_and_repo_local_paths():
    assert "sales_boost_inventory_report.json --force" in (ROOT / "RUN_HAR_INSPECT.bat").read_text()
    assert "factual_sales_boost_diagnostic.json --force" in (ROOT / "RUN_FACTUAL_INVENTORY.bat").read_text()
    assert "sales_inventory_discovery" in (ROOT / "RUN_SALES_INVENTORY_DISCOVERY.bat").read_text()


def test_combined_bat_stops_after_each_stage_and_reports_local_outputs():
    script = (ROOT / "RUN_SALES_DIAGNOSTICS.bat").read_text()
    assert script.count("if errorlevel 1 exit /b %errorlevel%") == 3
    assert "call RUN_HAR_INSPECT.bat" in script
    assert "call RUN_SALES_INVENTORY_DISCOVERY.bat" in script
    assert "call RUN_FACTUAL_INVENTORY.bat" in script
    assert "Desktop" not in script
    assert "C:\\Temp" not in script
