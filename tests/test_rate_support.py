"""Event-support accounting tests (audit Phase 5): a z-distance must never
be presented as meaningful for a rate whose event count is inadequate, and
protocol v2's exclusions are PREDECLARED (v1's committed verdict untouched).
"""

import pytest

from socio_sim.validation import seed_protocol as sp
from socio_sim.validation.support import (min_support_n, rate_support,
                                          wilson_interval)

TARGETS = {
    "ad_ctr": {"value": 0.001, "tolerance": 0.001},
    "appeal_grant_rate": {"value": 0.11, "tolerance": 0.044},
}


def _summary(filed=8, granted_rate=0.0, impressions=436, clicks=0):
    return {"appeals": {"filed": filed, "granted_rate": granted_rate},
            "ads": {"c1": {"impressions": impressions, "clicks": clicks}}}


def test_min_support_thresholds_match_the_closed_form():
    # n >= z^2 p(1-p)/tol^2
    assert min_support_n(0.11, 0.044) == 195
    assert min_support_n(0.001, 0.001) == 3838


def test_profile_scale_counts_are_inadequately_supported():
    """The measured fitting/validation-seed counts (appeals 3-12,
    impressions 119-451) are far below the support thresholds."""
    sup = rate_support(_summary(), TARGETS)
    ap = sup["appeal_grant_rate"]
    assert ap["numerator"] == 0 and ap["denominator"] == 8
    assert ap["minimum_support_n"] == 195
    assert ap["adequately_supported"] is False
    assert "insufficient event support" in ap["exclusion_rationale"]
    ctr = sup["ad_ctr"]
    assert ctr["denominator"] == 436 and ctr["minimum_support_n"] == 3838
    assert ctr["adequately_supported"] is False
    # v1 inclusion is preserved (committed verdict reproducible); v2 excludes
    assert ap["included_in_acceptance_v1"] is True
    assert ap["included_in_acceptance_v2"] is False


def test_adequate_support_flips_the_flag_and_clears_the_rationale():
    sup = rate_support(_summary(filed=400, granted_rate=0.11,
                                impressions=10_000, clicks=10), TARGETS)
    assert sup["appeal_grant_rate"]["adequately_supported"] is True
    assert sup["appeal_grant_rate"]["exclusion_rationale"] is None
    assert sup["ad_ctr"]["adequately_supported"] is True


def test_zero_denominator_is_flagged_not_fabricated():
    sup = rate_support(_summary(filed=0, impressions=0), TARGETS)
    ap = sup["appeal_grant_rate"]
    assert ap["zero_denominator"] is True and ap["denominator"] == 0
    lo, hi = ap["interval"]
    assert lo != lo and hi != hi          # NaN interval, never a made-up 0


def test_wilson_interval_basics():
    lo, hi = wilson_interval(0, 8)
    assert lo == 0.0 and 0.3 < hi < 0.4   # tiny n -> interval spans several
    assert hi - lo > TARGETS["appeal_grant_rate"]["tolerance"] * 2
    lo, hi = wilson_interval(44, 400)     # ~0.11 at adequate n
    assert lo < 0.11 < hi and (hi - lo) / 2 < 0.044


def test_protocol_v2_is_predeclared_disjoint_and_hash_stable():
    v2 = sp.PROTOCOL_V2
    assert v2["status"] == "predeclared_not_evaluated"
    assert v2["acceptance_metrics"] == sp.STRUCTURAL_METRICS
    assert set(v2["descriptive_only_metrics"]) == {"ad_ctr", "appeal_grant_rate"}
    h2 = set(v2["holdout_seeds"])
    assert len(h2) == 20
    for v1_list in (sp.FITTING_SEEDS, sp.VALIDATION_SEEDS, sp.HOLDOUT_SEEDS):
        assert not (h2 & set(v1_list)), "v2 holdout must be disjoint from v1"
    # predeclaration pin: changing the v2 holdout list is a reviewed act
    assert sp.seeds_sha256(v2["holdout_seeds"]) == (
        "2395094157a5754fbdcf9951113386dbe191a9b44787ecc388c93b73f3e95182")
    # and the v1 committed verdict is untouched by all of this
    results = sp.load_results()
    assert results["acceptance"]["accepted"] is False


def test_run_and_analyze_attaches_rate_support():
    from socio_sim.config import RunConfig
    from socio_sim.pipeline import run_and_analyze
    a = run_and_analyze(RunConfig.test(n_agents=60, n_ticks=8),
                        verify_replay=False, write=False)
    assert set(a.rate_support) == {"ad_ctr", "appeal_grant_rate"}
    for rec in a.rate_support.values():
        assert {"numerator", "denominator", "interval_method",
                "minimum_support_n", "adequately_supported"} <= set(rec)


def test_no_ordinary_z_presented_as_meaningful_without_support():
    """The support record is the machine-readable contract the UI/report
    uses: an inadequately supported rate carries its rationale, so no
    surface may present its z-distance as a plain pass/fail distance."""
    sup = rate_support(_summary(), TARGETS)
    for rec in sup.values():
        if not rec["adequately_supported"]:
            assert rec["exclusion_rationale"]
            assert rec["included_in_acceptance_v2"] is False


@pytest.mark.parametrize("k,n", [(0, 0), (1, 1), (5, 5)])
def test_interval_edges_never_crash(k, n):
    lo, hi = wilson_interval(k, n)
    assert (lo != lo) == (n == 0)
