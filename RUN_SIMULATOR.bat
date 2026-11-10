@echo off
REM Double-click to start ONLY the simulated smart bin (the website must already be running).
title Smart bin simulator
cd /d "%~dp0"
"%~dp0backend\venv\Scripts\python.exe" "%~dp0device\simulator.py"
pause
