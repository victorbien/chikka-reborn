# Verifies the frontend's hosted-build guard and the bundle's contents. Safe to run locally:
# it builds into a temporary folder and removes it.
#   scripts\verify-hosted-build.ps1 -ApiUrl https://api.example.com
param([string]$ApiUrl = "https://api.example.com")

$ErrorActionPreference = "Stop"
$frontend = Join-Path $PSScriptRoot "..\frontend"
$out = "dist-verify"
$failures = @()

function Invoke-Build([string]$appEnv, [string]$url) {
    $env:VITE_APP_ENV = $appEnv
    if ($url) { $env:VITE_API_BASE_URL = $url } else { Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue }
    $text = (cmd /c "node node_modules\vite\bin\vite.js build --outDir $out 2>&1") | Out-String
    return [pscustomobject]@{ Ok = ($LASTEXITCODE -eq 0); Text = $text }
}

Push-Location $frontend
try {
    $r = Invoke-Build "production" ""
    if ($r.Ok) { $failures += "build without VITE_API_BASE_URL should fail" } else { "ok   build without an API URL is refused" }

    $r = Invoke-Build "production" "http://api.example.com"
    if ($r.Ok) { $failures += "build with an http API URL should fail" } else { "ok   build with an http API URL is refused" }

    $r = Invoke-Build "production" $ApiUrl
    if (-not $r.Ok) { $failures += "build with a valid https API URL failed: $($r.Text)" } else {
        "ok   build with $ApiUrl succeeds"
        $js = Get-ChildItem "$out\assets\*.js"
        if (-not (Select-String -Path $js -Pattern $ApiUrl -SimpleMatch -List)) { $failures += "API URL not found in bundle" } else { "ok   API URL is compiled into the bundle" }
        $leak = Select-String -Path $js -Pattern "SERVICE_ROLE|sb_secret|TWILIO_AUTH|BEDROCK_API" -List
        if ($leak) { $failures += "bundle mentions a backend secret name" } else { "ok   no backend secret names in the bundle" }
        foreach ($f in "index.html", "favicon.svg", "robots.txt") {
            if (-not (Test-Path "$out\$f")) { $failures += "missing $f in output" } else { "ok   $f present" }
        }
    }
}
finally {
    Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
    Remove-Item Env:VITE_APP_ENV, Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
    Pop-Location
}

if ($failures.Count) { $failures | ForEach-Object { "FAIL $_" }; exit 1 }
"ALL OK"
