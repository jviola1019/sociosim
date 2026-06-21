import pytest

from socio_sim.config import ConfigError, RunConfig


def test_profiles_have_approved_defaults():
    std = RunConfig.standard()
    assert std.n_agents == 10_000
    assert std.n_ticks == 28 * 24
    assert std.n_replicates == 100
    quick = RunConfig.quick()
    assert quick.n_agents == 1_000
    assert quick.n_ticks == 7 * 24
    tst = RunConfig.test()
    assert tst.n_agents <= 200
    assert tst.n_ticks <= 48


def test_config_hash_stable_and_sensitive():
    a = RunConfig.quick()
    b = RunConfig.quick()
    assert a.config_hash() == b.config_hash()
    c = RunConfig.quick(root_seed=a.root_seed + 1)
    assert c.config_hash() != a.config_hash()


def test_validation_rejects_bad_fields():
    with pytest.raises(ConfigError, match="n_agents"):
        RunConfig.test(n_agents=0).validate()
    with pytest.raises(ConfigError, match="jurisdictions"):
        RunConfig.test(jurisdictions=("MARS",)).validate()
    with pytest.raises(ConfigError, match="feed_strategy"):
        RunConfig.test(feed_strategy="psychic").validate()
    with pytest.raises(ConfigError, match="holdout_fraction"):
        RunConfig.test(holdout_fraction=1.5).validate()
    with pytest.raises(ConfigError, match="content_mode"):
        RunConfig.test(content_mode="oracle").validate()


def test_round_trip_dict():
    cfg = RunConfig.quick(jurisdictions=("EU", "CN"))
    again = RunConfig.from_dict(cfg.to_dict())
    assert again == cfg
    assert again.config_hash() == cfg.config_hash()


def test_behavior_params_are_live_and_serializable():
    """Extracted BehaviorParams must actually drive the engine and round-trip
    through the manifest (so replays from a manifest reproduce them)."""
    from socio_sim.behavior import BehaviorParams
    from socio_sim.engine import Simulation
    base = RunConfig.test(jurisdictions=("EU",))
    tweaked = RunConfig.test(jurisdictions=("EU",),
                             behavior=BehaviorParams(p_post_given_active=0.6))
    h0 = Simulation(base).run().log.stream_hash()
    h1 = Simulation(tweaked).run().log.stream_hash()
    assert h0 != h1, "BehaviorParams override had no effect -> not wired"
    rt = RunConfig.from_dict(tweaked.to_dict())
    assert rt.behavior.p_post_given_active == 0.6
    assert rt.config_hash() == tweaked.config_hash()
