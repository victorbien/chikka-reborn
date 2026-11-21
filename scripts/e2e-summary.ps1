# Prints a compact pass/fail table from the Playwright JSON report (frontend/e2e-results/results.json).
param([string]$Report = (Join-Path (Split-Path -Parent $PSScriptRoot) "frontend\e2e-results\results.json"))
$json = Get-Content $Report -Raw | ConvertFrom-Json

function Walk($suite, $trail) {
    $name = if ($suite.title) { $trail + @($suite.title) } else { $trail }
    foreach ($spec in $suite.specs) {
        foreach ($test in $spec.tests) {
            $result = $test.results | Select-Object -Last 1
            $message = ""
            if ($result.status -ne "passed" -and $result.error.message) {
                $message = ($result.error.message -replace "\x1b\[[0-9;]*m", "" -split "`n" | Select-Object -First 4) -join " | "
            }
            [pscustomobject]@{ Status = $result.status; Ms = $result.duration; Title = ($name + @($spec.title)) -join " > "; Error = $message }
        }
    }
    foreach ($child in $suite.suites) { Walk $child $name }
}

$rows = foreach ($suite in $json.suites) { Walk $suite @() }
$rows | ForEach-Object { "{0,-9} {1,6}ms  {2}" -f $_.Status, $_.Ms, $_.Title; if ($_.Error) { "          -> " + $_.Error } }
"--- passed={0} failed={1} skipped={2} total={3}" -f ($rows | ? Status -eq "passed").Count, ($rows | ? { $_.Status -in "failed", "timedOut" }).Count, ($rows | ? Status -eq "skipped").Count, $rows.Count
