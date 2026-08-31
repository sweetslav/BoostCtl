@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe -m yandex_boost.har_inspect local_data\har\sales_boost_inventory.har local_data\reports\sales_boost_inventory_report.json --force
exit /b %errorlevel%
