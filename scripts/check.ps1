# Runs every quality gate once (no watch mode): lint, format, types, tests, build.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$failed = @()

function Step($name, $dir, [scriptblock]$command) {
    Write-Host "==> $name"
    Push-Location "$root\$dir"
    try {
        & $command
        if ($LASTEXITCODE -ne 0) { $script:failed += $name }
    } finally { Pop-Location }
}

$py = ".\.venv\Scripts\python.exe"
Step "backend: ruff lint"   "backend"  { & $py -m ruff check . }
Step "backend: ruff format" "backend"  { & $py -m ruff format --check . }
Step "backend: mypy"        "backend"  { & $py -m mypy }
Step "backend: pytest"      "backend"  { & $py -m pytest -q }
Step "frontend: eslint"     "frontend" { npm run lint }
Step "frontend: prettier"   "frontend" { npm run format:check }
Step "frontend: vitest"     "frontend" { npm run test }
Step "frontend: build"      "frontend" { npm run build }

if ($failed.Count -gt 0) {
    Write-Host "FAILED: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "All checks passed." -ForegroundColor Green
