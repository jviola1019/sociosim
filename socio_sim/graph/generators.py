"""Social graph generators (Spec §3.2): BA, PLC (Holme–Kim), WS, SBM + homophily mixing.

All generators take an explicit numpy Generator so graphs are reproducible
from the run's seed tree.
"""

from __future__ import annotations

import networkx as nx
import numpy as np


def make_graph(kind: str, n: int, rng: np.random.Generator, **params) -> nx.Graph:
    seed = int(rng.integers(0, 2**31 - 1))
    if kind == "ba":
        return nx.barabasi_albert_graph(n, params.get("m", 5), seed=seed)
    if kind == "plc":
        # Holme-Kim: BA-style power-law degree PLUS tunable clustering via the
        # triad-formation probability p (tuning knob for clustering).
        return nx.powerlaw_cluster_graph(
            n, params.get("m", 5), params.get("p", 0.3), seed=seed)
    if kind == "ws":
        return nx.watts_strogatz_graph(
            n, params.get("k", 10), params.get("p", 0.05), seed=seed
        )
    if kind == "sbm":
        sizes = params["block_sizes"]
        p_matrix = params["p_matrix"]
        g = nx.stochastic_block_model(sizes, p_matrix, seed=seed)
        # SBM returns a graph with `block` already on nodes via partition data;
        # normalize to a plain attribute.
        for node, data in g.nodes(data=True):
            data["block"] = int(data.get("block", 0))
        return nx.Graph(g)  # strip SBM metadata wrapper
    raise ValueError(f"unknown graph kind: {kind}")


def mix_homophily(g: nx.Graph, attributes: dict, rewire_fraction: float,
                  rng: np.random.Generator) -> nx.Graph:
    """Rewire a fraction of cross-attribute edges to same-attribute pairs.

    Preserves edge count. Models homophily on top of any base topology.
    """
    g = g.copy()
    nodes_by_attr: dict = {}
    for node, attr in attributes.items():
        nodes_by_attr.setdefault(attr, []).append(node)

    cross_edges = [(u, v) for u, v in g.edges if attributes[u] != attributes[v]]
    rng.shuffle(cross_edges)
    n_rewire = int(len(cross_edges) * rewire_fraction)

    for u, v in cross_edges[:n_rewire]:
        candidates = nodes_by_attr[attributes[u]]
        for _ in range(10):  # bounded retry to keep simple graph invariants
            w = candidates[int(rng.integers(0, len(candidates)))]
            if w != u and not g.has_edge(u, w):
                g.remove_edge(u, v)
                g.add_edge(u, w)
                break
    return g
