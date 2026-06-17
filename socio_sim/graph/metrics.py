"""Network statistics used as calibration targets (Spec §3.2, §3.9)."""

from __future__ import annotations

import networkx as nx
import numpy as np

from socio_sim.validation.targets import hill_exponent


def summary(g: nx.Graph) -> dict:
    degrees = np.array([d for _, d in g.degree()], dtype=float)
    try:
        assortativity = float(nx.degree_assortativity_coefficient(g))
    except (ValueError, ZeroDivisionError):
        assortativity = float("nan")
    # Degree histogram (<=24 bins) for dashboards; small + JSON-friendly.
    dmax = int(degrees.max()) if len(degrees) else 0
    nbins = min(24, max(dmax, 1))
    counts, edges = np.histogram(degrees, bins=nbins)
    degree_hist = [[float((edges[i] + edges[i + 1]) / 2), int(counts[i])]
                   for i in range(len(counts))]
    return {
        "n": g.number_of_nodes(),
        "m": g.number_of_edges(),
        "clustering": float(nx.average_clustering(g)),
        "degree_mean": float(degrees.mean()),
        "degree_median": float(np.median(degrees)),
        "degree_max": float(degrees.max()),
        "assortativity": assortativity,
        "degree_tail_exponent": (float(hill_exponent(degrees))
                                 if len(degrees) >= 20 else float("nan")),
        "degree_hist": degree_hist,
    }


def sample_subgraph(g: nx.Graph, groups: dict | None = None,
                    max_nodes: int = 150, max_edges: int = 500) -> dict:
    """A small, deterministic subgraph for visualization: the top-degree nodes
    (hubs) plus the edges among them, capped. Each node carries its degree and
    a group label (e.g. ideology bucket) for colouring. JSON-friendly.
    """
    deg = dict(g.degree())
    nodes = sorted(deg, key=lambda n: (-deg[n], n))[:max_nodes]
    nodeset = set(nodes)
    edges = []
    for u, v in g.edges():
        if u in nodeset and v in nodeset:
            edges.append([int(u), int(v)])
            if len(edges) >= max_edges:
                break
    node_objs = [{"id": int(n), "deg": int(deg[n]),
                  "group": (groups.get(n, "?") if groups else "?")}
                 for n in nodes]
    return {"nodes": node_objs, "edges": edges}


def homophily_index(g: nx.Graph, attributes: dict) -> float:
    """Observed same-attribute edge fraction minus the expectation under
    random mixing (Newman-style). Positive = homophilous."""
    if g.number_of_edges() == 0:
        return 0.0
    same = sum(1 for u, v in g.edges if attributes[u] == attributes[v])
    observed = same / g.number_of_edges()
    values, counts = np.unique(list(attributes.values()), return_counts=True)
    fractions = counts / counts.sum()
    expected = float((fractions**2).sum())
    return observed - expected
