#Requires -Version 5.1
<#
.SYNOPSIS
  Install / uninstall patent-research-skill (bundled with the release package).

.DESCRIPTION
  Copies `patent-research/` from the release package into the local AI client's skills directory;
  the default directory name = the `name` in `SKILL.md` (clients identify the skill by it).
  After installation it automatically runs a self-check using the package's `samples/sample_workspace/` (requires patentkit to be installed).

  Exit codes: 0 success; 1 failure (self-check failed / target already exists, etc.); 2 release package structure incomplete.

.EXAMPLE
  pwsh -File .\install.ps1 -DryRun
  Preview: changes no files, only prints where it would install.

.EXAMPLE
  pwsh -File .\install.ps1 -Client both
  Install into both Claude Code (~/.claude/skills) and Codex CLI (~/.agents/skills).

.EXAMPLE
  pwsh -File .\install.ps1 -Dest <skills-root>
  Install into a custom skills root (creates patent-research\ under it).

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

$skillName = [string]$manifest.skill.name
$skillVersion = [string]$manifest.skill.version
$installDirName = [string]$manifest.skill.install_dir
if (-not $skillName -or -not $installDirName) {
    Fail "manifest.json is missing skill.name / skill.install_dir" 2
}
if ($installDirName -ne $skillName) {
    Fail "manifest is self-contradictory: install_dir ($installDirName) must equal name ($skillName)" 2
}

$payload = Join-Path $PackageRoot $installDirName

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
Write-Host "patent-research-skill v$skillVersion  ·  $mode"
Write-Host "Skill name : $skillName (the install directory name must match)"
Write-Host "Targets    : $($roots -join '  ;  ')"
if ($DryRun) { Write-Host "Mode       : DRY-RUN (no files are changed)" }
Write-Host ""

if ($Uninstall) {
    $removed = 0
    foreach ($root in $roots) {
        $target = Join-Path $root $installDirName
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
    if ($DryRun) { Note "dry-run finished: no files deleted" }
    elseif ($removed -eq 0) { Note "no installed skill package found (try a different -Client / -Dest)" }
    exit 0
}

if (-not (Test-Path -LiteralPath $payload -PathType Container)) {
    Fail "release package is missing the payload directory: $installDirName (the zip may not have been fully extracted)" 2
}

$installedTargets = @()
foreach ($root in $roots) {
    $target = Join-Path $root $installDirName

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
    $installedTargets += $target
}

if ($DryRun) {
    Note "dry-run finished: no files written"
    exit 0
}

if (-not $NoSelfCheck) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $python) {
        Fail "Installation completed, but python was not found: the skill scripts need Python ≥ 3.11 + patentkit.`n  Fix: install Python, then run  pip install patentkit"
    }

    $probe = $installedTargets[0]
    $statusScript = Join-Path $probe 'scripts/status.py'
    Write-Host ""
    Write-Host "Self-check (using the package's sample workspace; no real data touched)..."
    if (Test-Path -LiteralPath $sampleRoot) {
        & $python.Source $statusScript --root $sampleRoot --json | Out-Null
    } else {
        & $python.Source '-c' 'import patentkit' | Out-Null
    }
    if ($LASTEXITCODE -ne 0) {
        Fail "self-check failed (exit $LASTEXITCODE). Most likely the patentkit core is not installed: pip install patentkit"
    }
    Write-Host "✅ Self-check passed: the scripts can locate the workspace and compute the status"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1) In the client, say 'run a patent novelty check' or 'show the workspace status'"
Write-Host "  2) No workspace yet? python -m patentkit init <dir> --target TGT-0002 --title <title>"
Write-Host "  3) With a real workspace, the skill uses PATENTKIT_WORKSPACE or walks up from the current directory to find workspace.yml"
exit 0
