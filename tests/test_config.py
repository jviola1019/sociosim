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
    assert RunConfig.quick(out_dir="out/a").config_hash() == RunConfig.quick(
        out_dir="out/b").config_hash()


def test_config_hash_ignores_noise_targets_in_trained_classifier_mode():
    targets_a = RunConfig.test().classifier_targets
    targets_b = {k: {"precision": 0.5, "recall": 0.5} for k in targets_a}
    a = RunConfig.test(classifier_mode="trained", classifier_targets=targets_a)
    b = RunConfig.test(classifier_mode="trained", classifier_targets=targets_b)
    assert a.config_hash() == b.config_hash()
    c = RunConfig.test(classifier_mode="noise", classifier_targets=targets_b)
    assert a.config_hash() != c.config_hash()


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
    with pytest.raises(ConfigError, match="llm_base_url"):
        RunConfig.test(content_mode="ollama",
                       llm_base_url="http://169.254.169.254/latest").validate()
    with pytest.raises(ConfigError, match="graph_params"):
        RunConfig.test(n_agents=3, graph_params={"m": 5}).validate()
    with pytest.raises(ConfigError, match="feed_size"):
        RunConfig.test(feed_size=0).validate()
    with pytest.raises(ConfigError, match="ad_slot_interval"):
        RunConfig.test(ad_slot_interval=0).validate()
    with pytest.raises(ConfigError, match="ad_frequency_cap_per_day"):
        RunConfig.test(ad_frequency_cap_per_day=0).validate()


def test_validation_rejects_malformed_numeric_fields():
    bad_cases = [
        ({"n_ticks": "bad"}, "n_ticks"),
        ({"feed_size": "bad"}, "feed_size"),
        ({"ad_slot_interval": "bad"}, "ad_slot_interval"),
        ({"ad_frequency_cap_per_day": "bad"}, "ad_frequency_cap_per_day"),
    ]
    for kwargs, field in bad_cases:
        with pytest.raises(ConfigError, match=field):
            RunConfig.test(**kwargs).validate()


def test_validation_rejects_malformed_graph_params():
    bad_cases = [
        ({"graph_params": {"m": "bad"}}, "graph_params"),
        ({"graph_kind": "ws", "graph_params": {"k": "bad"}}, "graph_params"),
        ({"graph_kind": "plc", "graph_params": {"m": 5, "p": "bad"}},
         "graph_params"),
        ({"graph_kind": "sbm",
          "graph_params": {"block_sizes": ["bad"], "p_matrix": [[0.1]]}},
         "graph_params"),
        ({"graph_kind": "sbm", "n_agents": 200,
          "graph_params": {"block_sizes": [100, 100],
                           "p_matrix": [["bad", 0.1], [0.1, 0.2]]}},
         "graph_params"),
    ]
    for kwargs, field in bad_cases:
        with pytest.raises(ConfigError, match=field):
            RunConfig.test(**kwargs).validate()


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


def test_behavior_params_are_validated():
    from socio_sim.behavior import BehaviorParams
    with pytest.raises(ConfigError, match="p_post_given_active"):
        RunConfig.test(behavior=BehaviorParams(p_post_given_active=2.0)).validate()
    with pytest.raises(ConfigError, match="impression_fatigue"):
        RunConfig.test(behavior=BehaviorParams(impression_fatigue=-1.0)).validate()
