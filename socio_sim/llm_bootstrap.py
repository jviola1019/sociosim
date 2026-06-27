"""Shared free-LLM (Ollama) bootstrap helpers.

Used by both the CLI launcher (run.py) and the web backend so the local LLM
content mode works without a separate setup step: locate the binary, start the
server if needed, pull the model if missing — no API key, no account.
"""

from __future__ import annotations

import os
import shutil
import subprocess  # nosec B404
import time
import urllib.request
from pathlib import Path

DEFAULT_HOST = "127.0.0.1:11434"


def find_ollama() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path("/usr/local/bin/ollama"),
        Path("/opt/homebrew/bin/ollama"),
        Path(os.environ.get("HOME", "")) / ".ollama" / "bin" / "ollama",
    ]
    for c in candidates:
        if c and c.exists():
            return str(c)
    return None


def server_up(host: str = DEFAULT_HOST, timeout: float = 2.0) -> bool:
    try:
        # B310 suppressed: localhost-only Ollama health check; host defaults to 127.0.0.1:11434.
        urllib.request.urlopen(f"http://{host}/api/version", timeout=timeout).read()  # nosec B310
        return True
    except Exception:
        return False


def ensure_server(host: str = DEFAULT_HOST, log=print):
    """Start `ollama serve` if not already reachable. Returns the Popen we
    started (or None if it was already up / could not be started)."""
    if server_up(host):
        return None
    ollama = find_ollama()
    if not ollama:
        raise RuntimeError(
            "Ollama is not installed. Install it (one time):\n"
            "  winget install Ollama.Ollama   (Windows)\n"
            "  brew install ollama            (macOS)\n"
            "  curl -fsSL https://ollama.com/install.sh | sh   (Linux)")
    log(f"starting Ollama server at {host}")
    env = dict(os.environ, OLLAMA_HOST=host)
    # B603 suppressed: list args, no shell=True, binary path resolved by find_ollama() via shutil.which.
    proc = subprocess.Popen([ollama, "serve"], env=env,  # nosec B603
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        if server_up(host):
            return proc
        time.sleep(1)
    raise RuntimeError("Ollama server did not become ready within 30s")


def ensure_model(model: str, host: str = DEFAULT_HOST, log=print):
    ollama = find_ollama()
    if not ollama:
        raise RuntimeError("Ollama binary not found")
    env = dict(os.environ, OLLAMA_HOST=host)
    have = subprocess.run([ollama, "list"], env=env, capture_output=True, text=True)  # nosec B603
    if model in have.stdout:
        return
    log(f"pulling model {model} (first time only)")
    r = subprocess.run([ollama, "pull", model], env=env)  # nosec B603
    if r.returncode != 0:
        raise RuntimeError(f"failed to pull model {model}")
