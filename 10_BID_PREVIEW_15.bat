@echo off
cd /d "%~dp0"
python -m yandex_boost update-bids-preview --fee 15
pause
