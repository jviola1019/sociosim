"""Component benchmark diagnostics for the classifier algorithm.

These metrics apply only to the benchmark artifact produced here. They do not
validate the runtime synthetic template classifier or any SocioSim run output.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

from socio_sim.content.ml_classifier import TrainableClassifier

PROVENANCE = "component_benchmark"
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "benchmarks" / "moderation"

BENCHMARKS = {
    "civil_comments": {"task": "toxicity", "license": "CC0-1.0",
                       "source": "Google/Jigsaw Civil Comments"},
    "spam_detection": {"task": "spam", "license": "Apache-2.0",
                       "source": "Deysi/spam-detection-dataset"},
}

_TOKEN = re.compile(r"[a-z0-9]+")


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


def normalize_text(text: str) -> str:
    return " ".join(_TOKEN.findall(str(text).lower()))


def source_hash(name: str) -> str:
    h = hashlib.sha256()
    with (DATA_DIR / f"{name}.jsonl.gz").open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def split_benchmark(texts, labels, seed: int = 0, train_frac: float = 0.8) -> dict:
    del labels
    groups = {}
    for i, text in enumerate(texts):
        groups.setdefault(normalize_text(text), []).append(i)
    keyed = []
    for key in sorted(groups):
        digest = hashlib.blake2s(f"{seed}|{key}".encode(), digest_size=8).digest()
        keyed.append((int.from_bytes(digest, "big"), key))
    keyed.sort()
    cut = int(len(keyed) * train_frac)
    train_keys = {key for _, key in keyed[:cut]}
    train, test = [], []
    for key in sorted(groups):
        (train if key in train_keys else test).extend(groups[key])
    train_norm = {normalize_text(texts[i]) for i in train}
    test_norm = {normalize_text(texts[i]) for i in test}
    leakage = sorted(train_norm & test_norm)
    return {
        "train": np.array(sorted(train), dtype=int),
        "test": np.array(sorted(test), dtype=int),
        "split_provenance": "deterministic_normalized_text_group_split",
        "n_duplicate_families": int(sum(len(v) > 1 for v in groups.values())),
        "leakage_pass": not leakage,
        "leakage_examples": leakage[:5],
    }


def roc_auc(y_true, scores) -> float:
    y = np.asarray(y_true)
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata(np.asarray(scores, dtype=float))
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def brier_score(y_true, p) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    return float(np.mean((p - y) ** 2))


def log_loss(y_true, p) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def expected_calibration_error(y_true, p, n_bins: int = 10) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(p, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        m = (p >= edges[i]) & (p < edges[i + 1]) if i < n_bins - 1 else (
            (p >= edges[i]) & (p <= edges[i + 1]))
        if m.any():
            ece += abs(y[m].mean() - p[m].mean()) * (m.mean())
    return float(ece)


def calibration_slope(y_true, p, max_iter: int = 50, tol: float = 1e-8) -> float:
    """Cox / Van Calster calibration slope: the coefficient b1 in the
    logistic regression logit P(Y=1) = b0 + b1 * logit(p_hat).

    A perfectly calibrated model has b1 = 1; b1 < 1 => over-confident
    (predictions too extreme), b1 > 1 => under-confident. This is NOT an OLS
    slope of y on logit(p) (that has no "= 1 iff calibrated" meaning and a
    different scale); it is fit here by Newton-Raphson on the two-parameter
    logistic likelihood. Ref: Cox 1958; Van Calster et al. 2019, J Clin
    Epidemiol 74:167-176.
    """
    y = np.asarray(y_true, dtype=float)
    x = np.log(np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
               / (1 - np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)))
    if y.size == 0 or float(np.var(x)) == 0 or len(np.unique(y)) < 2:
        return float("nan")
    X = np.column_stack([np.ones_like(x), x])          # intercept + logit(p)
    beta = np.zeros(2)
    for _ in range(max_iter):
        eta = np.clip(X @ beta, -30, 30)      # avoid exp overflow at the tails
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(mu * (1 - mu), 1e-9, None)
        grad = X.T @ (y - mu)
        hess = (X * w[:, None]).T @ X
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            return float("nan")
        beta = beta + step
        if np.max(np.abs(step)) < tol:
            break
    return float(beta[1])


def _binary_metrics(y_true, scores, threshold: float) -> dict:
    yte = np.asarray(y_true, dtype=int)
    scores = np.asarray(scores, dtype=float)
    pred = scores >= threshold
    tp = int((pred & (yte == 1)).sum())
    fp = int((pred & (yte == 0)).sum())
    fn = int((~pred & (yte == 1)).sum())
    prec = tp / (tp + fp) if (tp + fp) else float("nan")
    rec = tp / (tp + fn) if (tp + fn) else float("nan")
    f1 = (2 * prec * rec / (prec + rec)
          if np.isfinite(prec) and np.isfinite(rec) and (prec + rec) > 0 else float("nan"))
    return {
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "auc": roc_auc(yte, scores),
        "brier": brier_score(yte, scores),
        "log_loss": log_loss(yte, scores),
        "ece": expected_calibration_error(yte, scores),
        "calibration_slope": calibration_slope(yte, scores),
    }


def bootstrap_intervals(y_true, scores, threshold: float, seed: int = 0,
                        n_boot: int = 200) -> dict:
    rng = np.random.default_rng(seed)
    y = np.asarray(y_true)
    s = np.asarray(scores)
    rows = {k: [] for k in (
        "f1", "auc", "brier", "log_loss", "precision", "recall",
        "calibration_slope", "ece")}
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        m = _binary_metrics(y[idx], s[idx], threshold)
        for key in rows:
            if math.isfinite(float(m[key])):
                rows[key].append(float(m[key]))
    return {
        key: {
            "lo": float(np.percentile(vals, 2.5)) if vals else float("nan"),
            "hi": float(np.percentile(vals, 97.5)) if vals else float("nan"),
            "n_boot": len(vals),
        }
        for key, vals in rows.items()
    }


def reliability_diagram(y_true, scores, n_bins: int = 10) -> list[dict]:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(scores, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    rows = []
    for i in range(n_bins):
        mask = (p >= edges[i]) & (p < edges[i + 1]) if i < n_bins - 1 else (
            (p >= edges[i]) & (p <= edges[i + 1]))
        rows.append({
            "bin_lo": float(edges[i]),
            "bin_hi": float(edges[i + 1]),
            "n": int(mask.sum()),
            "mean_score": float(p[mask].mean()) if mask.any() else float("nan"),
            "empirical_rate": float(y[mask].mean()) if mask.any() else float("nan"),
        })
    return rows


def threshold_sweep(y_true, scores) -> list[dict]:
    out = []
    for threshold in np.linspace(0.1, 0.9, 9):
        m = _binary_metrics(y_true, scores, float(threshold))
        out.append({"threshold": float(threshold), "precision": m["precision"],
                    "recall": m["recall"], "f1": m["f1"]})
    return out


def evaluate_benchmark(name: str, seed: int = 0, train_frac: float = 0.8,
                       threshold: float = 0.5, epochs: int = 300) -> dict:
    texts, labels = load_benchmark(name)
    split = split_benchmark(texts, labels, seed=seed, train_frac=train_frac)
    tr, te = split["train"], split["test"]
    ytr = [labels[i] for i in tr]
    clf = TrainableClassifier(["positive"], epochs=epochs).fit(
        [texts[i] for i in tr], [{"positive"} if y else set() for y in ytr])
    yte = np.array([labels[i] for i in te])
    scores = np.array([clf.predict_scores(texts[i])["positive"] for i in te])
    metrics = _binary_metrics(yte, scores, threshold)
    brier = metrics["brier"]
    prior = float(np.mean(ytr))
    base_p = np.full(len(yte), prior)
    brier_base = brier_score(yte, base_p)
    ll_base = log_loss(yte, base_p)
    model_hash = hashlib.sha256(
        clf.W.tobytes() + clf.b.tobytes()
        + json.dumps({"dim": clf.dim, "epochs": clf.epochs, "l2": clf.l2},
                     sort_keys=True).encode()).hexdigest()
    return {
        "name": name,
        "provenance": PROVENANCE,
        "evidence_id": "ev.component_benchmark.bundled_classifier",
        **BENCHMARKS[name],
        "source_sha256": source_hash(name),
        "split_provenance": split["split_provenance"],
        "n_duplicate_families": split["n_duplicate_families"],
        "leakage_pass": split["leakage_pass"],
        "leakage_examples": split["leakage_examples"],
        "n_train": len(tr),
        "n_test": len(te),
        **metrics,
        "brier_baseline": brier_base,
        "log_loss_baseline": ll_base,
        "brier_skill_score": float(1 - brier / brier_base) if brier_base else float("nan"),
        "threshold": threshold,
        "positive_rate": float(yte.mean()),
        "baseline_majority_acc": float(max(yte.mean(), 1 - yte.mean())),
        "model_hash": model_hash,
        "bootstrap_ci": bootstrap_intervals(yte, scores, threshold, seed=seed),
        "reliability_diagram": reliability_diagram(yte, scores),
        "threshold_sweep": threshold_sweep(yte, scores),
    }


def evaluate_all(seed: int = 0) -> list:
    return [evaluate_benchmark(n, seed=seed) for n in available_benchmarks()]


def render_benchmark_report(results: list) -> str:
    lines = [
        "# SocioSim Classifier Component Benchmark Diagnostics",
        "",
        "> Scope: component benchmark only. These results do not validate the "
        "runtime synthetic template classifier or any simulation output.",
        "",
        "| benchmark | task | license | leakage | n_test | F1 | ROC-AUC | Brier | log-loss | ECE |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['task']} | {r['license']} | "
            f"{'pass' if r['leakage_pass'] else 'FAIL'} | {r['n_test']} | "
            f"{r['f1']:.3f} | {r['auc']:.3f} | {r['brier']:.3f} | "
            f"{r['log_loss']:.3f} | {r['ece']:.3f} |")
    lines += [
        "",
        "## Artifact Metadata",
    ]
    for r in results:
        lines.append(
            f"- {r['name']}: source_sha256 `{r['source_sha256']}`, "
            f"model_hash `{r['model_hash']}`, split `{r['split_provenance']}`, "
            f"duplicate families {r['n_duplicate_families']}")
    lines += [
        "",
        "## Limitations",
        "- Benchmark metrics are regenerated from bundled data and attached hashes.",
        "- They are valid only for this component evaluation protocol.",
        "- They do not make SocioSim outputs operationally valid.",
    ]
    return "\n".join(lines)
