import numpy as np

from socio_sim.agents.personas import Personas
from socio_sim.agents.state import AgentState
from socio_sim.config import RunConfig
from socio_sim.content.items import ContentItem
from socio_sim.feed.ranking import FeedRanker
from socio_sim.logs.events import EventLog
from socio_sim.rng import SeedTree


def post(pid, author, tick, topic=0, stance=0.0, status="visible"):
    return ContentItem(id=pid, author_id=author, tick=tick, media_type="text",
                       topic=topic, stance=stance, text=pid, status=status)


def setup(strategy="personalized", epsilon=0.0, **cfg_overrides):
    cfg = RunConfig.test(feed_strategy=strategy, exploration_epsilon=epsilon,
                         **cfg_overrides)
    n = 30
    personas = Personas.sample(
        n, degrees=np.ones(n), rng=SeedTree(4).generator("agents", 0))
    state = AgentState.init(n, cfg.n_topics)
    log = EventLog()
    ranker = FeedRanker(cfg, personas, state, log,
                        SeedTree(4).generator("feed", 0))
    return ranker, log, personas, state


def test_chronological_ordering():
    ranker, log, _, _ = setup("chronological")
    candidates = [post(f"p{t}", author=t % 5, tick=t) for t in range(10)]
    feed = ranker.serve(agent_id=0, candidates=candidates, ads=[], tick=10)
    ticks = [it.tick for it in feed]
    assert ticks == sorted(ticks, reverse=True)


def test_removed_excluded_downranked_demoted():
    ranker, _, _, _ = setup("personalized")
    ok = post("ok", author=1, tick=9)
    down = post("down", author=1, tick=9, status="downranked")
    gone = post("gone", author=1, tick=9, status="removed")
    feed = ranker.serve(0, [down, ok, gone], ads=[], tick=10)
    ids = [it.id for it in feed]
    assert "gone" not in ids
    assert ids.index("ok") < ids.index("down")


def test_affinity_boosts_author():
    ranker, _, _, _ = setup("personalized")
    for _ in range(5):
        ranker.record_engagement(agent_id=0, author_id=7)
    a = post("from7", author=7, tick=5)
    b = post("from8", author=8, tick=5)
    feed = ranker.serve(0, [b, a], ads=[], tick=10)
    assert feed[0].id == "from7"


def test_eu_optout_forces_chronological():
    ranker, log, _, _ = setup("personalized")
    for _ in range(5):
        ranker.record_engagement(agent_id=0, author_id=7)
    old_affinity = post("old7", author=7, tick=1)
    fresh = post("fresh", author=9, tick=9)
    feed = ranker.serve(0, [old_affinity, fresh], ads=[], tick=10,
                        opted_out=True)
    assert feed[0].id == "fresh"  # recency wins despite affinity
    imp = log.by_kind("impression")[0]
    assert imp["data"]["strategy"] == "chronological"


def test_ads_interleaved_at_slots():
    ranker, _, _, _ = setup("personalized", ad_slot_interval=3)
    candidates = [post(f"p{i}", author=i % 5, tick=i) for i in range(9)]
    ad = post("ad1", author=-1, tick=9)
    ad.sponsored = True
    feed = ranker.serve(0, candidates, ads=[ad], tick=10)
    assert feed[2].id == "ad1"  # inserted at the first ad slot


def test_impressions_logged_with_features():
    ranker, log, _, _ = setup("personalized")
    candidates = [post(f"p{i}", author=i % 5, tick=i) for i in range(6)]
    feed = ranker.serve(0, candidates, ads=[], tick=10)
    imps = log.by_kind("impression")
    assert len(imps) == len(feed)
    for imp in imps:
        assert "score" in imp["data"]
        assert "features" in imp["data"]
        assert "position" in imp["data"]


def test_exploration_injects_unseen_author():
    ranker, _, _, _ = setup("personalized", epsilon=1.0)
    followee_posts = [post(f"f{i}", author=1, tick=8) for i in range(5)]
    explore_pool = [post("new", author=20, tick=8)]
    feed = ranker.serve(0, followee_posts, ads=[], tick=10,
                        exploration_pool=explore_pool)
    assert any(it.id == "new" for it in feed)
