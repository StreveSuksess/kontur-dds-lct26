#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
exec runtime/local-ai/llama-server \
  -m "${LOCAL_LLM_MODEL_PATH:-models/local-ai/qwen3-1.7b-q4_k_m.gguf}" \
  --host 127.0.0.1 --port "${LOCAL_LLM_PORT:-11434}" \
  --alias qwen3-1.7b --ctx-size 4096 --parallel 1 --threads 4 \
  --n-gpu-layers 0 --jinja --chat-template-kwargs '{"enable_thinking":false}'
