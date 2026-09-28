#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_PORT="${PORT:-8000}"
APP_HOST="${HOST:-127.0.0.1}"

if [[ "${1:-}" != "--offline" ]]; then
  command -v uv >/dev/null || { echo 'Установите uv: https://docs.astral.sh/uv/getting-started/installation/'; exit 1; }
  command -v npm >/dev/null || { echo 'Нужен Node.js 22 и npm.'; exit 1; }
  uv sync --project "$PROJECT_ROOT/backend" --frozen
  npm --prefix "$PROJECT_ROOT/frontend" ci --no-fund
  npm --prefix "$PROJECT_ROOT/frontend" run build
elif [[ ! -f "$PROJECT_ROOT/frontend/dist/index.html" || ! -x "$PROJECT_ROOT/backend/.venv/bin/python" ]]; then
  echo 'Для офлайн-запуска сначала подготовьте зависимости и сборку обычным scripts/start.sh.'
  exit 1
fi

export ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-http://localhost:$APP_PORT,http://127.0.0.1:$APP_PORT}"
echo "Контур ДДС: http://$APP_HOST:$APP_PORT"
echo 'Демонстрационные аккаунты включены только при DEMO_MODE=true. Остановить: Ctrl+C.'
cd "$PROJECT_ROOT/backend"
exec .venv/bin/python -m uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT"
