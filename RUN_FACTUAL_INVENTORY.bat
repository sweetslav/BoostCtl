@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe -m yandex_boost.factual_inventory_cli local_data\reports\sales_boost_inventory_report.json local_data\reports\factual_sales_boost_diagnostic.json --force
exit /b %errorlevel%
