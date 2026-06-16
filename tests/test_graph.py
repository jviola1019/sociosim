import numpy as np

from socio_sim.graph.generators import make_graph, mix_homophily
from socio_sim.graph.metrics import homophily_index, summary
from socio_sim.rng import SeedTree


def rng():
    return SeedTree(7).generator("graph", 0)


def test_ba_heavy_tail():
    g = make_graph("ba", 1000, rng(), m=5)
    degrees = np.array([d for _, d in g.degree()])
    assert degrees.max() > 5 * np.median(degrees)


def test_ws_clustering_above_random():
    g_ws = make_graph("ws", 1000, rng(), k=10, p=0.05)
    s = summary(g_ws)
    # ER baseline clustering ~ k/n = 0.01; WS with low rewiring should be far above
    assert s["clustering"] > 0.2


def test_sbm_block_density():
    g = make_graph(
        "sbm", 300, rng(),
        block_sizes=[150, 150],
        p_matrix=[[0.08, 0.005], [0.005, 0.08]],
    )
    blocks = {n: g.nodes[n]["block"] for n in g.nodes}
    within = sum(1 for u, v in g.edges if blocks[u] == blocks[v])
    across = g.number_of_edges() - within
    assert within > 3 * across


def test_homophily_mixing_raises_index():
    g = make_graph("ba", 500, rng(), m=4)
    gen = rng()
    attrs = {n: int(gen.integers(0, 2)) for n in g.nodes}
    before = homophily_index(g, attrs)
    g2 = mix_homophily(g, attrs, rewire_fraction=0.5, rng=rng())
    after = homophily_index(g2, attrs)
    assert after > before
    assert g2.number_of_edges() == g.number_of_edges()


def test_seed_determinism():
    g1 = make_graph("ba", 200, SeedTree(7).generator("graph", 0), m=3)
    g2 = make_graph("ba", 200, SeedTree(7).generator("graph", 0), m=3)
    assert sorted(g1.edges) == sorted(g2.edges)


def test_summary_keys():
    g = make_graph("ws", 200, rng(), k=6, p=0.1)
    s = summary(g)
    for key in ("n", "m", "clustering", "degree_mean", "degree_max", "assortativity"):
        assert key in s
