"""Optional Claude text generation with a replay cache (Spec §3.4).

Structure (topic, stance, categories, labels) always comes from the seeded
TemplateGenerator — the LLM only replaces surface text. Responses are cached
to JSON keyed by prompt hash, so a completed run replays bit-identically
without network access. Any failure degrades to template text and reports it
(`degradation` event at the engine level) — never a silent fallback.
"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Callable

from socio_sim.content import llm_cache
from socio_sim.content.generate import (CN_LABEL_PREFIX, TOPICS,
                                        TemplateGenerator)
from socio_sim.content.items import ContentItem
from socio_sim.content.semantic_guard import check_generated_text

MODEL = "claude-haiku-4-5-20251001"  # cheapest adequate model for persona posts

_PROMPT_TEMPLATE = (
    "Write one short social media post (max 40 words) about {topic} with a "
    "{tone} tone. Persona: {age} year-old, ideology {ideo:+.1f} on a -1..1 "
    "scale. Simulation day {day}. Output only the post text."
)
#: Single source: socio_sim.content.generate.CN_LABEL_PREFIX.
_CN_LABEL_PREFIX = CN_LABEL_PREFIX


class ClaudeAdapter:
    def __init__(self, base: TemplateGenerator, cache_path: str | Path,
                 api_key: str | None = None, model: str | None = None,
                 on_degradation: Callable[[str], None] = lambda reason: None):
        self.base = base
        self.cache_path = Path(cache_path)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.MODEL = model or MODEL
        self.on_degradation = on_degradation
        self._cache: dict = llm_cache.load(self.cache_path, on_error=self.on_degradation)
        # Usage accounting: diagnostics only, surfaced via RunResult.llm_usage;
        # never enters the hashed event stream (latency is wall-clock).
        self.usage = {"calls": 0, "cache_hits": 0, "blocked": 0,
                      "failures": 0, "latency_s": 0.0,
                      "prompt_chars": 0, "response_chars": 0,
                      "prompt_eval_tokens": 0, "response_eval_tokens": 0}
        self._client = None
        if self.api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                self._client = None

    def prompt_key(self, author_id: int, personas, tick: int, topic: int = 0,
                   stance: float = 0.0) -> str:
        prompt = self._prompt(author_id, personas, topic, tick, stance)
        return hashlib.sha256(f"claude|{self.MODEL}|{prompt}".encode()).hexdigest()

    def _prompt(self, author_id: int, personas, topic: int, tick: int,
                stance: float) -> str:
        tone = "optimistic" if stance > 0.25 else ("skeptical" if stance < -0.25 else "measured")
        return _PROMPT_TEMPLATE.format(
            topic=TOPICS[topic % len(TOPICS)],
            tone=tone,
            age=personas.age_group[author_id],
            ideo=float(personas.ideology[author_id, 0]),
            day=tick // 24,
        )

    def cache_hash(self) -> str | None:
        return llm_cache.file_hash(self.cache_path)

    def _apply_text(self, item: ContentItem, text: str) -> None:
        item.text = (_CN_LABEL_PREFIX + text) if item.explicit_label else text

    def generate(self, author_id: int, personas, tick: int) -> ContentItem:
        item = self.base.generate(author_id, personas, tick)
        key = self.prompt_key(author_id, personas, tick, item.topic, item.stance)
        lookup = llm_cache.resolve(self._cache.get(key))

        if lookup.degradation:
            self.on_degradation(lookup.degradation)
        if lookup.hit:
            self.usage["cache_hits"] += 1
            if lookup.text is not None:
                self._apply_text(item, lookup.text)
            return item  # blocked or tamper-free accepted hit; never re-call

        if self._client is None:
            self.on_degradation("no API key or anthropic package; template text used")
            return item
        try:
            prompt = self._prompt(author_id, personas, item.topic, tick, item.stance)
            started = time.perf_counter()
            resp = self._client.messages.create(
                model=self.MODEL, max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
            )
            self.usage["calls"] += 1
            self.usage["latency_s"] += time.perf_counter() - started
            self.usage["prompt_chars"] += len(prompt)
            api_usage = getattr(resp, "usage", None)
            if api_usage is not None:
                self.usage["prompt_eval_tokens"] += int(
                    getattr(api_usage, "input_tokens", 0) or 0)
                self.usage["response_eval_tokens"] += int(
                    getattr(api_usage, "output_tokens", 0) or 0)
            text = (resp.content[0].text or "").strip()
            if not text:
                raise ValueError("empty LLM response")
            text = " ".join(text.split())[:280]
            self.usage["response_chars"] += len(text)
            reasons = check_generated_text(text, item)
            if reasons:
                self.usage["blocked"] += 1
                self._cache[key] = llm_cache.make_entry(
                    text, "blocked", reasons,
                    guard_version=llm_cache.BLOCKED_GUARD_VERSION)
                llm_cache.save(self.cache_path, self._cache)
                self.on_degradation(
                    f"semantic_mismatch:{','.join(reasons)}; template text used")
                return item
            self._cache[key] = llm_cache.make_entry(text, "accepted", [])
            llm_cache.save(self.cache_path, self._cache)
            self._apply_text(item, text)
            return item
        except Exception as exc:  # degrade loudly, keep the run going
            self.usage["failures"] += 1
            self.on_degradation(f"LLM call failed: {exc!r}; template text used")
            return item
