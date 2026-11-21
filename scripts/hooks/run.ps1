# Launcher for the Kiro hook checks and for running them by hand.
#   scripts\hooks\run.ps1 <check> [options]
#   scripts\hooks\run.ps1 all --all --print          whole-project review
#   scripts\hooks\run.ps1 security --changed --print only files changed in git
#   scripts\hooks\run.ps1 architecture --update-baseline --all   accept today's findings
# Checks: quality tests docs security architecture all summary forget guard-write guard-shell
# Hooks pipe Kiro's JSON into this script on stdin. It always exits 0 in report mode so a
# finding never looks like a hook failure; guards use exit 2 (block) as Kiro defines.
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Check,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)

$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$venv = Join-Path $root "backend\.venv\Scripts\python.exe"
$python = if (Test-Path $venv) { $venv } else { "python" }

$stdin = ""
try { if ([Console]::IsInputRedirected) { $stdin = [Console]::In.ReadToEnd() } } catch { }

Push-Location $root
try {
    $stdin | & $python (Join-Path $PSScriptRoot "hookcheck.py") $Check @Rest
    exit $LASTEXITCODE
}
finally { Pop-Location }
