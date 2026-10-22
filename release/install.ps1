#Requires -Version 5.1
<#
.SYNOPSIS
  安装 / 卸载 patent-research-skill（发布包内自带）。

.DESCRIPTION
  把发布包里的 `patent-research/` 复制到本地 AI 客户端的技能目录，
  默认目录名 = `SKILL.md` 的 name（客户端按这个识别技能）。
  安装后自动用包内 `samples/示例工作区/` 跑一次自检（需要已安装 patentkit）。

  退出码：0 成功；1 失败（自检不过/目标已存在等）；2 发布包结构不完整。

.EXAMPLE
  pwsh -File .\install.ps1 -DryRun
  预览：不改任何文件，只打印会装到哪里。

.EXAMPLE
  pwsh -File .\install.ps1 -Client both
  同时装到 Claude Code（~/.claude/skills）与 Codex CLI（~/.agents/skills）。

.EXAMPLE
  pwsh -File .\install.ps1 -Dest <技能根目录>
  装到自定义技能根目录（会在其下创建 patent-research\）。

.EXAMPLE
  pwsh -File .\install.ps1 -Uninstall -Client both
  从两个默认位置卸载。
#>
[CmdletBinding()]
param(
    [ValidateSet('claude', 'codex', 'both')]
    [string]$Client = 'claude',

    [string]$Dest = '',

    [switch]$Uninstall,
    [switch]$DryRun,
    [switch]$NoSelfCheck,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$PackageRoot = $PSScriptRoot
$ManifestPath = Join-Path $PackageRoot 'manifest.json'

function Fail {
    param([string]$Message, [int]$Code = 1)
    Write-Host "❌ $Message" -ForegroundColor Red
    exit $Code
}

function Note {
    param([string]$Message)
    Write-Host "  · $Message"
}

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    Fail "找不到 manifest.json —— 请在解压后的发布包根目录运行本脚本（当前：$PackageRoot）" 2
}
try {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Fail "manifest.json 解析失败：$($_.Exception.Message)" 2
}

$skillName = [string]$manifest.skill.name
$skillVersion = [string]$manifest.skill.version
$installDirName = [string]$manifest.skill.install_dir
if (-not $skillName -or -not $installDirName) {
    Fail "manifest.json 缺 skill.name / skill.install_dir" 2
}
if ($installDirName -ne $skillName) {
    Fail "manifest 自相矛盾：install_dir（$installDirName）必须等于 name（$skillName）" 2
}

$payload = Join-Path $PackageRoot $installDirName

# 技能根目录：优先 -Dest，否则按 -Client 取客户端默认位置
if ($Dest -ne '') {
    $roots = @($Dest)
} else {
    switch ($Client) {
        'claude' { $roots = @((Join-Path $HOME '.claude/skills')) }
        'codex'  { $roots = @((Join-Path $HOME '.agents/skills')) }
        'both'   { $roots = @((Join-Path $HOME '.claude/skills'), (Join-Path $HOME '.agents/skills')) }
    }
}

$sampleRoot = Join-Path $PackageRoot "samples/示例工作区"
$mode = if ($Uninstall) { '卸载' } else { '安装' }
Write-Host ""
Write-Host "patent-research-skill v$skillVersion  ·  $mode"
Write-Host "技能名   : $skillName（安装目录名必须一致）"
Write-Host "目标位置 : $($roots -join '  ;  ')"
if ($DryRun) { Write-Host "模式     : DRY-RUN（不改任何文件）" }
Write-Host ""

if ($Uninstall) {
    $removed = 0
    foreach ($root in $roots) {
        $target = Join-Path $root $installDirName
        if (-not (Test-Path -LiteralPath $target)) {
            Note "未安装：$target"
            continue
        }
        if ($DryRun) {
            Note "[dry-run] 将删除：$target"
            continue
        }
        Remove-Item -LiteralPath $target -Recurse -Force
        Write-Host "✅ 已卸载：$target"
        $removed++
    }
    if ($DryRun) { Note "dry-run 结束：没有删除任何文件" }
    elseif ($removed -eq 0) { Note "没有找到已安装的技能包（换 -Client / -Dest 再试）" }
    exit 0
}

if (-not (Test-Path -LiteralPath $payload -PathType Container)) {
    Fail "发布包缺 payload 目录：$installDirName（zip 可能没解压完整）" 2
}

$installedTargets = @()
foreach ($root in $roots) {
    $target = Join-Path $root $installDirName

    if (Test-Path -LiteralPath $target) {
        if (-not $Force) {
            Fail "目标已存在：$target`n  升级：先 -Uninstall 再安装；或加 -Force 直接覆盖。"
        }
        if ($DryRun) {
            Note "[dry-run] 将覆盖：$target"
        } else {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }

    if ($DryRun) {
        Note "[dry-run] 将复制：$payload  ->  $target"
        continue
    }

    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Copy-Item -Path (Join-Path $payload '*') -Destination $target -Recurse -Force
    Write-Host "✅ 已安装：$target"
    $installedTargets += $target
}

if ($DryRun) {
    Note "dry-run 结束：没有写入任何文件"
    exit 0
}

if (-not $NoSelfCheck) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $python) {
        Fail "安装完成，但没找到 python：技能脚本需要 Python ≥ 3.11 + patentkit。`n  修法：安装 Python 后执行  pip install patentkit"
    }

    $probe = $installedTargets[0]
    $statusScript = Join-Path $probe 'scripts/status.py'
    Write-Host ""
    Write-Host "自检（用包内示例工作区，不接触真实数据）..."
    if (Test-Path -LiteralPath $sampleRoot) {
        & $python.Source $statusScript --root $sampleRoot --json | Out-Null
    } else {
        & $python.Source '-c' 'import patentkit' | Out-Null
    }
    if ($LASTEXITCODE -ne 0) {
        Fail "自检失败（exit $LASTEXITCODE）。多半是没装 patentkit 内核：pip install patentkit"
    }
    Write-Host "✅ 自检通过：脚本能定位工作区并算出状态"
}

Write-Host ""
Write-Host "下一步："
Write-Host "  1) 在客户端里说「跑一遍专利新颖性核查」或「看看工作区状态」"
Write-Host "  2) 工作区还没有？python -m patentkit init <目录> --target TGT-0002 --title <名称>"
Write-Host "  3) 用真实工作区时，技能会用 PATENTKIT_WORKSPACE 或从当前目录向上找 workspace.yml"
exit 0
