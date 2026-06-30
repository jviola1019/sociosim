"""Synthetic mechanism checks on documented qualitative patterns.

Does the simulator reproduce DOCUMENTED empirical regularities of real social
systems? Each fact is a named, cited, qualitative check with a pass band. This
is a synthetic mechanism check, not point-prediction of any real platform.
"""

from __future__ import annotations

from collections import Counter

import numpy as np

from socio_sim.analytics.metrics import cascade_sizes, summarize_run
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation

PROVENANCE = "synthetic_mechanism_check"


def _fact(name, observed, lo, hi, source):
    ok = bool(np.isfinite(observed)) and (lo <= observed) and (observed <= hi)
    return {"name": name, "observed": (float(observed) if np.isfinite(observed) else None),
            "lo": lo, "hi": (None if hi == float("inf") else hi),
            "passes": ok, "source": source}


def _top_share(posts, frac):
    if not posts:
        return float("nan")
    counts = sorted(Counter(e["actor_id"] for e in posts).values(), reverse=True)
    k = max(1, int(len(counts) * frac))
    return sum(counts[:k]) / sum(counts)


def _diurnal_ratio(posts, tick_hours):
    if not posts:
        return float("nan")
    hours = np.array([(e["tick"] * tick_hours) % 24 for e in posts])
    hist = np.bincount(hours, minlength=24).astype(float)
    med = float(np.median(hist))
    return float(hist.max()) / med if med > 0 else float("nan")


def stylized_facts(result, summary) -> list:
    """Compute the cited stylized facts for a finished run."""
    g = summary["graph"]
    posts = result.log.by_kind("post")
    n = g["n"]
    out = []
    # 1. Scale-free: heavy-tailed degree, power-law exponent ~2–3.
    out.append(_fact("heavy_tailed_degree", g.get("degree_tail_exponent", float("nan")),
                     2.0, 3.6,
                     "Power-law degree exponent ~2–3 in social networks "
                     "(Barabási & Albert 1999; Clauset, Shalizi & Newman 2009)"))
    # 2. Triadic closure: clustering far exceeds an equivalent random graph.
    er = g["degree_mean"] / max(n - 1, 1)
    out.append(_fact("clustering_exceeds_random", (g["clustering"] / er) if er > 0 else float("nan"),
                     3.0, float("inf"),
                     "Real networks are far more clustered than random graphs "
                     "(Watts & Strogatz 1998)"))
    # 3. Heavy-tailed cascades: most stay small, a few go viral.
    cs = cascade_sizes(result.log)
    if cs:
        med = float(np.median(cs))
        skew = float(np.max(cs)) / med if med > 0 else float("nan")
    else:
        skew = float("nan")
    out.append(_fact("cascade_right_skew", skew, 2.0, float("inf"),
                     "Most diffusion cascades die quickly; a few go viral — "
                     "heavy-tailed cascade sizes (Goel, Watts & Goldstein 2012)"))
    # 4. Participation inequality: a minority produces most content.
    out.append(_fact("participation_inequality", _top_share(posts, 0.10), 0.30, 1.0,
                     "Participation inequality — a small minority makes most posts "
                     "(Nielsen '90-9-1'; van Mierlo 2014)"))
    # 5. Circadian rhythm: a clear day/night posting cycle.
    out.append(_fact("diurnal_cycle", _diurnal_ratio(posts, result.config.tick_hours),
                     1.5, float("inf"),
                     "Diurnal/circadian posting cycle (Golder & Macy 2011)"))
    return out


def evaluate_stylized_facts(cfg: RunConfig | None = None) -> dict:
    """Run the aggregate-matched prototype (or a given cfg) and score checks."""
    cfg = cfg or RunConfig.calibrated(jurisdictions=("EU",))
    result = Simulation(cfg).run()
    facts = stylized_facts(result, summarize_run(result))
    return {"provenance": PROVENANCE, "facts": facts,
            "n_pass": int(sum(f["passes"] for f in facts)), "n_total": len(facts)}
