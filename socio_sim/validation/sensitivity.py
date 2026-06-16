"""Global sensitivity analysis (Spec §1, §3.9).

First-order variance-based indices via the correlation-ratio (binned
conditional-mean) estimator over an LHS/random design — a documented
Sobol-style approximation: S_j ≈ Var(E[y | x_j]) / Var(y).
"""

from __future__ import annotations

import numpy as np


def first_order_indices(X: np.ndarray, y: np.ndarray, names: list,
                        n_bins: int = 20) -> dict:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    var_y = float(np.var(y))
    if var_y == 0:
        return {name: 0.0 for name in names}
    indices = {}
    for j, name in enumerate(names):
        order = np.argsort(X[:, j])
        y_sorted = y[order]
        bins = np.array_split(y_sorted, n_bins)
        bin_means = np.array([b.mean() for b in bins if len(b)])
        bin_weights = np.array([len(b) for b in bins if len(b)], dtype=float)
        grand = float(np.average(bin_means, weights=bin_weights))
        var_cond = float(np.average((bin_means - grand) ** 2,
                                    weights=bin_weights))
        indices[name] = max(var_cond / var_y, 0.0)
    return indices
