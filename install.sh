#!/usr/bin/env bash
# Solar Unified — macOS / Linux one-shot installer
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Checking prerequisites..."
missing=()
command -v python3 >/dev/null || missing+=("python3 (3.11+)")
command -v node    >/dev/null || missing+=("node (20+)")
if ! command -v pnpm >/dev/null; then
    echo "    pnpm not found — enabling via corepack"
    corepack enable >/dev/null 2>&1 || true
    corepack prepare pnpm@latest --activate >/dev/null 2>&1 || true
fi
if [ "${#missing[@]}" -gt 0 ]; then
    echo "Missing: ${missing[*]}"
    echo "Install from: https://python.org and https://nodejs.org"
    exit 1
fi

echo "==> Backend deps..."
(
    cd backend
    python3 -m pip install --upgrade pip
    python3 -m pip install -r requirements.txt
)

echo "==> Frontend deps..."
(
    cd frontend
    pnpm install --strict-peer-dependencies=false
)

if [ ! -f .env ]; then
    cp .env.example .env
    echo "==> .env created — fill in GOOGLE_MAPS_API_KEY and GEMINI_API_KEY"
fi

echo "==> Done. Run:  make dev  (or  docker compose up --build )"
