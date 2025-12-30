@echo off
REM =============================================================================
REM validate_all_xmls.bat - Regression Test Script
REM =============================================================================
REM Purpose: Validate all 13 XMLs from GOLDEN_COMMIT.yaml
REM Created: 2025-12-10
REM Location: utilities/validate_all_xmls.bat
REM =============================================================================

setlocal enabledelayedexpansion

REM Change to project root (parent of utilities folder)
cd /d "%~dp0.."

echo.
echo =============================================================================
echo   XML-to-SQL Regression Test Suite
echo   Based on GOLDEN_COMMIT.yaml (13 validated XMLs)
echo =============================================================================
echo.

REM Check if server is running
curl -s http://localhost:8000/health >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Server not running at http://localhost:8000
    echo         Run utilities\restart_server.bat first
    exit /b 1
)

echo [OK] Server is running at http://localhost:8000
echo.

REM Define XML files from GOLDEN_COMMIT.yaml
set "XML_COUNT=0"

REM BW_ON_HANA XMLs
set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/HANA 1.XX XML Views/BW_ON_HANA/CV_CNCLD_EVNTS.xml"
set "EXPECTED_TIME[%XML_COUNT%]=74ms"

set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/HANA 1.XX XML Views/BW_ON_HANA/CV_INVENTORY_ORDERS.xml"
set "EXPECTED_TIME[%XML_COUNT%]=42ms"

set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/HANA 1.XX XML Views/BW_ON_HANA/CV_PURCHASE_ORDERS.xml"
set "EXPECTED_TIME[%XML_COUNT%]=46ms"

set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/HANA 1.XX XML Views/BW_ON_HANA/CV_EQUIPMENT_STATUSES.xml"
set "EXPECTED_TIME[%XML_COUNT%]=26ms"

set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/HANA 1.XX XML Views/BW_ON_HANA/CV_TOP_PTHLGY.xml"
set "EXPECTED_TIME[%XML_COUNT%]=195ms"

set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/HANA 1.XX XML Views/BW_ON_HANA/CV_UPRT_PTLG.xml"
set "EXPECTED_TIME[%XML_COUNT%]=27ms"

set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/HANA 1.XX XML Views/BW_ON_HANA/CV_ELIG_TRANS_01.xml"
set "EXPECTED_TIME[%XML_COUNT%]=28ms"

set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/HANA 1.XX XML Views/BW_ON_HANA/CV_COMMACT_UNION.xml"
set "EXPECTED_TIME[%XML_COUNT%]=N/A"

REM ECC_ON_HANA XMLs
set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/HANA 1.XX XML Views/ECC_ON_HANA/CV_MCM_CNTRL_Q51.xml"
set "EXPECTED_TIME[%XML_COUNT%]=82ms"

set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/HANA 1.XX XML Views/ECC_ON_HANA/CV_MCM_CNTRL_REJECTED.xml"
set "EXPECTED_TIME[%XML_COUNT%]=53ms"

REM Root level XMLs (SESSION 8)
set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/CV_INVENTORY_STO.xml"
set "EXPECTED_TIME[%XML_COUNT%]=59ms"

set /a XML_COUNT+=1
set "XML[%XML_COUNT%]=Source (XML Files)/CV_PURCHASING_YASMIN.xml"
set "EXPECTED_TIME[%XML_COUNT%]=70ms"

REM Note: CV_CT02_CT03.xml is marked as NOT VALIDATABLE in GOLDEN_COMMIT.yaml
REM due to BUG-019 and BUG-003 (Active limitations)

echo Total XMLs to validate: %XML_COUNT%
echo.
echo =============================================================================
echo   REGRESSION TEST CHECKLIST
echo =============================================================================
echo.

set "PASS_COUNT=0"
set "FAIL_COUNT=0"
set "SKIP_COUNT=0"

for /L %%i in (1,1,%XML_COUNT%) do (
    set "CURRENT_XML=!XML[%%i]!"
    set "CURRENT_TIME=!EXPECTED_TIME[%%i]!"

    REM Extract filename for display
    for %%F in ("!CURRENT_XML!") do set "FILENAME=%%~nxF"

    echo [%%i/%XML_COUNT%] !FILENAME!
    echo         Path: !CURRENT_XML!
    echo         Expected HANA Time: !CURRENT_TIME!

    REM Check if file exists
    if exist "pipelines\xml-to-sql\!CURRENT_XML!" (
        echo         Status: FILE EXISTS
        echo         [ ] Convert via Web UI: http://localhost:8000
        echo         [ ] Execute in HANA Studio
        echo         [ ] Record execution time: ______ms
        echo         [ ] PASS / FAIL
    ) else (
        echo         Status: FILE NOT FOUND - SKIPPED
        set /a SKIP_COUNT+=1
    )
    echo.
)

echo =============================================================================
echo   MANUAL VALIDATION REQUIRED
echo =============================================================================
echo.
echo This script generates a checklist for manual validation.
echo.
echo Steps for each XML:
echo   1. Open http://localhost:8000
echo   2. Upload the XML file
echo   3. Click Convert
echo   4. Copy SQL from LATEST_SQL_FROM_DB.txt
echo   5. Execute in HANA Studio
echo   6. Record: PASS (with time) or FAIL (with error)
echo.
echo After validation:
echo   - If ALL PASS: Safe to commit changes
echo   - If ANY FAIL: DO NOT commit, investigate regression
echo.
echo Files skipped: %SKIP_COUNT%
echo.
echo =============================================================================
echo   IMPORTANT: GOLDEN_COMMIT.yaml Rule
echo =============================================================================
echo   "Working code is more valuable than fixing new bugs"
echo   If ANY previously working XML breaks, REVERT IMMEDIATELY
echo =============================================================================
echo.

pause
