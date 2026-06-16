"""Deterministic, seeded template content generation (Spec §3.4).

Default content source: free, reproducible, replayable. The ClaudeAdapter
(claude_adapter.py) wraps this generator and swaps only the surface text.
"""

from __future__ import annotations

import numpy as np

from socio_sim.config import RunConfig
from socio_sim.content.items import ContentItem

TOPICS = (
    "local news", "sports", "technology", "health", "politics",
    "entertainment", "finance", "lifestyle",
)

_TEMPLATES = (
    "Thoughts on {topic} today: {slant} take, honestly.",
    "Can't believe what's happening in {topic} right now. {slant} vibes.",
    "Hot take about {topic}: {slant} and I stand by it.",
    "Sharing this {topic} piece — {slant} perspective worth reading.",
    "My daily {topic} update: things look {slant}.",
)

_SLANTS = ("an optimistic", "a skeptical", "a critical", "an enthusiastic", "a cautious")

#: Probability a creator properly labels AI-generated content (CN compliance knob).
CN_CREATOR_LABEL_COMPLIANCE = 0.9

WATERMARK_PROVIDER = "SocioSimGen-01"


class TemplateGenerator:
    def __init__(self, cfg: RunConfig, rng: np.random.Generator):
        self.cfg = cfg
        self.rng = rng
        self._counter = 0
        self._cn_active = "CN" in cfg.jurisdictions

    def _next_id(self) -> str:
        self._counter += 1
        return f"c{self._counter}"

    def generate(self, author_id: int, personas, tick: int) -> ContentItem:
        rng = self.rng
        # Topic from the author's interest distribution
        topic = int(rng.choice(self.cfg.n_topics, p=personas.interests[author_id]))
        # Stance correlated with author ideology (axis 0), noised
        stance = float(np.clip(
            personas.ideology[author_id, 0] + rng.normal(0, 0.3), -1, 1))

        # Ground-truth categories from configured base rates; political content
        # is more likely for ideologically extreme authors.
        cats: set = set()
        for cat, rate in self.cfg.category_base_rates.items():
            if cat == "political":
                rate = rate * (1 + abs(personas.ideology[author_id, 0]))
            if cat == "ai_generated":
                continue  # handled below as a flag
            if rng.random() < rate:
                cats.add(cat)

        ai_generated = rng.random() < self.cfg.category_base_rates.get(
            "ai_generated", 0.0)
        if ai_generated:
            cats.add("ai_generated")

        media_type = str(rng.choice(["text", "image", "video"], p=[0.7, 0.2, 0.1]))
        template = _TEMPLATES[int(rng.integers(0, len(_TEMPLATES)))]
        slant = _SLANTS[int(rng.integers(0, len(_SLANTS)))]
        text = template.format(topic=TOPICS[topic % len(TOPICS)], slant=slant)

        explicit_label = False
        watermark = None
        if ai_generated:
            # CN rules: providers must add explicit labels + implicit metadata
            # watermarks. Compliance is probabilistic so the platform-detection
            # path (policy pack) gets exercised on the remainder.
            compliant = rng.random() < CN_CREATOR_LABEL_COMPLIANCE
            if self._cn_active and compliant:
                explicit_label = True
                watermark = {
                    "provider": WATERMARK_PROVIDER,
                    "content_ref": f"ref-{self._counter + 1}",
                }
                text = "[AI-generated content] " + text

        return ContentItem(
            id=self._next_id(),
            author_id=author_id,
            tick=tick,
            media_type=media_type,
            topic=topic,
            stance=stance,
            text=text,
            true_categories=cats,
            ai_generated=ai_generated,
            explicit_label=explicit_label,
            implicit_watermark=watermark,
        )
