@echo off
cd /d "%~dp0"
python -m yandex_boost.shows_create --limit 10
pause
