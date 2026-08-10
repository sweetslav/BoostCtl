@echo off
cd /d "%~dp0"
python -m yandex_boost update-bids --fee 15 --limit 3
pause
