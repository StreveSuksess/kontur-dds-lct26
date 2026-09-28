#!/bin/sh
# Reproducible developer setup for this verified macOS arm64 host. No global install.
set -eu
cd "$(dirname "$0")/../.."
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
  echo 'This setup packages Darwin arm64 only. See docs/local-ai.md for portable deployment limits.' >&2
  exit 2
fi
mkdir -p runtime/local-ai models/local-ai
ARCHIVE=runtime/local-ai/ollama-darwin.tgz
if [ ! -f "$ARCHIVE" ]; then
  curl --fail --location --retry 2 https://github.com/ollama/ollama/releases/download/v0.34.2/ollama-darwin.tgz -o "$ARCHIVE"
fi
printf '%s  %s\n' f33b2a5aa59bc6c961ed3ec23ba9dc646ca6d99ced8d2a0d46eb3a522167dd3f "$ARCHIVE" | shasum -a 256 -c -
if [ ! -x runtime/local-ai/llama-server ]; then tar -xzf "$ARCHIVE" -C runtime/local-ai; fi
PYTHON=${LOCAL_AI_PYTHON:-runtime/local-ai/venv/bin/python}
if [ ! -x "$PYTHON" ]; then uv venv --python 3.13 runtime/local-ai/venv; fi
uv pip install --system-certs --python "$PYTHON" 'openai-whisper==20250625' 'torch==2.14.0' 'av==18.1.0' 'truststore==0.10.4' 'kagglehub==1.0.2' 'transformers==4.57.6' 'sentencepiece==0.2.2' 'safetensors==0.8.0' 'protobuf==4.25.9'
KAGGLEHUB_CACHE="$PWD/models/local-ai/kaggle" "$PYTHON" scripts/local_ai/download_models.py
if [ ! -d runtime/local-ai/llama.cpp-source/.git ]; then
  git clone --no-checkout https://github.com/ggml-org/llama.cpp.git runtime/local-ai/llama.cpp-source
  git -C runtime/local-ai/llama.cpp-source checkout 2b1847030cef76ef315eaee0b7ae0cdcd4fb15ff
fi
if [ "$(git -C runtime/local-ai/llama.cpp-source rev-parse HEAD)" != 2b1847030cef76ef315eaee0b7ae0cdcd4fb15ff ]; then
  echo 'Converter source is not the validated commit; keep or restore the pinned checkout explicitly.' >&2
  exit 2
fi
if [ ! -f models/local-ai/qwen3-1.7b-f16.gguf ]; then
  "$PYTHON" runtime/local-ai/llama.cpp-source/convert_hf_to_gguf.py models/local-ai/kaggle/models/qwen-lm/qwen-3/transformers/1.7b/1 --outfile models/local-ai/qwen3-1.7b-f16.gguf --outtype f16
fi
if [ ! -f models/local-ai/qwen3-1.7b-q4_k_m.gguf ]; then
  runtime/local-ai/llama-quantize models/local-ai/qwen3-1.7b-f16.gguf models/local-ai/qwen3-1.7b-q4_k_m.gguf Q4_K_M 4
fi
echo 'Ready. Start scripts/local_ai/start.sh and LOCAL_AI_PYTHON=runtime/local-ai/venv/bin/python WHISPER_MODEL_PATH=models/local-ai/whisper-small.pt scripts/local_ai/start_speech.sh'
