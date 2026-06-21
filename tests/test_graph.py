import numpy as np

from socio_sim.graph.generators import make_graph, mix_homophily
from socio_sim.graph.metrics import (average_clustering, homophily_index,
                                     summary)
from socio_sim.rng import SeedTree


def rng():
    return SeedTree(7).generator("graph", 0)


def test_approx_clustering_matches_exact_and_is_deterministic():
    g = make_graph("ba", 600, rng(), m=4)
    exact = average_clustering(g, exact_max=10**9)
    approx = average_clustering(g, exact_max=100, trials=8000, seed=0)
    assert abs(exact - approx) < 0.02            # sampled estimate ~ exact
    again = average_clustering(g, exact_max=100, trials=8000, seed=0)
    assert approx == again                        # deterministic (fixed seed)
    # small graphs always take the exact path
    small = make_graph("ba", 80, rng(), m=3)
    import networkx as nx
    assert average_clustering(small) == float(nx.average_clustering(small))


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


def test_sample_subgraph_caps_membership_and_determinism():
    import networkx as nx

    from socio_sim.graph.metrics import sample_subgraph
    g = nx.barabasi_albert_graph(300, 4, seed=1)
    groups = {i: ("L" if i % 2 == 0 else "R") for i in g.nodes()}
    s = sample_subgraph(g, groups, max_nodes=50, max_edges=120)
    assert len(s["nodes"]) <= 50 and len(s["edges"]) <= 120
    ids = {n["id"] for n in s["nodes"]}
    for u, v in s["edges"]:
        assert u in ids and v in ids          # edges only among sampled nodes
    assert all("group" in n and "deg" in n for n in s["nodes"])
    assert sample_subgraph(g, groups, 50, 120) == s   # deterministic


def test_run_exposes_graph_sample():
    from socio_sim.config import RunConfig
    from socio_sim.engine import Simulation
    res = Simulation(RunConfig.test(jurisdictions=("EU",))).run()
    gs = res.graph_stats.get("graph_sample")
    assert gs and gs["nodes"] and gs["edges"]
