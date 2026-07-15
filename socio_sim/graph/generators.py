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
    if kind == "cm":
        # Configuration model with a target power-law degree exponent, plus
        # degree-preserving triangle-forming swaps to inject clustering.
        # Unlike preferential attachment (BA/PLC, whose exponent asymptotes
        # to 3), this reproduces a specified tail exponent -- real social
        # graphs sit near 2.3 (Barabasi & Albert 1999). Fully deterministic
        # from the run's seed tree.
        return _configuration_graph(
            n, gamma=float(params.get("gamma", 2.3)),
            min_degree=int(params.get("min_degree", 2)),
            triangle_swaps=float(params.get("triangle_swaps", 8.0)),
            rng=rng)
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


def _configuration_graph(n: int, gamma: float, min_degree: int,
                         triangle_swaps: float,
                         rng: np.random.Generator) -> nx.Graph:
    """Simple graph with a power-law(gamma) degree sequence + triangle swaps.

    All randomness derives from `rng` (deterministic). The degree sequence
    is drawn from `nx.utils.powerlaw_sequence`, floored at `min_degree` and
    parity-corrected; the configuration model is collapsed to a simple
    graph. Then `triangle_swaps * |E|` degree-preserving double-edge swaps
    that CREATE a triangle are attempted, lifting clustering without
    changing any node's degree (so the tail exponent is preserved).
    """
    seed = int(rng.integers(0, 2**31 - 1))
    seq = nx.utils.powerlaw_sequence(n, gamma, seed=seed)
    deg = [max(min_degree, int(round(d))) for d in seq]
    if sum(deg) % 2:                       # configuration model needs even sum
        deg[int(rng.integers(0, n))] += 1
    g = nx.Graph(nx.configuration_model(deg, seed=seed))   # collapse multi-edges
    g.remove_edges_from(nx.selfloop_edges(g))

    n_swaps = int(triangle_swaps * g.number_of_edges())
    if n_swaps:
        swap_rng = np.random.default_rng(seed ^ 0x5DEECE66D)
        edges = list(g.edges())
        for _ in range(n_swaps):
            (a, b) = edges[int(swap_rng.integers(0, len(edges)))]
            (c, d) = edges[int(swap_rng.integers(0, len(edges)))]
            if len({a, b, c, d}) < 4 or g.has_edge(a, c) or g.has_edge(b, d):
                continue
            # rewire (a,b),(c,d) -> (a,c),(b,d) only if it closes a triangle
            if (set(g[a]) & set(g[c])) or (set(g[b]) & set(g[d])):
                g.remove_edge(a, b)
                g.remove_edge(c, d)
                g.add_edge(a, c)
                g.add_edge(b, d)
                edges = list(g.edges())
    return g


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
