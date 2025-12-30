@echo off
REM Change to the project root (parent of utilities folder)
cd /d "%~dp0.."

echo ========================================
echo X2S Monorepo - Hard Restart Server
echo ========================================
echo.

echo [1/15] Killing Python processes by name...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM pythonw.exe >nul 2>&1
echo    ✓ Killed by process name

echo.
echo [2/15] Finding processes using port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo    Found PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)
echo    ✓ Port-based kill complete

echo.
echo [3/15] Waiting for connections to clear (attempt 1)...
timeout /t 3 /nobreak >nul
netstat -ano | findstr :8000 >nul
if %ERRORLEVEL% EQU 0 (
    echo    ⏳ Port still in TIME_WAIT, continuing cleanup...
) else (
    echo    ✓ Port 8000 is free
    goto :port_free
)

echo.
echo [4/15] Additional cleanup - killing uvicorn processes...
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST ^| findstr /C:"PID:"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo    ✓ Additional cleanup complete

echo.
echo [5/15] Waiting for connections to clear (attempt 2)...
timeout /t 5 /nobreak >nul
netstat -ano | findstr :8000 >nul
if %ERRORLEVEL% EQU 0 (
    echo    ⏳ Port still in TIME_WAIT, continuing...
) else (
    echo    ✓ Port 8000 is free
    goto :port_free
)

echo.
echo [6/15] Final port check and PID cleanup...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    echo    Forcing kill PID: %%a
    taskkill /F /T /PID %%a >nul 2>&1
)
timeout /t 5 /nobreak >nul

:port_free
echo.
echo [7/15] Verifying port 8000 is free...
netstat -ano | findstr :8000 >nul
if %ERRORLEVEL% EQU 0 (
    echo    ⚠ Port 8000 still has TIME_WAIT connections
    echo    This is normal, continuing anyway...
) else (
    echo    ✓ Port 8000 is completely free
)

echo.
echo [8/15] Clearing Python cache files (core)...
for /r "core" %%i in (*.pyc) do @del "%%i" >nul 2>&1
for /d /r "core" %%i in (__pycache__) do @rd /s /q "%%i" >nul 2>&1
echo    ✓ Core cache cleared

echo.
echo [9/15] Clearing Python cache files (pipelines)...
for /r "pipelines" %%i in (*.pyc) do @del "%%i" >nul 2>&1
for /d /r "pipelines" %%i in (__pycache__) do @rd /s /q "%%i" >nul 2>&1
echo    ✓ Pipeline cache cleared

echo.
echo [10/15] Reinstalling core package...
cd core
pip install -e . --quiet
if %ERRORLEVEL% EQU 0 (
    echo    ✓ Core package reinstalled successfully
) else (
    echo    ✗ Core package reinstall failed!
    cd ..
    pause
    exit /b 1
)
cd ..

echo.
echo [11/15] Reinstalling xml-to-sql pipeline...
cd pipelines\xml-to-sql
pip install -e . --quiet
if %ERRORLEVEL% EQU 0 (
    echo    ✓ xml-to-sql pipeline reinstalled successfully
) else (
    echo    ✗ xml-to-sql pipeline reinstall failed!
    cd ..\..
    pause
    exit /b 1
)

echo.
echo [12/15] Verifying package installation...
python -c "from x2s_core.parser import scenario_parser; print('    ✓ Core loaded')" 2>&1
python -c "from xml_to_sql.sql.renderer import HanaSQLRenderer; print('    ✓ xml-to-sql loaded')" 2>&1

echo.
echo [13/15] Building React frontend...
cd web_frontend
call npm run build --silent
if %ERRORLEVEL% EQU 0 (
    echo    ✓ Frontend built successfully
) else (
    echo    ✗ Frontend build failed!
    cd ..\..\..
    pause
    exit /b 1
)
cd ..

echo.
echo [14/15] Verifying frontend build...
if exist "web_frontend\dist\index.html" (
    echo    ✓ Frontend dist/index.html exists
) else (
    echo    ✗ Frontend dist/index.html missing!
    cd ..\..
    pause
    exit /b 1
)

echo.
echo [15/15] Starting web server...
echo    Server will start at http://localhost:8000
echo    Press Ctrl+C to stop the server
echo.
echo ========================================
echo Ready to start!
echo ========================================
timeout /t 2 /nobreak >nul
echo.

REM Start server from xml-to-sql pipeline directory
python -m uvicorn xml_to_sql.web.main:app --reload --host 0.0.0.0 --port 8000
cd ..\..

