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
