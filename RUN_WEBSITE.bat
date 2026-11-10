@echo off
REM ==================================================================
REM  Edge-AI Smart Dustbin - DOUBLE-CLICK THIS FILE to start the website
REM  Then open  http://localhost:8000  in Chrome (it opens by itself).
REM  Keep this black window open. Close it (or press CTRL+C) to stop.
REM
REM  Options (from a terminal):  RUN_WEBSITE.bat demo   = also start a simulated bin
REM                              RUN_WEBSITE.bat build  = rebuild the dashboard first
REM ==================================================================
title Edge-AI Smart Dustbin - server
cd /d "%~dp0"
set "PY=%~dp0backend\venv\Scripts\python.exe"
set "MODE=%~1"

REM ---- 1. Python environment (first run only)
if exist "%PY%" goto :env
echo [1/4] Creating Python environment and installing packages (first time only)...
python -m venv backend\venv
if errorlevel 1 goto :error
"%PY%" -m pip install -r backend\requirements.txt
if errorlevel 1 goto :error

:env
if not exist backend\.env copy backend\.env.example backend\.env >nul

REM ---- 2. React dashboard (first run, or "build")
if /i "%MODE%"=="build" goto :build
if exist frontend\dist\index.html goto :database

:build
echo [2/4] Building the React dashboard...
pushd frontend
if not exist node_modules call npm install
call npm run build
if errorlevel 1 (
    popd
    goto :error
)
popd

:database
REM ---- 3. Database (SQLite file backend\db.sqlite3)
set FIRST=0
if not exist backend\db.sqlite3 set FIRST=1
echo [3/4] Updating database...
"%PY%" backend\manage.py migrate --noinput
if errorlevel 1 goto :error
if "%FIRST%"=="0" goto :run
echo First run: creating demo accounts and demo data...
"%PY%" backend\manage.py seed_demo
if errorlevel 1 goto :error

:run
REM ---- 4. Start
if /i "%MODE%"=="demo" start "Smart bin simulator" "%PY%" "%~dp0device\simulator.py"
echo.
echo [4/4] Server running. KEEP THIS WINDOW OPEN. Press CTRL+C to stop.
echo.
echo     Dashboard:          http://localhost:8000
echo     Phone / other PC:   http://YOUR-PC-IP:8000   (find it with ipconfig)
echo     Admin panel:        http://localhost:8000/admin
echo     Demo logins:        admin / admin12345     cleaner / cleaner12345
echo.
start "" cmd /c "ping -n 6 127.0.0.1 >nul & start http://localhost:8000"
"%PY%" backend\manage.py runserver 0.0.0.0:8000
goto :eof

:error
echo.
echo Something failed - read the message above.
pause
