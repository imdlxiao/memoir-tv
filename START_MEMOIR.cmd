@echo off
rem Author: donglixiao
chcp 65001 >nul
cd /d "%~dp0"
python -m memoir serve --open
if errorlevel 1 pause
