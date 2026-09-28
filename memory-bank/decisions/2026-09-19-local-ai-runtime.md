# Workspace-only local AI runtime

## Context

The customer requires local execution; Q&A accepts outgoing-call prepared greetings and pre-generated classroom scenarios. The development host is macOS arm64 with 48 GB RAM; target classroom specifications differ. Several model hosts are blocked in this network, while official QwenLM Kaggle distribution is accessible. Ollama serve creates a key under the user's home directory, conflicting with workspace-only installation scope.

## Decision

Use the official Ollama standalone archive's bundled llama-server directly, with Qwen3 1.7B Q4_K_M converted from official QwenLM weights. Bind loopback11434, CPU4threads, one slot. Run local original Whisper-small through a separate loopback11435 HTTP service. Prepare four outgoing responses with installed Milena voice. Treat LLM generation as teacher-reviewed drafting; retain deterministic evidence checks and teacher control of grades. Parent explicitly approved this runtime selection.

## Alternatives

- Ollama serve: rejected here because it writes outside workspace.
- Hugging Face/Ollama registry/ModelScope download: unavailable in this network; no access bypass.
- Remote inference: incompatible with customer runtime requirement.
- Real-time fully dynamic dialogue: unnecessary for the current outgoing-report MVP and unverified on target hardware.
- LLM as automatic grader: local smoke checks exposed semantic errors despite valid JSON.

## Consequences

A real offline neural speech and text stack works on the development host. Runtime/model binaries stay ignored; source scripts and factual validation reports are versioned. The Darwin package is not a verified Linux/x86 delivery artifact. Classroom concurrency, real microphone accuracy, actual SIP transport and teacher scoring methodology still require separate validation. Prepared TTS uses only the available female Russian voice; no claim of male voice support or SIP test is made.
