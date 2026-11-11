# Starts the FastAPI backend with auto-reload on http://localhost:8000 (docs at /docs).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\backend"
try {
    & .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
} finally { Pop-Location }
