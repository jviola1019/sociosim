
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation
from socio_sim.experiments.compare import compare
from socio_sim.experiments.scenarios import (disclosure_evader_campaigns,
                                             policy_stress_eu_vs_us,
                                             red_team_suite)


def n_original_posts(result):
    originals = [e for e in result.log.by_kind("post")
                 if e["data"].get("parent_id") is None]
    return {"posts": float(len(originals))}


def test_common_random_numbers_zero_delta_on_identical_worlds():
    # Posting has its own RNG stream, so a feed-strategy intervention must
    # leave original-post counts identical under CRN in every replicate.
    base = RunConfig.test(n_agents=100, n_ticks=24)
    interv = RunConfig.test(n_agents=100, n_ticks=24,
                            feed_strategy="chronological")
    res = compare(base, interv, n_replicates=3, metric_fn=n_original_posts)
    assert res["posts"]["deltas"] == [0.0, 0.0, 0.0]


def test_independent_seeds_give_nonzero_deltas():
    base = RunConfig.test(n_agents=100, n_ticks=24)
    interv = RunConfig.test(n_agents=100, n_ticks=24, root_seed=777)
    res = compare(base, interv, n_replicates=3, metric_fn=n_original_posts)
    assert any(d != 0.0 for d in res["posts"]["deltas"])


def test_spammer_raises_post_volume_and_moderation_load():
    base_cfg = RunConfig.test(n_agents=100, n_ticks=48)
    spam_cfg = RunConfig.test(n_agents=100, n_ticks=48, red_team=("spammer",))
    base = Simulation(base_cfg).run()
    spam_sim = Simulation(spam_cfg)
    spam = spam_sim.run()
    assert len(spam.log.by_kind("post")) > len(base.log.by_kind("post"))
    spammer_posts = [e for e in spam.log.by_kind("post")
                     if e["actor_id"] in spam_sim.spammers
                     and e["data"].get("parent_id") is None]
    per_capita = len(spam.log.by_kind("post")) / spam_cfg.n_agents
    assert len(spammer_posts) / len(spam_sim.spammers) > 3 * per_capita


def test_disclosure_evader_caught_iff_ftc_pack_on():
    cfg_on = RunConfig.test(n_agents=100, n_ticks=24, ftc_enabled=True)
    res_on = Simulation(cfg_on,
                        campaigns=disclosure_evader_campaigns(cfg_on)).run()
    violations_on = [e for e in res_on.log.by_kind("moderation")
                     if e["data"].get("ftc_violation")]
    assert violations_on, "FTC pack should catch the disclosure evader"
    assert all("ad-evader" in e["content_id"] for e in violations_on)

    cfg_off = RunConfig.test(n_agents=100, n_ticks=24, ftc_enabled=False)
    res_off = Simulation(cfg_off,
                         campaigns=disclosure_evader_campaigns(cfg_off)).run()
    violations_off = [e for e in res_off.log.by_kind("moderation")
                      if e["data"].get("ftc_violation")]
    assert not violations_off


def test_scenarios_construct_valid_configs():
    b, i = policy_stress_eu_vs_us("test")
    assert b.jurisdictions == ("US",) and i.jurisdictions == ("EU",)
    suite = red_team_suite("test")
    assert set(suite) == {"spammer", "misinfo_amplifier", "brigading_ring",
                          "auction_gamer", "disclosure_evader"}
    for entry in suite.values():
        entry["config"].validate()
