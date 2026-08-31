@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python.exe -m yandex_boost.sales_inventory_discovery --force
exit /b %errorlevel%
