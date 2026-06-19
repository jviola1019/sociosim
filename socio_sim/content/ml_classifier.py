"""A REAL, trainable moderation classifier (Spec §3.4 "interface for plugging
real models in") — replaces the noise model in `classifier_mode="trained"`.

Pure-numpy one-vs-rest logistic regression over a stable hashing vectoriser (no
new dependency, no GPU). Fully deterministic (zero init, fixed data order, fixed
epochs, blake2s feature hashing — not Python's salted hash), so trained runs
replay bit-identically. Performance is MEASURED (held-out precision/recall),
never assumed.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

_TOKEN = re.compile(r"[a-z0-9]+")


def _bucket(token: str, dim: int) -> int:
    h = hashlib.blake2s(token.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(h, "big") % dim


def vectorize(text: str, dim: int) -> np.ndarray:
    v = np.zeros(dim, dtype=float)
    for tok in _TOKEN.findall(text.lower()):
        v[_bucket(tok, dim)] += 1.0
    return v


class TrainableClassifier:
    """One-vs-rest logistic regression; outputs per-category scores in [0, 1]."""

    def __init__(self, categories, dim: int = 1024, lr: float = 0.5,
                 epochs: int = 300, l2: float = 1e-4):
        self.categories = list(categories)
        self.dim = dim
        self.lr = lr
        self.epochs = epochs
        self.l2 = l2
        self.W = np.zeros((dim, len(self.categories)))
        self.b = np.zeros(len(self.categories))

    def fit(self, texts, labels) -> "TrainableClassifier":
        X = np.array([vectorize(t, self.dim) for t in texts])
        Y = np.array([[1.0 if c in lab else 0.0 for c in self.categories]
                      for lab in labels])
        n = max(len(X), 1)
        for _ in range(self.epochs):
            P = 1.0 / (1.0 + np.exp(-np.clip(X @ self.W + self.b, -30, 30)))
            G = P - Y
            self.W -= self.lr * ((X.T @ G) / n + self.l2 * self.W)
            self.b -= self.lr * G.mean(axis=0)
        return self

    def predict_scores(self, text: str) -> dict:
        z = vectorize(text, self.dim) @ self.W + self.b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        return {c: float(p[i]) for i, c in enumerate(self.categories)}


def build_training_data(generator, personas, n: int):
    """Generate n labelled items (text, true_categories) from the content
    generator (which must have inject_signal=True) for training/evaluation."""
    texts, labels = [], []
    for i in range(n):
        item = generator.generate(i % personas.n, personas, tick=i % 24)
        texts.append(item.text)
        labels.append(set(item.true_categories))
    return texts, labels


def evaluate(clf: TrainableClassifier, texts, labels, threshold: float = 0.5) -> dict:
    """Per-category precision/recall on held-out data (measured, not assumed)."""
    out = {}
    for c in clf.categories:
        tp = fp = fn = 0
        for t, lab in zip(texts, labels):
            pred = clf.predict_scores(t)[c] >= threshold
            truth = c in lab
            tp += pred and truth
            fp += pred and not truth
            fn += (not pred) and truth
        out[c] = {
            "precision": tp / (tp + fp) if (tp + fp) else float("nan"),
            "recall": tp / (tp + fn) if (tp + fn) else float("nan"),
            "support": tp + fn,
        }
    return out
