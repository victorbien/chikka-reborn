# Runs the Playwright browser suite (frontend/e2e) against a throwaway local stack.
#   .\scripts\e2e-browser.ps1                      # whole suite
#   .\scripts\e2e-browser.ps1 sms.e2e.ts           # selected spec files / any playwright arguments
# Playwright starts PGlite, the fake Supabase, the API and Vite itself (see frontend/playwright.config.ts).
# If an earlier run was interrupted its servers can still hold the ports; this script frees them
# first and again afterwards, so a stale process never blocks or pollutes a run.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$PlaywrightArgs)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$ports = 54329, 54400, 8010, 5173

function Stop-StackProcesses {
    foreach ($port in $ports) {
        Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    }
    Start-Sleep -Milliseconds 800
}

Stop-StackProcesses
Push-Location "$root\frontend"
try {
    npx playwright test @PlaywrightArgs
    $code = $LASTEXITCODE
} finally {
    Pop-Location
    Stop-StackProcesses
}
exit $code
