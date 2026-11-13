@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-input-mrt2.ps1" %*
if errorlevel 1 pause
