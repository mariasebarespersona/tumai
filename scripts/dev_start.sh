#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate
export WEB_BASE="http://localhost:3000,http://localhost:3004,http://localhost:3005,http://localhost:3006"
uvicorn app:app --reload --port 7901


