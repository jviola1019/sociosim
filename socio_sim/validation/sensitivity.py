"""Global sensitivity analysis (Spec §1, §3.9).

First-order variance-based indices via the correlation-ratio (binned
conditional-mean) estimator over an LHS/random design — a documented
Sobol-style approximation: S_j ≈ Var(E[y | x_j]) / Var(y).
"""

from __future__ import annotations

import numpy as np


def first_order_indices(X: np.ndarray, y: np.ndarray, names: list,
                        n_bins: int = 20) -> dict:
    """First-order sensitivity via the correlation-ratio (binned
    conditional-mean) estimator, S_j ~= Var(E[y|x_j]) / Var(y).

    Two corrections over the naive form:
    - keep >= ~10 samples per bin (the naive `len(y)//2` cap allows 2/bin,
      where the between-bin variance saturates and a NULL parameter reads
      ~0.5);
    - subtract the within-bin sampling-variance inflation: the observed
      between-bin variance overestimates the true Var(E[y|x]) by
      mean_b( var_within_b / n_b ) (an ANOVA/omega-squared-style debiasing),
      so a non-influential parameter estimates ~0 rather than a positive
      floor.

    For a rigorous index prefer `saltelli_indices`; this remains the fast
    single-output screen.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    n_bins = max(2, min(n_bins, max(2, len(y) // 10)))
    var_y = float(np.var(y))
    if var_y == 0:
        return {name: 0.0 for name in names}
    indices = {}
    for j, name in enumerate(names):
        order = np.argsort(X[:, j])
        bins = [b for b in np.array_split(y[order], n_bins) if len(b)]
        bin_means = np.array([b.mean() for b in bins])
        bin_sizes = np.array([len(b) for b in bins], dtype=float)
        grand = float(np.average(bin_means, weights=bin_sizes))
        var_between = float(np.average((bin_means - grand) ** 2,
                                       weights=bin_sizes))
        # Inflation of the between-bin variance by within-bin sampling noise.
        within = np.array([float(np.var(b)) / len(b) if len(b) > 1 else 0.0
                           for b in bins])
        bias = float(np.average(within, weights=bin_sizes))
        indices[name] = max((var_between - bias) / var_y, 0.0)
    return indices


def saltelli_indices(f_a, f_b, f_ab: dict, names: list) -> dict:
    """Gold-standard variance-based sensitivity (Saltelli et al. 2010): both
    first-order S1 and TOTAL-effect ST, from the A/B/AB_i design.

    S1_i = mean(f_B * (f_AB_i - f_A)) / Var(Y)        (Saltelli 2010)
    ST_i = 0.5 * mean((f_A - f_AB_i)^2) / Var(Y)      (Jansen 1999)

    ST captures interactions (ST_i >= S1_i); ST_i ~ 0 means parameter i is
    non-influential and can be fixed.
    """
    f_a = np.asarray(f_a, dtype=float)
    f_b = np.asarray(f_b, dtype=float)
    var_y = float(np.var(np.concatenate([f_a, f_b])))
    s1, st = {}, {}
    for name in names:
        fab = np.asarray(f_ab[name], dtype=float)
        if var_y > 0:
            s1[name] = max(0.0, float(np.mean(f_b * (fab - f_a))) / var_y)
            st[name] = max(0.0, float(0.5 * np.mean((f_a - fab) ** 2)) / var_y)
        else:
            s1[name] = st[name] = 0.0
    return {"S1": s1, "ST": st, "var_y": var_y}
