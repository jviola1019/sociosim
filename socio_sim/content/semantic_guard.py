"""Post-generation semantic consistency checks for LLM surface text.

This is not a full safety classifier. It is a deterministic guard that blocks
obvious contradictions between generated text and the simulator metadata.
"""

from __future__ import annotations

import re

from socio_sim.content.generate import TOPICS

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"\+?\d[\d\-\s().]{7,}\d")
_HANDLE = re.compile(r"(?<!\w)@\w+")

_CATEGORY_TERMS = {
    "fraud": {"giftcard", "wiretransfer", "claimprize", "freemoney"},
    "hate": {"slurplaceholder", "derogatoryplaceholder", "grouptarget"},
    "harassment": {"threatplaceholder", "worthless", "pathetic"},
    "adult": {"explicitplaceholder", "adultonly", "nsfwtag"},
    "self_harm": {"selfharmplaceholder", "hopeless"},
    "illegal_goods": {"contraband", "blackmarket", "unregistered"},
    "misinfo": {"miraclecure", "coverup", "theydonttellyou"},
}

_TOPIC_TERMS = {
    "local news": {"citycouncil", "zoning", "mayor", "schoolboard"},
    "sports": {"game", "league", "match", "score", "team"},
    "technology": {"algorithm", "app", "chip", "software", "startup"},
    "health": {"clinic", "doctor", "medicine", "symptom", "vaccine"},
    "politics": {"campaign", "congress", "election", "senate", "vote"},
    "entertainment": {"album", "celebrity", "movie", "show", "streaming"},
    "finance": {"crypto", "earnings", "inflation", "loan", "stock"},
    "lifestyle": {"fashion", "recipe", "routine", "travel", "wellness"},
}


def check_generated_text(text: str, item) -> list[str]:
    lower = str(text).lower()
    reasons: list[str] = []
    if _EMAIL.search(text) or _PHONE.search(text) or _HANDLE.search(text):
        reasons.append("pii_like_output")

    truth = set(getattr(item, "true_categories", set()) or set())
    for cat, terms in _CATEGORY_TERMS.items():
        if cat not in truth and any(term in lower for term in terms):
            reasons.append(f"category_contradiction:{cat}")

    topic = TOPICS[int(getattr(item, "topic", 0)) % len(TOPICS)]
    topic_terms = _TOPIC_TERMS.get(topic, set())
    other_terms = set().union(*(
        terms for other, terms in _TOPIC_TERMS.items() if other != topic
    ))
    if (any(term in lower for term in other_terms)
            and not any(term in lower for term in topic_terms)):
        reasons.append("topic_contradiction")

    stance = float(getattr(item, "stance", 0.0))
    if stance > 0.4 and any(word in lower for word in ("terrible", "awful", "hate")):
        reasons.append("stance_contradiction")
    if stance < -0.4 and any(word in lower for word in ("great", "amazing", "love")):
        reasons.append("stance_contradiction")
    return sorted(set(reasons))
