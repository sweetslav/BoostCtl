@echo off
cd /d "%~dp0"
python -m yandex_boost retry-errors
pause
