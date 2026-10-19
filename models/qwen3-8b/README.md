# Local Qwen3-8B model (offline transfer)

This directory is for a locally transferred GGUF model. Model weights are ignored by Git.

## Transfer this file

- Repository: [`Qwen/Qwen3-8B-GGUF`](https://huggingface.co/Qwen/Qwen3-8B-GGUF)
- File: `Qwen3-8B-Q4_K_M.gguf`
- Format/quantization: GGUF, Q4_K_M (4-bit)
- Approximate size: 5.03 GB

Transfer that one file into this directory, keeping the exact filename:

```text
models/qwen3-8b/Qwen3-8B-Q4_K_M.gguf
```

The existing Windows Ollama installation is the runtime. It imports the local GGUF through `Modelfile`; inference runs on the CPU when no GPU is available. Nothing in this setup downloads the model or changes the HR Copilot application.

## Import and verify after transfer

From the repository root, with the Ollama service running:

```powershell
python models/qwen3-8b/verify_local_model.py
```

The script checks for the transferred file, imports it into Ollama, sends a short generation request to `127.0.0.1`, and reports elapsed time and generated tokens per second when Ollama returns those measurements. It fails if the file or local service is unavailable, or if inference returns no text.
