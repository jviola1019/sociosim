import numpy as np

from socio_sim.agents.personas import DIURNAL_CURVE, Personas
from socio_sim.agents.state import AgentState
from socio_sim.rng import SeedTree


def make_personas(n=2000):
    rng = SeedTree(11).generator("agents", 0)
    degrees = SeedTree(11).generator("graph", 0).integers(1, 200, size=n)
    return Personas.sample(n, degrees=degrees, rng=rng)


def test_minor_flag_consistent_with_age_group():
    p = make_personas()
    assert np.array_equal(p.is_minor, p.age_group == "13-17")
    minor_rate = p.is_minor.mean()
    assert 0.03 < minor_rate < 0.15


def test_diurnal_curve_peak_and_trough():
    peak = DIURNAL_CURVE[16:19].mean()
    trough = DIURNAL_CURVE[4:7].mean()
    assert peak > 2 * trough
    assert np.isclose(DIURNAL_CURVE.mean(), 1.0, atol=1e-9)


def test_activity_heavy_tail():
    p = make_personas()
    assert p.activity.max() > 5 * np.median(p.activity)
    assert (p.activity >= 0).all() and (p.activity <= 1).all()


def test_active_mask_respects_diurnal():
    p = make_personas(5000)
    rng = SeedTree(11).generator("activity", 0)
    active_peak = p.active_mask(hour=17, rng=rng).mean()
    active_trough = p.active_mask(hour=5, rng=rng).mean()
    assert active_peak > active_trough


def test_influencers_are_top_degree():
    p = make_personas()
    assert 0.005 <= p.influencer.mean() <= 0.02


def test_belief_update_moves_toward_stance_and_stays_bounded():
    n, topics = 100, 4
    state = AgentState.init(n, topics)
    trust = np.full(n, 0.8)
    exposed = np.zeros((n, topics))
    exposed[:, 2] = 1.0  # everyone sees stance +1 content on topic 2
    before = state.beliefs[:, 2].copy()
    state.update_beliefs(exposed, trust, lr=0.1)
    after = state.beliefs[:, 2]
    assert (after >= before).all()
    assert (state.beliefs <= 1).all() and (state.beliefs >= -1).all()


def test_fatigue_accumulates_and_decays():
    state = AgentState.init(10, 2)
    state.add_fatigue(np.ones(10) * 0.5)
    assert (state.fatigue > 0).all()
    f = state.fatigue.copy()
    state.decay_fatigue(rate=0.5)
    assert (state.fatigue < f).all()
