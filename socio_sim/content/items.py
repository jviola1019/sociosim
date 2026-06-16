"""ContentItem schema (Spec §3.4).

`true_categories` is simulation ground truth (assigned at generation); the
NoisyClassifier produces the platform's *belief* about it. Moderation state
lives on the item (`status`, `applied_labels`).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContentItem:
    id: str
    author_id: int
    tick: int
    media_type: str            # text | image | video (media simulated as metadata)
    topic: int
    stance: float              # [-1, 1]
    text: str
    true_categories: set = field(default_factory=set)
    ai_generated: bool = False
    explicit_label: bool = False           # CN: conspicuous AI-content notice
    implicit_watermark: dict | None = None  # CN: {provider, content_ref}
    disclosure_present: bool = False        # FTC: material-connection disclosure
    sponsored: bool = False
    campaign_id: str | None = None

    # Moderation state
    status: str = "visible"     # visible | downranked | removed
    applied_labels: list = field(default_factory=list)
    platform_label_added: bool = False  # CN: platform-added notice on unlabeled synthetic media

    # Engagement counters (for affinity/cascade analytics)
    shares: int = 0
    likes: int = 0
    parent_id: str | None = None  # for shares/reshares (cascade trees)
