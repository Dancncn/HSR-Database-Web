@echo off
setlocal EnableDelayedExpansion

pushd "%~dp0" >nul

echo ============================================================
echo [1/6] Checking dump file
echo ============================================================
if not exist "..\dump_all.sql" (
  echo ERROR: Missing ..\dump_all.sql
  echo Please run this at repo root first:
  echo   python scripts\export_sqlite_dump.py
  popd >nul
  exit /b 2
)

echo ============================================================
echo [2/6] Remote import to D1 (^--remote^)
echo ============================================================
wrangler --config wrangler.jsonc d1 execute hsrdb --file=..\dump_all.sql --remote
if errorlevel 1 (
  echo ERROR: Remote import failed.
  popd >nul
  exit /b 1
)

echo.
echo ============================================================
echo [3/6] Verify A: table count
echo ============================================================
wrangler --config wrangler.jsonc d1 execute hsrdb --remote --command="SELECT COUNT(*) AS tables FROM sqlite_master WHERE type='table';"
if errorlevel 1 (
  echo ERROR: Verify A failed.
  popd >nul
  exit /b 1
)

echo.
echo ============================================================
echo [4/6] Verify B: first 30 table names
echo ============================================================
wrangler --config wrangler.jsonc d1 execute hsrdb --remote --command="SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 30;"
if errorlevel 1 (
  echo ERROR: Verify B failed.
  popd >nul
  exit /b 1
)

echo.
echo ============================================================
echo [5/6] Verify C: probe dialogue/avatar tables by LIKE
echo ============================================================
echo -- LIKE '%%dialog%%'
wrangler --config wrangler.jsonc d1 execute hsrdb --remote --command="SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%dialog%' ORDER BY name;"
if errorlevel 1 (
  echo ERROR: Verify C(dialog) failed.
  popd >nul
  exit /b 1
)
echo -- LIKE '%%avatar%%'
wrangler --config wrangler.jsonc d1 execute hsrdb --remote --command="SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%avatar%' ORDER BY name;"
if errorlevel 1 (
  echo ERROR: Verify C(avatar) failed.
  popd >nul
  exit /b 1
)

echo.
echo ============================================================
echo [6/6] Start local Worker (^--remote^) and run API tests
echo ============================================================
if exist "_dev_remote.log" del /f /q "_dev_remote.log" >nul 2>nul
start "hsrdb-dev-remote" /b cmd /c "wrangler --config wrangler.jsonc dev --remote --port 8787 > _dev_remote.log 2>&1"

set /a __wait=0
:wait_loop
set /a __wait+=1
if %__wait% gtr 40 (
  echo ERROR: dev server did not become ready in time.
  if exist "_dev_remote.log" (
    echo ----- dev log -----
    type "_dev_remote.log"
    echo -------------------
  )
  popd >nul
  exit /b 1
)

curl -sS -i "http://127.0.0.1:8787/api/stats" > "_ping_tmp.txt" 2>nul
if errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait_loop
)
del /f /q "_ping_tmp.txt" >nul 2>nul

call :test_api "http://127.0.0.1:8787/api/stats"
if errorlevel 1 goto :api_failed
call :test_api "http://127.0.0.1:8787/api/search/dialogue?q=test&lang=zh&page=1&page_size=5"
if errorlevel 1 goto :api_failed
call :test_api "http://127.0.0.1:8787/api/avatar/1001?lang=zh"
if errorlevel 1 goto :api_failed

echo.
echo All checks finished.
echo Dev server is still running in background.
echo Press Ctrl+C in that dev terminal if you opened it interactively.
echo If needed, inspect log: %cd%\_dev_remote.log
popd >nul
exit /b 0

:api_failed
echo ERROR: one or more API tests failed.
if exist "_dev_remote.log" (
  echo ----- dev log -----
  type "_dev_remote.log"
  echo -------------------
)
popd >nul
exit /b 1

:test_api
set "URL=%~1"
set "TMP=_curl_resp.txt"
echo.
echo ------------------------------------------------------------
echo API: %URL%
echo ------------------------------------------------------------
curl -sS -i "%URL%" > "%TMP%"
if errorlevel 1 (
  echo curl failed for %URL%
  exit /b 1
)

set "FIRST="
set /p FIRST=<"%TMP%"
set "STATUS=UNKNOWN"
for /f "tokens=2" %%S in ("%FIRST%") do set "STATUS=%%S"
echo HTTP Status: !STATUS!
echo Response preview ^(first 200 chars^):

set "PREVIEW="
for /f "usebackq delims=" %%L in ("%TMP%") do (
  set "PREVIEW=!PREVIEW!%%L"
  if not "!PREVIEW:~200,1!"=="" goto :preview_done
)
:preview_done
set "PREVIEW=!PREVIEW:~0,200!"
echo 1: !PREVIEW!
echo Numbered header/body preview:
for /f "usebackq delims=" %%L in (`findstr /n "^" "%TMP%"`) do (
  echo %%L
  set /a __lines+=1 >nul 2>nul
  if !__lines! geq 12 goto :lines_done
)
:lines_done
set "__lines=0"

del /f /q "%TMP%" >nul 2>nul
exit /b 0
