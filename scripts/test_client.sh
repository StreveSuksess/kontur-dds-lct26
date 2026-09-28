#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p runtime/client-tests
frontend/node_modules/.bin/tsc frontend/src/eventQueue.ts --target es2022 --module commonjs --outDir runtime/client-tests --skipLibCheck
echo '{"type":"commonjs"}' > runtime/client-tests/package.json
node --test tests/event_queue.test.cjs tests/event_queue_races.test.cjs
