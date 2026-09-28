#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p runtime/presentation-v2-build deliverables
PRESENTATION_RUNTIME_DIR="${PRESENTATION_RUNTIME_DIR:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies}"
export PRESENTATION_RUNTIME_DIR
RUNTIME_NODE_MODULES="${RUNTIME_NODE_MODULES:-$PRESENTATION_RUNTIME_DIR/node/node_modules}"
export RUNTIME_NODE_MODULES
if [ ! -e runtime/presentation-v2-build/node_modules ]; then
  ln -s "$RUNTIME_NODE_MODULES" runtime/presentation-v2-build/node_modules
fi
cp scripts/presentation-v2.mjs runtime/presentation-v2-build/build.mjs
exec "$PRESENTATION_RUNTIME_DIR/node/bin/node" runtime/presentation-v2-build/build.mjs
