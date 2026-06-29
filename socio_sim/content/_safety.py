"""Shared safety + reclassification guards for the LLM content adapters.

Both the local (Ollama / OpenAI-compatible) and the Claude adapter replace only
the surface TEXT of a template-structured item; the category labels stay
template-decided. These guards run over the *generated surface text* so that:

  1. no PII / operational-harm / executable content is ever surfaced, and
  2. the surface text cannot assert a harm category the item was not labelled
     with — **reclassification consistency**. A safe item whose text leaks a
     harm signal, or a harm item whose text drifts into a *different* harm
     category, is rejected and the run degrades to deterministic template text.

Both adapters import these so the safety posture is identical regardless of
backend (previously the Claude path applied no guard at all).
"""

from __future__ import annotations

import re

#: CN explicit-label prefix that must survive surface-text replacement.
CN_LABEL_PREFIX = "[AI-generated content] "

_PII_PATTERNS = (
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
)
_UNSAFE_PHRASES = (
    "kill yourself",
    "build a bomb",
    "evade moderation",
    "avoid detection",
    "harass",
    "dox",
    "real person's",
)

#: Category-specific keyword signals used by reclass_violation(). If the surface
#: text fires one of these for a category the item was NOT labelled with, the
#: text is rejected.
_RECLASS_SIGNALS: dict[str, tuple[str, ...]] = {
    "hate": ("hate", "n-word", "slur", "racial", "kill all"),
    "self_harm": ("suicide", "self-harm", "cut myself", "end my life"),
    "fraud": ("phishing", "scam", "wire transfer", "send money", "bank details"),
    "harassment": ("i will find you", "you will regret", "destroy you"),
}


def safe_generated_text(text: str) -> str:
    """Normalise and guard generated surface text; raise ValueError on violation."""
    text = " ".join(text.split())[:280]
    lowered = text.lower()
    for pat in _PII_PATTERNS:
        if pat.search(text):
            raise ValueError("generated text failed PII/contact-info guard")
    if any(phrase in lowered for phrase in _UNSAFE_PHRASES):
        raise ValueError("generated text failed operational-harm guard")
    if "```" in text or "<script" in lowered:
        raise ValueError("generated text failed executable-content guard")
    return text


def reclass_violation(text: str, item) -> str | None:
    """Reclassify the surface TEXT against the item's labelled categories.

    The generated text must not assert a harm category the item was not
    labelled with: a safe item (no categories) whose text fires any harm
    signal, or a harm item whose text fires a *different* harm category, is a
    violation. Signals for an already-assigned category are allowed — the
    template intentionally chose that content type. Returns a non-empty
    violation string on failure, else None.
    """
    lowered = text.lower()
    assigned = set(getattr(item, "true_categories", None) or ())
    for category, signals in _RECLASS_SIGNALS.items():
        if category in assigned:
            continue  # the text may legitimately express an assigned harm category
        for signal in signals:
            if signal in lowered:
                return (f"surface text asserts unlabelled {category!r} "
                        f"category (signal {signal!r})")
    return None
