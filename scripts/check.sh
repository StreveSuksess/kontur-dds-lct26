#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
backend/.venv/bin/python -m unittest discover -s tests -v
uv run --frozen --directory backend pytest -q
npm --prefix frontend run build
bash scripts/test_client.sh
