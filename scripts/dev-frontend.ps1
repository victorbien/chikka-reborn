# Starts the Vite dev server on http://localhost:5173.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\frontend"
try {
    npm run dev
} finally { Pop-Location }
