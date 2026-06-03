@echo off
cd /d D:\testM\fund_monitor

set PYTHON=python
where python >nul 2>&1
if %errorlevel% neq 0 (
    where py >nul 2>&1
    if %errorlevel% equ 0 (set PYTHON=py) else (
        echo Python not found
        pause & exit /b 1
    )
)

echo Starting fund monitor server...
start "" http://127.0.0.1:8080
%PYTHON% main.py --serve
pause