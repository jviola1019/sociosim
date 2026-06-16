"""Noisy classifier: turns ground truth into platform belief (Spec §3.4).

Per category, false-negative and false-positive rates are derived from the
configured (precision, recall) operating point and the category's prevalence:

    recall r  -> P(flag | true) = r
    precision p, prevalence π -> fpr = r·π·(1-p) / (p·(1-π))

Scores are continuous: flagged items score in [0.5, 1), unflagged in [0, 0.5),
so rule packs can apply stricter evidence thresholds on top of the flag.
"""

from __future__ import annotations

import numpy as np


class NoisyClassifier:
    def __init__(self, targets: dict, base_rates: dict, rng: np.random.Generator):
        self.rng = rng
        self.params = {}
        for cat, t in targets.items():
            prevalence = base_rates.get(cat, 0.01)
            r, p = t["recall"], t["precision"]
            fpr = (r * prevalence * (1 - p)) / max(p * (1 - prevalence), 1e-9)
            self.params[cat] = {"recall": r, "fpr": min(fpr, 1.0)}

    def classify_one(self, true_categories: set) -> dict:
        """Return per-category scores in [0, 1] for one item."""
        scores = {}
        for cat, prm in self.params.items():
            is_true = cat in true_categories
            p_flag = prm["recall"] if is_true else prm["fpr"]
            flagged = self.rng.random() < p_flag
            if flagged:
                scores[cat] = float(0.5 + 0.5 * self.rng.random())
            else:
                scores[cat] = float(0.5 * self.rng.random())
        return scores


def confusion(truth: np.ndarray, flags: np.ndarray) -> dict:
    truth = np.asarray(truth, dtype=bool)
    flags = np.asarray(flags, dtype=bool)
    return {
        "tp": int((truth & flags).sum()),
        "fp": int((~truth & flags).sum()),
        "fn": int((truth & ~flags).sum()),
        "tn": int((~truth & ~flags).sum()),
    }
