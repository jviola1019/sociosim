"""Synthetic template classifier dynamics mode.

Pure-numpy one-vs-rest logistic regression over a stable hashing vectoriser.
Runtime training data is generated from SocioSim templates with category signal
tokens, so this module must not be described as a real deployable or externally
validated classifier artifact.
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
                 epochs: int = 300, l2: float = 1e-4, xp=None):
        self.categories = list(categories)
        self.dim = dim
        self.lr = lr
        self.epochs = epochs
        self.l2 = l2
        self._xp = xp
        self.W = np.zeros((dim, len(self.categories)))
        self.b = np.zeros(len(self.categories))

    def fit(self, texts, labels) -> "TrainableClassifier":
        from socio_sim import accel
        xp = self._xp if self._xp is not None else accel.array_module()
        Xn = np.array([vectorize(t, self.dim) for t in texts])
        Yn = np.array([[1.0 if c in lab else 0.0 for c in self.categories]
                       for lab in labels])
        X, Y = xp.asarray(Xn), xp.asarray(Yn)
        W, b = xp.asarray(self.W), xp.asarray(self.b)
        n = max(len(Xn), 1)
        for _ in range(self.epochs):
            P = 1.0 / (1.0 + xp.exp(-xp.clip(X @ W + b, -30, 30)))
            G = P - Y
            W -= self.lr * ((X.T @ G) / n + self.l2 * W)
            b -= self.lr * G.mean(axis=0)
        self.W, self.b = accel.to_numpy(W), accel.to_numpy(b)
        return self

    def predict_scores(self, text: str) -> dict:
        z = vectorize(text, self.dim) @ self.W + self.b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        return {c: float(p[i]) for i, c in enumerate(self.categories)}


def build_training_data(generator, personas, n: int):
    """Generate labelled synthetic template items for runtime fitting."""
    texts, labels = [], []
    for i in range(n):
        item = generator.generate(i % personas.n, personas, tick=i % 24)
        texts.append(item.text)
        labels.append(set(item.true_categories))
    return texts, labels


def evaluate(clf: TrainableClassifier, texts, labels, threshold: float = 0.5) -> dict:
    """Per-category precision/recall on held-out synthetic template data."""
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
