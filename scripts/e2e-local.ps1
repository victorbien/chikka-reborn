# Local end-to-end check of the auth module across real processes:
#   PGlite (all migrations) -> fake Supabase Auth/Storage -> uvicorn backend -> frontend API client.
# Simulation mode only. Nothing leaves 127.0.0.1. All secrets below are throwaway test values.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

$dbPort = 54329
$fakePort = 54400
$apiPort = 8010
$dbUrl = "postgresql+asyncpg://postgres:postgres@127.0.0.1:$dbPort/postgres"

$env:SUPABASE_JWT_SECRET = "e2e-only-jwt-secret-with-at-least-32-bytes"
$env:SUPABASE_ANON_KEY = "e2e-anon-key"
$env:SUPABASE_SERVICE_ROLE_KEY = "e2e-service-role-key"

$procs = @()
function Wait-Http($url, $seconds = 60) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try { Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 2 | Out-Null; return } catch { Start-Sleep -Milliseconds 500 }
    }
    throw "Timed out waiting for $url"
}

try {
    Write-Host "==> database (PGlite)"
    $procs += Start-Process node -ArgumentList "serve-db.mjs", "--port=$dbPort" -WorkingDirectory "$root\supabase\tools" -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        $tcp = New-Object Net.Sockets.TcpClient
        try { $tcp.Connect("127.0.0.1", $dbPort); $tcp.Close(); break } catch { Start-Sleep -Milliseconds 500 }
    }

    Write-Host "==> fake Supabase Auth and Storage"
    $procs += Start-Process $py -ArgumentList "-m", "tests.support.run_fake_supabase", "--port", "$fakePort", "--database-url", $dbUrl -WorkingDirectory "$root\backend" -PassThru -WindowStyle Hidden
    Wait-Http "http://127.0.0.1:$fakePort/__outbox?to=nobody@example.com"

    Write-Host "==> backend (uvicorn)"
    $env:APP_ENV = "development"
    $env:DATABASE_URL = $dbUrl
    $env:DB_POOL_SIZE = "4"
    $env:DB_MAX_OVERFLOW = "0"
    $env:SUPABASE_URL = "http://127.0.0.1:$fakePort"
    $env:APP_SECRET_KEY = "e2e-only-app-secret-key-0123456789"
    $env:SMS_PROVIDER_MODE = "mock"
    $env:CORS_ORIGINS = "http://localhost:5173"
    $procs += Start-Process $py -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "$apiPort" -WorkingDirectory "$root\backend" -PassThru -WindowStyle Hidden -RedirectStandardOutput "$env:TEMP\chikka-e2e-api.log" -RedirectStandardError "$env:TEMP\chikka-e2e-api.err"
    Wait-Http "http://127.0.0.1:$apiPort/api/v1/health"

    Write-Host "==> CORS preflight from the SPA origin"
    $pre = Invoke-WebRequest "http://127.0.0.1:$apiPort/api/v1/auth/refresh" -Method Options -UseBasicParsing -Headers @{
        Origin = "http://localhost:5173"; "Access-Control-Request-Method" = "POST"; "Access-Control-Request-Headers" = "x-chikka-csrf,content-type"
    }
    if ($pre.Headers["Access-Control-Allow-Credentials"] -ne "true" -or $pre.Headers["Access-Control-Allow-Origin"] -ne "http://localhost:5173") {
        throw "CORS preflight did not allow the SPA origin with credentials"
    }
    Write-Host "    allowed with credentials"

    Write-Host "==> frontend service layer against the live API"
    $env:LIVE_API_URL = "http://127.0.0.1:$apiPort"
    $env:LIVE_FAKE_SUPABASE_URL = "http://127.0.0.1:$fakePort"
    Push-Location "$root\frontend"
    try {
        npx vitest --run src/test/live
        if ($LASTEXITCODE -ne 0) { throw "live end-to-end tests failed" }
    } finally { Pop-Location }

    $leaks = Select-String -Path "$env:TEMP\chikka-e2e-api.log" -Pattern "Correct-Horse|Brand-New-Pass|Bearer ey" -SimpleMatch:$false
    if ($leaks) { throw "secrets found in API logs" }
    Write-Host "    API log checked: no passwords or tokens"
    Write-Host "End-to-end check passed." -ForegroundColor Green
} finally {
    foreach ($p in $procs) { if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
    Remove-Item Env:LIVE_API_URL, Env:LIVE_FAKE_SUPABASE_URL -ErrorAction SilentlyContinue
}
