@echo off
cd /d "%~dp0"
title Telegram File Explorer
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with an error.
    pause
)
