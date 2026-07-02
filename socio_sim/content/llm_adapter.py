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
import json
import urllib.request
from pathlib import Path
from typing import Callable

from socio_sim.content import llm_cache
from socio_sim.content.generate import TOPICS, TemplateGenerator
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
_CN_LABEL_PREFIX = "[AI-generated content] "


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

    def _save_cache(self):
        llm_cache.save(self.cache_path, self._cache)

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
            if lookup.text is not None:
                self._apply_text(item, lookup.text)
            return item  # blocked or tamper-free accepted hit; never re-call

        if self._disabled:
            self.on_degradation(
                f"{self.backend} disabled after repeated failures; "
                f"template text used")
            return item
        try:
            text = (self.transport(prompt) or "").strip()
            if not text:
                raise ValueError("empty LLM response")
            text = " ".join(text.split())[:280]
            reasons = check_generated_text(text, item)
            if reasons:
                self._cache[key] = llm_cache.make_entry(
                    text, "blocked", reasons,
                    guard_version=llm_cache.BLOCKED_GUARD_VERSION)
                self._save_cache()
                self.on_degradation(
                    f"semantic_mismatch:{','.join(reasons)}; template text used")
                return item
            self._cache[key] = llm_cache.make_entry(text, "accepted", [])
            self._save_cache()
            self._fail_streak = 0
        except Exception as exc:
            self._fail_streak += 1
            self.on_degradation(
                f"{self.backend} call failed: {exc!r}; template text used")
            if self._fail_streak >= self._give_up_after:
                self._disabled = True
                self.on_degradation(
                    f"{self.backend} unreachable after {self._fail_streak} "
                    f"attempts; using template text for the rest of this run")
            return item
        self._apply_text(item, text)
        return item

    # -- transports ----------------------------------------------------------
    def _http_transport(self, prompt: str) -> str:
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

        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # nosec B310
            body = json.loads(resp.read().decode("utf-8"))
        if self.backend == "ollama":
            return body["response"]
        return body["choices"][0]["message"]["content"]
