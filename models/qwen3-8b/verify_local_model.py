"""Import the transferred GGUF into local Ollama and run a smoke inference."""

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


MODEL_DIR = Path(__file__).resolve().parent
MODEL_FILE = MODEL_DIR / "Qwen3-8B-Q4_K_M.gguf"
MODEL_NAME = "qwen3-8b-q4km-local"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


def main() -> int:
    if not MODEL_FILE.is_file():
        print(f"Model file not found: {MODEL_FILE}", file=sys.stderr)
        return 1

    ollama = shutil.which("ollama")
    if not ollama:
        print("Ollama CLI was not found on PATH.", file=sys.stderr)
        return 1

    print(f"Importing {MODEL_FILE.name} into local Ollama as {MODEL_NAME}...")
    created = subprocess.run(
        [ollama, "create", MODEL_NAME, "-f", str(MODEL_DIR / "Modelfile")],
        cwd=MODEL_DIR,
        check=False,
    )
    if created.returncode:
        print("Ollama could not import the local GGUF. Is its service running?", file=sys.stderr)
        return created.returncode

    payload = json.dumps(
        {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": "Reply with a short greeting and identify yourself as Qwen3-8B.",
                }
            ],
            "stream": False,
            "think": False,
            "options": {"num_predict": 64, "temperature": 0},
        }
    ).encode("utf-8")
    request = Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=900) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (URLError, TimeoutError, ValueError) as error:
        print(f"Local Ollama inference request failed: {error}", file=sys.stderr)
        return 1
    wall_seconds = time.perf_counter() - started

    answer = result.get("message", {}).get("content", "").strip()
    if not answer:
        print("Ollama returned no generated text; inference verification failed.", file=sys.stderr)
        return 1

    print("\nGenerated response:")
    print(answer.encode(sys.stdout.encoding or "utf-8", errors="backslashreplace").decode(sys.stdout.encoding or "utf-8"))
    print(f"\nInference request wall time: {wall_seconds:.2f} seconds")
    token_count = result.get("eval_count")
    eval_ns = result.get("eval_duration")
    if isinstance(token_count, int) and isinstance(eval_ns, int) and eval_ns > 0:
        print(f"Generation: {token_count} tokens in {eval_ns / 1e9:.2f} seconds ({token_count * 1e9 / eval_ns:.2f} tokens/s)")
    print("Local model generated text successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
