# One-time local setup: backend virtualenv + dependencies, frontend dependencies,
# and local env files copied from the committed examples (never overwritten).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "==> Backend: virtualenv and dependencies"
Push-Location "$root\backend"
try {
    if (-not (Test-Path ".venv")) { python -m venv .venv }
    & .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency install failed" }
    if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created backend\.env" }
} finally { Pop-Location }

Write-Host "==> Frontend: dependencies"
Push-Location "$root\frontend"
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency install failed" }
    if (-not (Test-Path ".env.local")) { Copy-Item ".env.example" ".env.local"; Write-Host "Created frontend\.env.local" }
} finally { Pop-Location }

Write-Host "Setup complete. Run scripts\dev-backend.ps1 and scripts\dev-frontend.ps1 in two terminals."
