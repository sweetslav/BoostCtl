@echo off
setlocal
cd /d "%~dp0"
call RUN_HAR_INSPECT.bat
if errorlevel 1 exit /b %errorlevel%
call RUN_SALES_INVENTORY_DISCOVERY.bat
if errorlevel 1 exit /b %errorlevel%
call RUN_FACTUAL_INVENTORY.bat
if errorlevel 1 exit /b %errorlevel%
echo Reports updated:
echo   local_data\reports\sales_boost_inventory_report.json
echo   local_data\reports\sales_inventory_discovery.json
echo   local_data\reports\factual_sales_boost_diagnostic.json
exit /b 0
