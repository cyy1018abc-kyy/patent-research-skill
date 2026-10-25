#Requires -Version 5.1
<#
.SYNOPSIS
  Install / uninstall the patent skills bundled with the release package (multi-skill).

.DESCRIPTION
  按 manifest.json 的 skills 列表，把每个技能目录（patent-research/、patent-drafting/…）
  复制到本地 AI 客户端的技能目录；目录名 = SKILL.md 的 name。
  安装后自动用包内 samples/sample_workspace/ 自检（需要 patentkit；单技能包无样例时
  自检降级为「SKILL.md 就位」检查）。

  Exit codes: 0 success; 1 failure (self-check failed / target already exists, etc.); 2 release package structure incomplete.

.EXAMPLE
  pwsh -File .\install.ps1 -DryRun
  Preview: changes no files, only prints where it would install.

.EXAMPLE
  pwsh -File .\install.ps1 -Client both
  Install into both Claude Code (~/.claude/skills) and Codex CLI (~/.agents/skills).

.EXAMPLE
  pwsh -File .\install.ps1 -Dest <skills-root>
  Install into a custom skills root (creates patent-research\ and patent-drafting\ under it).

.EXAMPLE
  pwsh -File .\install.ps1 -Uninstall -Client both
  Uninstall from both default locations.
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
    Fail "manifest.json not found — please run this script from the root of the unzipped release package (current: $PackageRoot)" 2
}
try {
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Fail "failed to parse manifest.json: $($_.Exception.Message)" 2
}

if ($manifest.schema_version -ne 2 -or -not $manifest.skills -or $manifest.skills.Count -lt 1) {
    Fail "manifest.json must be schema 2 with a non-empty skills list" 2
}
$skillDirs = @()
foreach ($entry in $manifest.skills) {
    if ([string]$entry.install_dir -ne [string]$entry.name -or @('patent-research', 'patent-drafting') -notcontains [string]$entry.name) {
        Fail "unsupported skill entry in manifest.json: $($entry.name)" 2
    }
    $skillDirs += [string]$entry.name
}
$skillVersion = [string]$manifest.skills[0].version

# Skills root: -Dest takes precedence; otherwise use the client default selected by -Client
if ($Dest -ne '') {
    $roots = @($Dest)
} else {
    switch ($Client) {
        'claude' { $roots = @((Join-Path $HOME '.claude/skills')) }
        'codex'  { $roots = @((Join-Path $HOME '.agents/skills')) }
        'both'   { $roots = @((Join-Path $HOME '.claude/skills'), (Join-Path $HOME '.agents/skills')) }
    }
}

$sampleRoot = Join-Path $PackageRoot "samples/sample_workspace"
$mode = if ($Uninstall) { 'Uninstall' } else { 'Install' }
Write-Host ""
Write-Host "patent-research-skill v$skillVersion  ·  $mode (multi-skill)"
Write-Host "Skills     : $($skillDirs -join '  ')"
Write-Host "Targets    : $($roots -join '  ;  ')"
if ($DryRun) { Write-Host "Mode       : DRY-RUN (no files are changed)" }
Write-Host ""

if ($Uninstall) {
    $removed = 0
    foreach ($root in $roots) {
        foreach ($dir in $skillDirs) {
            $target = Join-Path $root $dir
            if (-not (Test-Path -LiteralPath $target)) {
                Note "not installed: $target"
                continue
            }
            if ($DryRun) {
                Note "[dry-run] would delete: $target"
                continue
            }
            Remove-Item -LiteralPath $target -Recurse -Force
            Write-Host "✅ Uninstalled: $target"
            $removed++
        }
    }
    if ($DryRun) { Note "dry-run finished: no files deleted" }
    elseif ($removed -eq 0) { Note "no installed skill package found (try a different -Client / -Dest)" }
    exit 0
}

foreach ($dir in $skillDirs) {
    $payload = Join-Path $PackageRoot $dir
    if (-not (Test-Path -LiteralPath $payload -PathType Container)) {
        Fail "release package is missing the payload directory: $dir (the zip may not have been fully extracted)" 2
    }
}

$python = $null
if (-not $DryRun -and -not $NoSelfCheck) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $python) { Fail "Python 3.11+ with patentkit 0.4.0 is required before installation" }
    & $python.Source '-c' 'import sys; from patentkit.assessment import PROTOCOL_VERSION; assert sys.version_info >= (3, 11) and PROTOCOL_VERSION == 1' | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "Install the patentkit 0.4.0 wheel before replacing the skill" }
}

$installedAny = @()
foreach ($root in $roots) {
    foreach ($dir in $skillDirs) {
        $payload = Join-Path $PackageRoot $dir
        $target = Join-Path $root $dir

        if (Test-Path -LiteralPath $target) {
            if (-not $Force) {
                Fail "target already exists: $target`n  Upgrade: run -Uninstall first and then install; or add -Force to overwrite it."
            }
            if ($DryRun) {
                Note "[dry-run] would overwrite: $target"
            } else {
                Remove-Item -LiteralPath $target -Recurse -Force
            }
        }

        if ($DryRun) {
            Note "[dry-run] would copy: $payload  ->  $target"
            continue
        }

        New-Item -ItemType Directory -Force -Path $target | Out-Null
        Copy-Item -Path (Join-Path $payload '*') -Destination $target -Recurse -Force
        Write-Host "✅ Installed: $target"
        $installedAny += $target
    }
}

if ($DryRun) {
    Note "dry-run finished: no files written"
    exit 0
}

if (-not $NoSelfCheck) {
    Write-Host ""
    Write-Host "Self-check (no real data touched)..."
    if (Test-Path -LiteralPath $sampleRoot) {
        $probe = Join-Path $roots[0] 'patent-research'
        $statusScript = Join-Path $probe 'scripts/status.py'
        & $python.Source $statusScript --root $sampleRoot --json | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Fail "self-check failed (exit $LASTEXITCODE). Install the matching patentkit 0.4.0 wheel and retry"
        }
        Write-Host "✅ Self-check passed: status.py located the sample workspace and computed the status"
    } else {
        # 单技能包（无样例）：退化为就位检查
        foreach ($dir in $skillDirs) {
            if (-not (Test-Path -LiteralPath (Join-Path $roots[0] "$dir/SKILL.md")) ) {
                Fail "self-check failed: $(Join-Path $roots[0] "$dir/SKILL.md") missing"
            }
        }
        Write-Host "✅ Self-check passed: SKILL.md in place for $($skillDirs -join ' ') (no sample workspace in this package)"
    }
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1) In the client, say 'run a patent novelty check' or 'show the workspace status' (patent-research)"
Write-Host "  2) Drafting/OA work: 'draft a disclosure from the search results' (patent-drafting)"
Write-Host "  3) No workspace yet? python -m patentkit init <dir> --target TGT-0002 --title <title>"
Write-Host "  4) With a real workspace, the skill uses PATENTKIT_WORKSPACE or walks up from the current directory to find workspace.yml"
exit 0
