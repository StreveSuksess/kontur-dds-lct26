#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
PYTHON=${LOCAL_AI_PYTHON:-research/.venv-asr/bin/python}
exec "$PYTHON" scripts/local_ai/speech_server.py --model "${WHISPER_MODEL_PATH:-research/models/openai/small.pt}" --port "${SPEECH_PORT:-11435}"
