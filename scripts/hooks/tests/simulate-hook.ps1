# Simulates how Kiro calls a command hook: JSON on stdin, run.ps1 as the command.
#   scripts\hooks\tests\simulate-hook.ps1 -Check quality -File backend/app/core/storage_paths.py
#   scripts\hooks\tests\simulate-hook.ps1 -Check guard-shell -Command "git push origin main"
#   scripts\hooks\tests\simulate-hook.ps1 -Check guard-write -File backend/.env -Text "X=1"
param(
    [Parameter(Mandatory = $true)][string]$Check,
    [string]$File = "",
    [string]$Command = "",
    [string]$Text = ""
)

$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$payload = [ordered]@{ hook_event_name = "simulated"; cwd = $root }
if ($File) { $payload["file_path"] = Join-Path $root $File }
if ($Check -like "guard-*") {
    $payload["tool_name"] = if ($Check -eq "guard-shell") { "execute_pwsh" } else { "fs_write" }
    $input_ = [ordered]@{}
    if ($Command) { $input_["command"] = $Command }
    if ($File) { $input_["path"] = $File }
    if ($Text) { $input_["text"] = $Text }
    $payload["tool_input"] = $input_
}
$json = $payload | ConvertTo-Json -Depth 5 -Compress

$timer = [Diagnostics.Stopwatch]::StartNew()
$json | & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root "scripts\hooks\run.ps1") $Check --print
$code = $LASTEXITCODE
$timer.Stop()
"exit=$code seconds=$([math]::Round($timer.Elapsed.TotalSeconds, 1))  (0 = allow or report only, 2 = blocked)"
