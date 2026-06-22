"""Rung 4 — MEASURED classifier performance on real, licensed public benchmarks.

Trains the project's numpy classifier on a deterministic split of a bundled,
license-clean, de-identified moderation dataset and reports REAL precision /
recall / F1 / ROC-AUC. Provenance: ``measured-on-benchmark`` — the only rung that
reports performance measured on real data rather than synthetic. Offline +
deterministic (seeded split + zero-init logistic regression). Datasets are
governed in docs/DATA_MANIFEST.md.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from socio_sim.content.ml_classifier import TrainableClassifier

PROVENANCE = "measured-on-benchmark"
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "benchmarks" / "moderation"

#: Bundled benchmarks with verified license + source (see docs/DATA_MANIFEST.md).
BENCHMARKS = {
    "civil_comments": {"task": "toxicity", "license": "CC0-1.0",
                       "source": "Google/Jigsaw Civil Comments"},
    "spam_detection": {"task": "spam", "license": "Apache-2.0",
                       "source": "Deysi/spam-detection-dataset"},
}


def available_benchmarks() -> list:
    return [n for n in BENCHMARKS if (DATA_DIR / f"{n}.jsonl.gz").is_file()]


def load_benchmark(name: str):
    texts, labels = [], []
    with gzip.open(DATA_DIR / f"{name}.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            texts.append(r["text"])
            labels.append(int(r["label"]))
    return texts, labels


def roc_auc(y_true, scores) -> float:
    """Tie-corrected ROC-AUC via the Mann–Whitney rank statistic."""
    y = np.asarray(y_true)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata(np.asarray(scores, dtype=float))
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def evaluate_benchmark(name: str, seed: int = 0, train_frac: float = 0.8,
                       threshold: float = 0.5, epochs: int = 300) -> dict:
    texts, labels = load_benchmark(name)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(texts))
    cut = int(len(texts) * train_frac)
    tr, te = idx[:cut], idx[cut:]
    clf = TrainableClassifier(["positive"], epochs=epochs).fit(
        [texts[i] for i in tr],
        [{"positive"} if labels[i] else set() for i in tr])
    yte = np.array([labels[i] for i in te])
    scores = np.array([clf.predict_scores(texts[i])["positive"] for i in te])
    pred = scores >= threshold
    tp = int((pred & (yte == 1)).sum())
    fp = int((pred & (yte == 0)).sum())
    fn = int((~pred & (yte == 1)).sum())
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * prec * rec / (prec + rec)
          if np.isfinite(prec) and np.isfinite(rec) and (prec + rec) > 0 else float("nan"))
    return {
        "name": name, "provenance": PROVENANCE, **BENCHMARKS[name],
        "n_train": len(tr), "n_test": len(te),
        "precision": prec, "recall": rec, "f1": f1, "auc": roc_auc(yte, scores),
        "threshold": threshold, "positive_rate": float(yte.mean()),
        "baseline_majority_acc": float(max(yte.mean(), 1 - yte.mean())),
    }


def evaluate_all(seed: int = 0) -> list:
    return [evaluate_benchmark(n, seed=seed) for n in available_benchmarks()]


def render_benchmark_report(results: list) -> str:
    lines = [
        "# SocioSim Measured-Classifier Benchmark Report",
        "",
        "> Provenance: **measured-on-benchmark** — the moderation classifier's "
        "precision/recall/F1/ROC-AUC measured on REAL, license-clean, de-identified "
        "public datasets (see `docs/DATA_MANIFEST.md`). Deterministic (seeded split "
        "+ zero-init logistic regression). This is the highest rung of the "
        "validation ladder: a measured component, not a synthetic estimate.",
        "",
        "| benchmark | task | license | n_train | n_test | precision | recall | F1 | ROC-AUC |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['task']} | {r['license']} | {r['n_train']} | "
            f"{r['n_test']} | {r['precision']:.3f} | {r['recall']:.3f} | "
            f"{r['f1']:.3f} | {r['auc']:.3f} |")
    lines += [
        "",
        "## Honest scope",
        "- These are REAL measured metrics on real public benchmarks — usable by "
        "businesses/governments under the datasets' licenses (CC0-1.0, Apache-2.0).",
        "- The classifier is a transparent numpy logistic-regression over hashed "
        "features (auditable, deterministic), not a black-box LLM — a deliberate "
        "trade of peak accuracy for reproducibility + explainability.",
        "- Measures the CLASSIFIER COMPONENT only; it does not make the synthetic "
        "agent-based simulation itself predictive of real platforms.",
        "- Text was PII-scrubbed (emails/URLs/phones/@handles redacted) on top of "
        "the sources' own de-identification; no decisions about real individuals.",
    ]
    return "\n".join(lines)
