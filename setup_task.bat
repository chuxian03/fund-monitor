@echo off
REM 注册 Windows 计划任务：每天 16:30 自动运行基金监控报告
REM 需要管理员权限运行

cd /d "%~dp0"

set TASK_NAME=FundDailyMonitor
set BAT_PATH=%~dp0run_daily.bat

echo 正在创建计划任务: %TASK_NAME%
echo 执行路径: %BAT_PATH%
echo 执行时间: 每天 16:30
echo.

schtasks /create /tn "%TASK_NAME%" /tr "%BAT_PATH%" /sc daily /st 16:30 /f

if %errorlevel% equ 0 (
    echo [OK] 计划任务创建成功！
    echo 可在"任务计划程序"中查看和管理
) else (
    echo [ERROR] 计划任务创建失败，请以管理员身份运行此脚本
)

pause