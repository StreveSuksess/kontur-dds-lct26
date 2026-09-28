#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p runtime/presentation-build deliverables
PRESENTATION_RUNTIME_DIR="${PRESENTATION_RUNTIME_DIR:-$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies}"
export PRESENTATION_RUNTIME_DIR
export RUNTIME_NODE_MODULES="${RUNTIME_NODE_MODULES:-$PRESENTATION_RUNTIME_DIR/node/node_modules}"
if [ ! -e runtime/presentation-build/node_modules ]; then
  ln -s "$RUNTIME_NODE_MODULES" runtime/presentation-build/node_modules
fi
cp scripts/presentation.mjs runtime/presentation-build/build.mjs
exec "$PRESENTATION_RUNTIME_DIR/node/bin/node" runtime/presentation-build/build.mjs "$@"
