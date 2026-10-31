@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title patent-research Skill One-Click Install

rem ============================================================
rem  Usage: put this file together with patent-research-skill-v*.zip
rem         and patentkit-*.whl in the same folder, then double-click it.
rem  What it does: check Python -> install the kernel wheel -> unzip the skill package -> run install.ps1.
rem  Exit codes: 0 success; 1 missing files/environment problem; 2 install script failed.
rem ============================================================

set "QUIET="
set "DEST="
set "HERE=%~dp0"
:args
if "%~1"=="" goto :args_done
if /i "%~1"=="--quiet" (
    set "QUIET=1"
    shift
    goto :args
)
if /i "%~1"=="--dest" (
    if "%~2"=="" goto :fail
    set "DEST=%~2"
    shift
    shift
    goto :args
)
echo [X] Unknown argument: %~1
goto :fail
:args_done
cd /d "%HERE%"

set "WHEEL="
set "SKILLZIP="
set "PY="
set "PYDIR="

echo ===============================================
echo   Patent Research Skill · One-Click Install (Windows)
echo ===============================================
echo.

rem ---------- 1. Find Python ----------
rem Prefer python from PATH (consistent with install.ps1/the skill scripts); fall back to py -3
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
    echo [X] Python 3.11+ not found.
    echo     Please install it from https://www.python.org/downloads/ and check
    echo     "Add Python to PATH" during installation, then reopen this window and retry.
    goto :fail
)
for /f "delims=" %%p in ('%PY% -c "import sys,os; print(os.path.dirname(sys.executable))"') do set "PYDIR=%%p"
if defined PYDIR set "PATH=%PYDIR%;%PATH%"
echo [1/4] Python: OK
%PY% --version
echo       interpreter: %PYDIR%

rem ---------- 2. Find the files ----------
for %%f in ("patentkit-0.10.0-py3-none-any.whl") do if exist "%%~ff" set "WHEEL=%%~ff"
if not defined WHEEL (
    echo [X] There is no patentkit-*.whl kernel package in the current folder.
    echo     Please put patentkit-0.10.0-py3-none-any.whl in the same folder as this file.
    goto :fail
)
for %%f in ("patent-research-skill-v3.10.0.zip") do if exist "%%~ff" set "SKILLZIP=%%~ff"
if not defined SKILLZIP (
    echo [X] There is no patent-research-skill-v*.zip skill package in the current folder.
    echo     Please put the skill package zip in the same folder as this file.
    goto :fail
)
echo [2/4] Files found: OK
echo       kernel: %WHEEL%
echo       skill : %SKILLZIP%

rem ---------- 3. Install the kernel ----------
echo.
echo [3/4] Installing the patentkit kernel ...
%PY% -m pip install --upgrade "%WHEEL%"
if errorlevel 1 (
    echo     [!] Default install failed; trying --user ...
    %PY% -m pip install --user --upgrade "%WHEEL%"
    if errorlevel 1 (
        echo [X] Kernel installation failed. Common causes: network/permissions.
        echo     Please send the pip error above verbatim to technical support.
        goto :fail
    )
)
%PY% -c "import patentkit; from patentkit.assessment import PROTOCOL_VERSION; assert PROTOCOL_VERSION == 1; print('    kernel version:', patentkit.__version__)"
if errorlevel 1 (
    echo [X] The kernel was installed but import failed; please check the pip environment.
    goto :fail
)

rem ---------- 4. Unzip and install the skill ----------
echo.
echo [4/4] Unzipping and installing the skill package ...
set "TMPDIR=%TEMP%\patent-research-install-%RANDOM%%RANDOM%"
mkdir "%TMPDIR%" >nul 2>nul
%PY% -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "%SKILLZIP%" "%TMPDIR%"
if errorlevel 1 (
    echo [X] Failed to unzip: %SKILLZIP%
    goto :fail
)

set "PS=pwsh"
where pwsh >nul 2>nul
if errorlevel 1 set "PS=powershell"
if /i "%PS%"=="powershell" (
    if defined DEST (
        powershell -NoProfile -ExecutionPolicy Bypass -File "%TMPDIR%\install.ps1" -Dest "%DEST%" -Force
    ) else (
        powershell -NoProfile -ExecutionPolicy Bypass -File "%TMPDIR%\install.ps1" -Client both -Force
    )
) else (
    if defined DEST (
        pwsh -NoProfile -File "%TMPDIR%\install.ps1" -Dest "%DEST%" -Force
    ) else (
        pwsh -NoProfile -File "%TMPDIR%\install.ps1" -Client both -Force
    )
)
if errorlevel 1 (
    echo.
    echo [X] The install script failed; please send the error above verbatim to technical support.
    set "INSTALL_DIR=%TMPDIR%"
    goto :fail
)

rem Clean up the temporary directory
rd /s /q "%TMPDIR%" >nul 2>nul

echo.
echo ===============================================
echo   [OK] Installation succeeded
echo ===============================================
echo.
echo   Next steps:
echo     1) Restart Codex desktop or Claude Code
echo     2) Codex desktop: pick "Patent Research" in the sidebar Skills, or select it with @
echo     3) Claude Code: say "follow the patent-research skill; first locate the workspace and run a self-check"
echo.
echo   For the 5 acceptance checks, see section 4 of install-guide-for-colleagues.md in the release package.
echo.
if not defined QUIET pause
exit /b 0

:fail
echo.
echo Installation did not complete. For troubleshooting, see section 5 of install-guide-for-colleagues.md in the release package.
echo.
if not defined QUIET pause
exit /b 1
