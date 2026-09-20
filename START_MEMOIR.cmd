@echo off
rem Author: donglixiao
chcp 65001 >nul
cd /d "%~dp0"
start "" http://127.0.0.1:8765
python -m memoir serve
if errorlevel 1 pause
