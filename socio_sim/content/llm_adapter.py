"""Free, keyless LLM content adapters (Spec §3.4).

Backends (no API key, no account):
- "ollama": local Ollama server, default http://localhost:11434
- "openai_compatible": any OpenAI-compatible local server (LM Studio,
  llamafile, vLLM, llama.cpp server); Authorization header optional

Same guarantees as the Claude adapter: structure (topic, stance, categories,
labels) always comes from the seeded TemplateGenerator — the LLM only replaces
surface text. Responses are cached by prompt hash so completed runs replay
bit-identically offline. Failures degrade loudly to template text via
on_degradation — never silently.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import socket
import ssl
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from socio_sim.content import llm_cache
from socio_sim.security import validate_llm_url
from socio_sim.content.generate import (CN_LABEL_PREFIX, TOPICS,
                                        TemplateGenerator)
from socio_sim.content.items import ContentItem
from socio_sim.content.semantic_guard import check_generated_text

DEFAULT_MODELS = {
    "ollama": "qwen2.5:0.5b",          # ~400MB pull; adequate for short posts
    "openai_compatible": "local-model",
}
DEFAULT_URLS = {
    "ollama": "http://localhost:11434",
    "openai_compatible": "http://localhost:1234/v1",  # LM Studio default
}

_PROMPT_TEMPLATE = (
    "Write one short social media post (max 40 words) about {topic}. "
    "Persona: {age} year-old, ideology {ideo:+.1f} on a -1..1 scale "
    "(negative=left, positive=right). Day {day} of the simulation. "
    "Output only the post text, no quotes."
)

#: CN explicit-label prefix that must survive text replacement.
#: Single source: socio_sim.content.generate.CN_LABEL_PREFIX.
_CN_LABEL_PREFIX = CN_LABEL_PREFIX


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """TCP-connects to a pre-validated IP while keeping the original
    hostname for the Host header (E-05): between validate_llm_url() and the
    connect there is no second DNS lookup left to rebind."""

    def __init__(self, host, port, pinned_ip, timeout):
        super().__init__(host, port, timeout=timeout)
        self._pinned_ip = pinned_ip

    def connect(self):
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS variant of _PinnedHTTPConnection: dials the pinned IP but
    keeps TLS SNI + certificate hostname verification on the ORIGINAL
    hostname, so pinning does not weaken certificate checks."""

    def __init__(self, host, port, pinned_ip, timeout):
        super().__init__(host, port, timeout=timeout,
                         context=ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self):
        sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class LLMAdapter:
    def __init__(self, base: TemplateGenerator, cache_path: str | Path,
                 backend: str = "ollama", model: str = "",
                 base_url: str = "", api_key: str | None = None,
                 on_degradation: Callable[[str], None] = lambda reason: None,
                 transport: Callable[[str], str] | None = None,
                 timeout: int = 120):
        if backend not in DEFAULT_URLS:
            raise ValueError(f"unknown LLM backend: {backend}")
        self.base = base
        self.backend = backend
        self.model = model or DEFAULT_MODELS[backend]
        self.base_url = (base_url or DEFAULT_URLS[backend]).rstrip("/")
        self.api_key = api_key
        self.on_degradation = on_degradation
        self.timeout = timeout
        self.transport = transport or self._http_transport
        self.cache_path = Path(cache_path)
        self._cache: dict = llm_cache.load(self.cache_path, on_error=self.on_degradation)
        # After this many consecutive transport failures we stop calling out and
        # degrade instantly — avoids minutes of per-call connect timeouts when a
        # local server is down. Reset on any success.
        self._fail_streak = 0
        self._give_up_after = 3
        self._disabled = False
        # Usage accounting (deferred P5 item). Diagnostics ONLY: lives on
        # the adapter, surfaced via RunResult.llm_usage, and never enters
        # the hashed event stream (latency is wall-clock).
        self.usage = {"calls": 0, "cache_hits": 0, "blocked": 0,
                      "failures": 0, "latency_s": 0.0,
                      "prompt_chars": 0, "response_chars": 0,
                      "prompt_eval_tokens": 0, "response_eval_tokens": 0}
        self._last_token_counts: tuple | None = None

    # -- prompt & cache ----------------------------------------------------
    def _prompt(self, author_id: int, personas, topic: int, tick: int) -> str:
        return _PROMPT_TEMPLATE.format(
            topic=TOPICS[topic % len(TOPICS)],
            age=personas.age_group[author_id],
            ideo=float(personas.ideology[author_id, 0]),
            day=tick // 24,
        )

    def prompt_key(self, prompt: str) -> str:
        return hashlib.sha256(f"{self.model}|{prompt}".encode()).hexdigest()

    def cache_hash(self) -> str | None:
        return llm_cache.file_hash(self.cache_path)

    def _apply_text(self, item: ContentItem, text: str) -> None:
        # Preserve the CN explicit label when replacing surface text.
        item.text = (_CN_LABEL_PREFIX + text) if item.explicit_label else text

    # -- generation ----------------------------------------------------------
    def generate(self, author_id: int, personas, tick: int) -> ContentItem:
        item = self.base.generate(author_id, personas, tick)
        prompt = self._prompt(author_id, personas, item.topic, tick)
        key = self.prompt_key(prompt)
        lookup = llm_cache.resolve(self._cache.get(key))

        if lookup.degradation:
            self.on_degradation(lookup.degradation)
        if lookup.hit:
            self.usage["cache_hits"] += 1
            if lookup.text is not None:
                self._apply_text(item, lookup.text)
            return item  # blocked or tamper-free accepted hit; never re-call

        if self._disabled:
            self.on_degradation(
                f"{self.backend} disabled after repeated failures; "
                f"template text used")
            return item
        try:
            self._last_token_counts = None
            started = time.perf_counter()
            text = (self.transport(prompt) or "").strip()
            self.usage["calls"] += 1
            self.usage["latency_s"] += time.perf_counter() - started
            self.usage["prompt_chars"] += len(prompt)
            self.usage["response_chars"] += len(text)
            if self._last_token_counts is not None:
                self.usage["prompt_eval_tokens"] += self._last_token_counts[0]
                self.usage["response_eval_tokens"] += self._last_token_counts[1]
            if not text:
                raise ValueError("empty LLM response")
            text = " ".join(text.split())[:280]
            reasons = check_generated_text(text, item)
            if reasons:
                self.usage["blocked"] += 1
                # Concurrency-safe upsert; first writer wins per key.
                self._cache = llm_cache.update(
                    self.cache_path, key,
                    llm_cache.make_entry(
                        text, "blocked", reasons,
                        guard_version=llm_cache.BLOCKED_GUARD_VERSION),
                    on_error=self.on_degradation)
                # E-04: the transport call SUCCEEDED (only the content was
                # rejected) -- reset the consecutive-failure streak so a
                # live backend isn't disabled by interleaved guard blocks.
                self._fail_streak = 0
                self.on_degradation(
                    f"semantic_mismatch:{','.join(reasons)}; template text used")
                # Adopt the winner here too (see _adopt): if a concurrent
                # writer's ACCEPTED entry won this key, serving template
                # text while the cache holds accepted text would make the
                # next same-seed run diverge -- a determinism break. The
                # semantic_mismatch degradation was just reported, so
                # _adopt must not report a second one for the same call.
                return self._adopt(item, key, announced=True)
            self._cache = llm_cache.update(
                self.cache_path, key,
                llm_cache.make_entry(text, "accepted", []),
                on_error=self.on_degradation)
            self._fail_streak = 0
        except Exception as exc:
            self._fail_streak += 1
            self.usage["failures"] += 1
            self.on_degradation(
                f"{self.backend} call failed: {exc!r}; template text used")
            if self._fail_streak >= self._give_up_after:
                self._disabled = True
                self.on_degradation(
                    f"{self.backend} unreachable after {self._fail_streak} "
                    f"attempts; using template text for the rest of this run")
            return item
        return self._adopt(item, key)

    def _adopt(self, item: ContentItem, key: str,
               announced: bool = False) -> ContentItem:
        """Apply whatever entry actually WON this key.

        Under first-writer-wins another process may have screened the same
        prompt first. Whatever is on disk is what the next run with this
        config+seed will replay, so this run must serve exactly that -- or
        the two runs' event streams diverge (determinism invariant). A
        blocked winner yields text=None, so blocked text is still never
        served as content.

        `announced` suppresses a duplicate degradation when the caller has
        already reported one for this same generate() call.
        """
        final = llm_cache.resolve(self._cache.get(key))
        if final.hit and final.text is not None:
            self._apply_text(item, final.text)
        elif final.degradation and not announced:
            self.on_degradation(final.degradation)
        return item

    # -- transports ----------------------------------------------------------
    def _http_transport(self, prompt: str) -> str:
        """POST the prompt to the configured local LLM server.

        SSRF hardening (E-02 + E-05): the allow-list check runs on every
        call and returns the exact IP it checked; the TCP connection is
        made to THAT pinned IP (original hostname kept for the Host header
        and TLS SNI/certificate verification), so no second DNS lookup
        exists to rebind. Redirects are never followed: any 3xx response
        is a hard error.
        """
        if self.backend == "ollama":
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 60, "temperature": 0.8, "seed": 0},
            }
            url = f"{self.base_url}/api/generate"
            headers = {"Content-Type": "application/json"}
        else:  # openai_compatible
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 80,
                "temperature": 0.8,
            }
            url = f"{self.base_url}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

        pinned_ip = validate_llm_url(self.base_url)
        if pinned_ip is None:  # unreachable: base_url always has a default
            raise ValueError("llm_base_url is empty")
        p = urlparse(url)
        port = p.port or (443 if p.scheme == "https" else 80)
        path = p.path + (f"?{p.query}" if p.query else "")
        conn_cls = (_PinnedHTTPSConnection if p.scheme == "https"
                    else _PinnedHTTPConnection)
        conn = conn_cls(p.hostname, port, pinned_ip, self.timeout)
        try:
            conn.request("POST", path, body=json.dumps(payload).encode(),
                         headers=headers)
            resp = conn.getresponse()
            if 300 <= resp.status < 400:
                raise ValueError(
                    f"redirect (HTTP {resp.status}) refused by SSRF guard")
            if resp.status != 200:
                raise ValueError(f"LLM server returned HTTP {resp.status}")
            body = json.loads(resp.read().decode("utf-8"))
        finally:
            conn.close()
        if self.backend == "ollama":
            if "prompt_eval_count" in body or "eval_count" in body:
                self._last_token_counts = (int(body.get("prompt_eval_count", 0)),
                                           int(body.get("eval_count", 0)))
            return body["response"]
        usage = body.get("usage") or {}
        if usage:
            self._last_token_counts = (int(usage.get("prompt_tokens", 0)),
                                       int(usage.get("completion_tokens", 0)))
        return body["choices"][0]["message"]["content"]
