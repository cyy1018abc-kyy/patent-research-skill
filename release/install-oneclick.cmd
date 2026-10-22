@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title patent-research skill one-click installer

rem ============================================================
rem  Usage: put this file, patent-research-skill-v*.zip and
rem        patentkit-*.whl in one folder and double-click this file.
rem  Flow: check Python -> install kernel wheel -> extract skill -> run install.ps1.
rem  Exit codes: 0 success; 1 missing files/environment; 2 installer failed.
rem ============================================================

set "QUIET="
if /i "%~1"=="--quiet" set "QUIET=1"
cd /d "%~dp0"

set "HERE=%~dp0"
set "WHEEL="
set "SKILLZIP="
set "PY="
set "PYDIR="

echo ===============================================
echo   patent-research skill - one-click installer (Windows)
echo ===============================================
echo.

rem ---------- 1. locate Python ----------
rem Prefer python from PATH (same as install.ps1/scripts); fall back to py -3
where python >nul 2>nul
if not errorlevel 1 (
    python -c "import sys; assert sys.version_info >= (3, 11)" >nul 2>nul
    if not errorlevel 1 set "PY=python"
)
if not defined PY (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "import sys; assert sys.version_info >= (3, 11)" >nul 2>nul
        if not errorlevel 1 set "PY=py -3"
    )
)
if not defined PY (
    echo [X] Python 3.11+ was not found.
    echo     Install from https://www.python.org/downloads/ and enable
    echo     "Add Python to PATH", then reopen this window and retry.
    goto :fail
)
for /f "delims=" %%p in ('%PY% -c "import sys,os; print(os.path.dirname(sys.executable))"') do set "PYDIR=%%p"
if defined PYDIR set "PATH=%PYDIR%;%PATH%"
echo [1/4] Python: OK
%PY% --version
echo       Interpreter: %PYDIR%

rem ---------- 2. locate files ----------
for %%f in ("patentkit-*.whl") do set "WHEEL=%%~ff"
if not defined WHEEL (
    echo [X] patentkit-*.whl kernel file is not in the current folder.
    echo     Put patentkit-0.1.1-py3-none-any.whl next to this file.
    goto :fail
)
for %%f in ("patent-research-skill-v*.zip") do set "SKILLZIP=%%~ff"
if not defined SKILLZIP (
    echo [X] patent-research-skill-v*.zip skill package is not in the current folder.
    echo     Put the skill zip next to this file.
    goto :fail
)
echo [2/4] Files found: OK
echo       Kernel: %WHEEL%
echo       Skill: %SKILLZIP%

rem ---------- 3. install kernel ----------
echo.
echo [3/4] Installing kernel patentkit ...
%PY% -m pip install --upgrade "%WHEEL%"
if errorlevel 1 (
    echo     [!] Default install failed; retrying with --user ...
    %PY% -m pip install --user --upgrade "%WHEEL%"
    if errorlevel 1 (
        echo [X] Kernel installation failed. Common causes: network/permissions.
        echo     Send the pip error above to your support contact.
        goto :fail
    )
)
%PY% -c "import patentkit; print('    Kernel version:', patentkit.__version__)"
if errorlevel 1 (
    echo [X] Kernel installed but import failed; check the pip environment.
    goto :fail
)

rem ---------- 4. extract and install skill ----------
echo.
echo [4/4] Extracting and installing the skill package ...
set "TMPDIR=%TEMP%\patent-research-install-%RANDOM%%RANDOM%"
mkdir "%TMPDIR%" >nul 2>nul
%PY% -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "%SKILLZIP%" "%TMPDIR%"
if errorlevel 1 (
    echo [X] Extraction failed: %SKILLZIP%
    goto :fail
)

set "PS=pwsh"
where pwsh >nul 2>nul
if errorlevel 1 set "PS=powershell"
if /i "%PS%"=="powershell" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%TMPDIR%\install.ps1" -Client both -Force
) else (
    pwsh -NoProfile -File "%TMPDIR%\install.ps1" -Client both -Force
)
if errorlevel 1 (
    echo.
    echo [X] Installer failed; send the error above to your support contact.
    set "INSTALL_DIR=%TMPDIR%"
    goto :fail
)

rem clean up temporary directory
rd /s /q "%TMPDIR%" >nul 2>nul

echo.
echo ===============================================
echo   [OK] Installation succeeded
echo ===============================================
echo.
echo   Next steps:
echo     1) Restart the Codex desktop app or Claude Code
echo     2) Codex desktop: open Skills in the sidebar and select "Patent Research", or use @
echo     3) Claude Code: ask "use the patent-research skill; locate the workspace and run the self-check"
echo.
echo   See section 4 of INSTALL-colleagues.md for the five acceptance checks.
echo.
if not defined QUIET pause
exit /b 0

:fail
echo.
echo Installation incomplete. See section 5 of INSTALL-colleagues.md for troubleshooting.
echo.
if not defined QUIET pause
exit /b 1
