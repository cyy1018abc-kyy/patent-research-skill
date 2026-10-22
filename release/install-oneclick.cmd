@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title patent-research 技能一键安装

rem ============================================================
rem  用法：把本文件与 patent-research-skill-v*.zip、
rem        patentkit-*.whl 放在同一个文件夹，双击运行。
rem  作用：检查 Python → 装内核 wheel → 解压技能包 → 调 install.ps1 安装。
rem  退出码：0 成功；1 缺文件/环境问题；2 安装脚本失败。
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
echo   专利调研技能 · 一键安装（Windows）
echo ===============================================
echo.

rem ---------- 1. 找 Python ----------
rem 优先用 PATH 里的 python（与 install.ps1/技能脚本一致），没有再退回 py -3
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
    echo [X] 没找到 Python 3.11+。
    echo     请到 https://www.python.org/downloads/ 安装，安装时勾选
    echo     "Add Python to PATH"，然后重开本窗口再试。
    goto :fail
)
for /f "delims=" %%p in ('%PY% -c "import sys,os; print(os.path.dirname(sys.executable))"') do set "PYDIR=%%p"
if defined PYDIR set "PATH=%PYDIR%;%PATH%"
echo [1/4] Python: OK
%PY% --version
echo       解释器: %PYDIR%

rem ---------- 2. 找文件 ----------
for %%f in ("patentkit-*.whl") do set "WHEEL=%%~ff"
if not defined WHEEL (
    echo [X] 当前文件夹没有 patentkit-*.whl（内核包）。
    echo     请把 patentkit-0.1.1-py3-none-any.whl 与本文件放在同一文件夹。
    goto :fail
)
for %%f in ("patent-research-skill-v*.zip") do set "SKILLZIP=%%~ff"
if not defined SKILLZIP (
    echo [X] 当前文件夹没有 patent-research-skill-v*.zip（技能包）。
    echo     请把技能包 zip 与本文件放在同一文件夹。
    goto :fail
)
echo [2/4] 找到文件: OK
echo       内核: %WHEEL%
echo       技能: %SKILLZIP%

rem ---------- 3. 装内核 ----------
echo.
echo [3/4] 安装内核 patentkit ...
%PY% -m pip install --upgrade "%WHEEL%"
if errorlevel 1 (
    echo     [!] 默认安装失败，尝试 --user ...
    %PY% -m pip install --user --upgrade "%WHEEL%"
    if errorlevel 1 (
        echo [X] 内核安装失败。常见原因：网络/权限。
        echo     请把上面的 pip 报错原样发给技术支持。
        goto :fail
    )
)
%PY% -c "import patentkit; print('    内核版本:', patentkit.__version__)"
if errorlevel 1 (
    echo [X] 内核装上了但 import 失败，请检查 pip 环境。
    goto :fail
)

rem ---------- 4. 解压并安装技能 ----------
echo.
echo [4/4] 解压并安装技能包 ...
set "TMPDIR=%TEMP%\patent-research-install-%RANDOM%%RANDOM%"
mkdir "%TMPDIR%" >nul 2>nul
%PY% -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "%SKILLZIP%" "%TMPDIR%"
if errorlevel 1 (
    echo [X] 解压失败：%SKILLZIP%
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
    echo [X] 安装脚本失败，请把上面的报错原样发给技术支持。
    set "INSTALL_DIR=%TMPDIR%"
    goto :fail
)

rem 清理临时目录
rd /s /q "%TMPDIR%" >nul 2>nul

echo.
echo ===============================================
echo   [OK] 安装成功
echo ===============================================
echo.
echo   下一步：
echo     1) 重启 Codex 桌面端 或 Claude Code
echo     2) Codex 桌面端：侧边栏 Skills 里选「专利调研」，或用 @ 选择
echo     3) Claude Code：说「按 patent-research 技能，先定位工作区并自检」
echo.
echo   验收 5 条见发布包里的《安装说明-给同事.md》第 4 节。
echo.
if not defined QUIET pause
exit /b 0

:fail
echo.
echo 安装未完成。排查建议见发布包里的《安装说明-给同事.md》第 5 节。
echo.
if not defined QUIET pause
exit /b 1
