@echo off
cd /d "%~dp0"
chcp 65001 >nul
python -m yandex_boost.menu
if errorlevel 1 (
    echo.
    echo Не удалось запустить BoostCtl.
    echo Если это первый запуск, выполните 00_INSTALL.bat
    echo.
    pause
)
