# Solar Unified — Windows one-shot installer
# Run in PowerShell:  ./install.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Checking prerequisites..." -ForegroundColor Cyan
$missing = @()
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $missing += "python (3.11+)" }
if (-not (Get-Command node   -ErrorAction SilentlyContinue)) { $missing += "node (20+)" }
if (-not (Get-Command pnpm   -ErrorAction SilentlyContinue)) {
    Write-Host "    pnpm not found — enabling via corepack" -ForegroundColor Yellow
    corepack enable
    corepack prepare pnpm@latest --activate
}
if ($missing.Count -gt 0) {
    Write-Host "Missing: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Install from: https://python.org  and  https://nodejs.org" -ForegroundColor Red
    exit 1
}

Write-Host "==> Backend deps..." -ForegroundColor Cyan
Push-Location backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Pop-Location

Write-Host "==> Frontend deps..." -ForegroundColor Cyan
Push-Location frontend
pnpm install --legacy-peer-deps
Pop-Location

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> .env created — fill in GOOGLE_MAPS_API_KEY and GEMINI_API_KEY" -ForegroundColor Yellow
}

Write-Host "==> Done. Run:  make dev  (or  docker compose up --build )" -ForegroundColor Green
