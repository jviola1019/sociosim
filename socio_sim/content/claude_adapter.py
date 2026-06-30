"""Optional Claude text generation with a replay cache (Spec §3.4).

Structure (topic, stance, categories, labels) always comes from the seeded
TemplateGenerator — the LLM only replaces surface text. Responses are cached
to JSON keyed by prompt hash, so a completed run replays bit-identically
without network access. Any failure degrades to template text and reports it
(`degradation` event at the engine level) — never a silent fallback.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Callable

from socio_sim.content.generate import TOPICS, TemplateGenerator
from socio_sim.content.items import ContentItem
from socio_sim.content.semantic_guard import check_generated_text, semantic_hash

MODEL = "claude-haiku-4-5-20251001"  # cheapest adequate model for persona posts

_PROMPT_TEMPLATE = (
    "Write one short social media post (max 40 words) about {topic} with a "
    "{tone} tone. Persona: {age} year-old, ideology {ideo:+.1f} on a -1..1 "
    "scale. Simulation day {day}. Output only the post text."
)
_CN_LABEL_PREFIX = "[AI-generated content] "


class ClaudeAdapter:
    def __init__(self, base: TemplateGenerator, cache_path: str | Path,
                 api_key: str | None = None, model: str | None = None,
                 on_degradation: Callable[[str], None] = lambda reason: None):
        self.base = base
        self.cache_path = Path(cache_path)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.MODEL = model or MODEL
        self.on_degradation = on_degradation
        self._cache: dict = {}
        if self.cache_path.exists():
            self._cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
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
        if not self.cache_path.exists():
            return None
        return hashlib.sha256(self.cache_path.read_bytes()).hexdigest()

    def generate(self, author_id: int, personas, tick: int) -> ContentItem:
        item = self.base.generate(author_id, personas, tick)
        key = self.prompt_key(author_id, personas, tick, item.topic, item.stance)
        if key in self._cache:
            cached = self._cache[key]
            text = cached.get("text") if isinstance(cached, dict) else cached
            item.text = (_CN_LABEL_PREFIX if item.explicit_label else "") + text
            return item
        if self._client is None:
            self.on_degradation("no API key or anthropic package; template text used")
            return item
        try:
            prompt = self._prompt(author_id, personas, item.topic, tick, item.stance)
            resp = self._client.messages.create(
                model=self.MODEL, max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            reasons = check_generated_text(text, item)
            if reasons:
                self._cache[key] = {
                    "text": text,
                    "semantic_hash": semantic_hash(text),
                    "status": "blocked",
                    "reason_codes": reasons,
                }
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.cache_path.write_text(
                    json.dumps(self._cache, sort_keys=True), encoding="utf-8")
                self.on_degradation(
                    f"semantic_mismatch:{','.join(reasons)}; template text used")
                return item
            self._cache[key] = {
                "text": text,
                "semantic_hash": semantic_hash(text),
                "status": "accepted",
                "reason_codes": [],
            }
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(self._cache, sort_keys=True), encoding="utf-8")
            item.text = (_CN_LABEL_PREFIX if item.explicit_label else "") + text
            return item
        except Exception as exc:  # degrade loudly, keep the run going
            self.on_degradation(f"LLM call failed: {exc!r}; template text used")
            return item
