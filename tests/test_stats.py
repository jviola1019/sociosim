"""Proportion-statistics helpers: Newcombe, BH-FDR, two-proportion p-value."""

import numpy as np

from socio_sim.stats import (benjamini_hochberg, newcombe_diff_ci,
                             two_proportion_p)


def test_benjamini_hochberg_controls_discoveries():
    # one clearly-significant, one borderline, two null
    rejected = benjamini_hochberg([0.001, 0.04, 0.5, 0.9], alpha=0.05)
    assert rejected[0] is True
    assert rejected[2] is False and rejected[3] is False
    # all-null stays null
    assert benjamini_hochberg([0.6, 0.7, 0.8], alpha=0.05) == [False, False, False]


def test_two_proportion_p_extremes():
    assert two_proportion_p(50, 100, 50, 100) > 0.5      # identical -> not sig
    assert two_proportion_p(90, 100, 10, 100) < 0.01     # very different -> sig
    assert np.isnan(two_proportion_p(0, 0, 1, 10))       # empty arm -> nan


def test_min_detectable_effect_shrinks_with_n():
    from socio_sim.stats import min_detectable_effect
    small_n = min_detectable_effect(50, 50, 0.1)
    big_n = min_detectable_effect(5000, 5000, 0.1)
    assert small_n > big_n > 0
    assert np.isnan(min_detectable_effect(0, 10, 0.1))


def test_discrete_ks_zero_when_matching():
    from socio_sim.stats import discrete_ks
    assert discrete_ks([1, 1, 1, 1], [2, 2, 2, 2]) == 0.0     # same shape
    assert discrete_ks([10, 0, 0], [0, 0, 10]) > 0.5          # very different
    assert np.isnan(discrete_ks([0, 0], [1, 1]))


def test_newcombe_brackets_difference():
    lo, hi = newcombe_diff_ci(60, 100, 40, 100)
    assert lo < 0.2 < hi                                  # true diff 0.2 inside
    assert all(np.isnan(x) for x in newcombe_diff_ci(1, 0, 1, 10))


# --- closed-form / analytical property tests (catch formula regressions) ---

def test_wilson_interval_closed_form():
    """Wilson 95% score interval for 50/100 is the textbook (0.4038, 0.5962)."""
    from socio_sim.stats import wilson_interval
    lo, hi = wilson_interval(50, 100, z=1.96)
    assert abs(lo - 0.40383) < 1e-4, lo
    assert abs(hi - 0.59617) < 1e-4, hi
    # Symmetric about 0.5 for a symmetric count.
    assert abs((lo + hi) / 2 - 0.5) < 1e-9


def test_two_proportion_p_reference_value():
    """Pooled two-sided z for 60/100 vs 40/100: p_pool=0.5,
    z = 0.2 / sqrt(0.25*(1/100+1/100)) = 2.8284 -> p = 0.004678."""
    from scipy import stats as ss
    p = two_proportion_p(60, 100, 40, 100)
    z = 0.2 / np.sqrt(0.25 * (2 / 100))
    assert abs(p - 2 * ss.norm.sf(z)) < 1e-9
    assert abs(p - 0.0046777) < 1e-5, p


def test_bh_excludes_nan_from_the_family():
    """A NaN p-value must neither be rejected nor inflate m (which would
    dilute the power of the real tests)."""
    # Without the NaN, [0.01, 0.02, 0.03] at alpha=0.05 all reject (m=3).
    with_nan = benjamini_hochberg([0.01, 0.02, 0.03, float("nan")], alpha=0.05)
    assert with_nan == [True, True, True, False]
    # The NaN did not change the verdicts vs a clean family of 3.
    assert benjamini_hochberg([0.01, 0.02, 0.03], alpha=0.05) == with_nan[:3]


def test_prob_diff_positive_symmetry_and_separation():
    from socio_sim.stats import prob_diff_positive
    # identical arms -> ~0.5 by symmetry
    assert abs(prob_diff_positive(30, 100, 30, 100) - 0.5) < 0.03
    # arm 1 clearly higher -> near 1
    assert prob_diff_positive(80, 100, 20, 100) > 0.99
    # arm 1 clearly lower -> near 0
    assert prob_diff_positive(20, 100, 80, 100) < 0.01
    assert np.isnan(prob_diff_positive(1, 0, 1, 10))
