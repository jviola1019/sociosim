"""Property-based invariants (hypothesis) for the core numerics/determinism."""

from hypothesis import given, settings
from hypothesis import strategies as st

from socio_sim.rng import SeedTree
from socio_sim.stats import (benjamini_hochberg, newcombe_diff_ci,
                             two_proportion_p, wilson_interval)

# Property tests assert invariants, not latency; disable per-example deadlines
# (first example pays scipy's lazy import, which is environment-sensitive).
settings.register_profile("nodeadline", deadline=None)
settings.load_profile("nodeadline")


@given(n=st.integers(min_value=1, max_value=2000),
       k=st.integers(min_value=0, max_value=2000))
def test_wilson_always_in_unit_and_ordered(n, k):
    lo, hi = wilson_interval(min(k, n), n)
    assert 0.0 <= lo <= hi <= 1.0


@given(n1=st.integers(1, 1000), k1=st.integers(0, 1000),
       n2=st.integers(1, 1000), k2=st.integers(0, 1000))
def test_newcombe_interval_is_ordered(n1, k1, n2, k2):
    lo, hi = newcombe_diff_ci(min(k1, n1), n1, min(k2, n2), n2)
    assert lo <= hi


@given(n1=st.integers(1, 1000), k1=st.integers(0, 1000),
       n2=st.integers(1, 1000), k2=st.integers(0, 1000))
def test_two_proportion_p_in_unit(n1, k1, n2, k2):
    p = two_proportion_p(min(k1, n1), n1, min(k2, n2), n2)
    assert 0.0 <= p <= 1.0


@given(ps=st.lists(st.floats(min_value=0, max_value=1), max_size=25))
def test_bh_returns_aligned_boolean_mask(ps):
    rejected = benjamini_hochberg(ps)
    assert len(rejected) == len(ps)
    assert all(isinstance(x, bool) for x in rejected)


@given(root=st.integers(0, 10**6), rep=st.integers(0, 64))
def test_seedtree_is_deterministic_per_module_replicate(root, rep):
    a = SeedTree(root).generator("mod", rep).random(6)
    b = SeedTree(root).generator("mod", rep).random(6)
    assert (a == b).all()
