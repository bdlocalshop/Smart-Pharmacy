@echo off
title Smart Pharmacy Desktop App
cd /d "%~dp0"

echo Starting Smart Pharmacy Management Desktop App...

where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    python main.py
    goto end
)

if exist "C:\Users\New User\AppData\Local\Programs\Python\Python312\python.exe" (
    "C:\Users\New User\AppData\Local\Programs\Python\Python312\python.exe" main.py
    goto end
)

echo Python was not found! Please ensure Python 3.12 is installed.
pause

:end
