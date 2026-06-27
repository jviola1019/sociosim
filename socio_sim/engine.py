"""Simulation engine: the hourly tick loop wiring all modules (Spec §3, design §2).

Data flow per tick:
  active mask -> posts (generate, classify, moderate) -> moderation queues ->
  ad auctions -> feeds (impressions) -> engagement/flags/shares ->
  belief + fatigue updates.

Determinism: every random draw comes from a module-keyed SeedTree generator;
events append in a fixed order; replays from the manifest are bit-identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from socio_sim.ads.auction import AdSystem
from socio_sim.ads.campaigns import Campaign, campaign_to_spec
from socio_sim.agents.personas import Personas
from socio_sim.agents.state import AgentState
from socio_sim.config import RunConfig
from socio_sim.content.claude_adapter import ClaudeAdapter
from socio_sim.content.classify import NoisyClassifier
from socio_sim.content.generate import TemplateGenerator
from socio_sim.feed.ranking import FeedRanker
from socio_sim.graph.generators import make_graph, mix_homophily
from socio_sim.graph.metrics import sample_subgraph
from socio_sim.graph.metrics import summary as graph_summary
from socio_sim.logs.events import EventLog
from socio_sim.logs.manifest import Manifest
from socio_sim.moderation.workflow import ModerationSystem
from socio_sim.policy.engine import PolicyEngine

# Behaviour constants now live in socio_sim.behavior.BehaviorParams (cfg.behavior),
# so they are documented, sensitivity-testable, and calibratable. Defaults there
# reproduce the prior hardcoded values exactly (determinism guard locks this).

HARMFUL_CATEGORIES = {"hate", "harassment", "fraud", "misinfo", "adult",
                      "illegal_goods", "self_harm"}

#: Content modes that call an external LLM (logged as llm_call events).
LLM_CONTENT_MODES = {"claude", "ollama", "openai_compatible"}


def default_campaigns(cfg: RunConfig) -> list[Campaign]:
    budget = 0.02 * cfg.n_agents  # scales with audience size
    return [
        Campaign(id="brand-general", advertiser="BrandCo", bid=2.0,
                 budget=budget, base_ctr=0.012, base_cvr=0.05),
        Campaign(id="tech-niche", advertiser="GadgetInc", bid=3.5,
                 budget=budget / 2, targeting={"topics": [2]},
                 base_ctr=0.020, base_cvr=0.08),
        Campaign(id="adults-finance", advertiser="FinServe", bid=2.8,
                 budget=budget / 2,
                 targeting={"age_groups": ["25-34", "35-49", "50-64", "65+"]},
                 base_ctr=0.008, base_cvr=0.10),
    ]


@dataclass
class RunResult:
    log: EventLog
    manifest: Manifest
    personas: Personas
    campaigns: list
    graph_stats: dict
    config: RunConfig
    ads: AdSystem


class Simulation:
    def __init__(self, cfg: RunConfig, campaigns: list | None = None):
        cfg.validate()
        self.cfg = cfg
        self.bp = cfg.behavior  # documented behaviour knobs (was module constants)
        from socio_sim.rng import SeedTree
        tree = SeedTree(cfg.root_seed)
        rep = cfg.replicate_id
        # Dedicated stream per decision type: keeps common-random-number
        # pairing intact when an intervention changes one subsystem only.
        self.rngs = {name: tree.generator(name, rep) for name in (
            "graph", "agents", "content", "classifier", "moderation", "ads",
            "feed", "activity", "posting", "engagement", "optout", "conversion",
            "ad_latency", "graph_dynamics")}

        # Graph + personas
        graph = make_graph(cfg.graph_kind, cfg.n_agents, self.rngs["graph"],
                           **cfg.graph_params)
        degrees = np.array([graph.degree(i) for i in range(cfg.n_agents)])
        self.personas = Personas.sample(cfg.n_agents, degrees,
                                        self.rngs["agents"], cfg.n_topics)
        if cfg.homophily_rewire_fraction > 0:
            attrs = {i: ("L" if self.personas.ideology[i, 0] < 0 else "R")
                     for i in range(cfg.n_agents)}
            graph = mix_homophily(graph, attrs, cfg.homophily_rewire_fraction,
                                  self.rngs["graph"])
        self.graph_stats = graph_summary(graph)
        # Sampled subgraph for the topology view (hubs + their edges, coloured
        # by ideology bucket). Not in the event stream -> determinism unaffected.
        _groups = {i: ("L" if self.personas.ideology[i, 0] < 0 else "R")
                   for i in range(cfg.n_agents)}
        self.graph_stats["graph_sample"] = sample_subgraph(graph, _groups)
        self.neighbors = {i: np.array(sorted(graph.neighbors(i)), dtype=int)
                          for i in range(cfg.n_agents)}
        # Optional dynamic-graph state (follow/unfollow/churn). Built only when
        # enabled so static (default) runs pay nothing and stay bit-identical.
        self._dynamic_graph = (cfg.follow_rate > 0 or cfg.unfollow_rate > 0
                               or cfg.churn_rate > 0)
        self.churned: set[int] = set()
        self._adj = ({i: set(self.neighbors[i].tolist())
                      for i in range(cfg.n_agents)}
                     if self._dynamic_graph else None)

        self.state = AgentState.init(cfg.n_agents, cfg.n_topics)
        self.log = EventLog()

        # Content generation. Default: deterministic templates (free, exact
        # replays). Optional LLM backends all cache responses for replay and
        # degrade loudly to templates on failure:
        #   claude            -> Anthropic API (needs ANTHROPIC_API_KEY)
        #   ollama            -> free local Ollama server (no key)
        #   openai_compatible -> free local OpenAI-compatible server (no key)
        base_gen = TemplateGenerator(cfg, self.rngs["content"],
                                     inject_signal=(cfg.classifier_mode == "trained"))
        # The implicit LLM cache affects generated text, so keep it tied to the
        # behavioral config identity rather than output storage (`out_dir`).
        cache = cfg.llm_cache_path or str(
            Path("out") / "llm_cache" / f"{cfg.config_hash()}.json")
        if cfg.content_mode == "claude":
            self.generator = ClaudeAdapter(
                base=base_gen, cache_path=cache,
                model=cfg.llm_model or None,
                on_degradation=self._log_degradation)
        elif cfg.content_mode in ("ollama", "openai_compatible"):
            from socio_sim.content.llm_adapter import LLMAdapter
            self.generator = LLMAdapter(
                base=base_gen, cache_path=cache, backend=cfg.content_mode,
                model=cfg.llm_model, base_url=cfg.llm_base_url,
                on_degradation=self._log_degradation)
        else:
            self.generator = base_gen
        self._current_tick = 0

        if cfg.classifier_mode == "trained":
            # Train a REAL classifier on category-signal content (measured P/R,
            # not assumed). Deterministic: seeded training generator + numpy LR.
            from socio_sim.config import CATEGORIES
            from socio_sim.content.ml_classifier import (TrainableClassifier,
                                                         build_training_data)
            train_gen = TemplateGenerator(cfg, tree.generator("content_train", rep),
                                          inject_signal=True)
            texts, labels = build_training_data(train_gen, self.personas, n=1500)
            self.classifier = TrainableClassifier(CATEGORIES).fit(texts, labels)
        else:
            self.classifier = NoisyClassifier(cfg.classifier_targets,
                                              cfg.category_base_rates,
                                              self.rngs["classifier"])
        self.policy = PolicyEngine(cfg.jurisdictions, cfg.ftc_enabled)
        self.moderation = ModerationSystem(cfg, self.policy, self.personas,
                                           self.log, self.rngs["moderation"])
        self.campaigns = campaigns if campaigns is not None else default_campaigns(cfg)
        self._campaign_specs = [campaign_to_spec(c) for c in self.campaigns]
        self.ads = AdSystem(cfg, self.campaigns, self.personas, self.state,
                            self.policy, self.log, self.rngs["ads"],
                            baseline_rng=self.rngs["conversion"],
                            latency_rng=self.rngs["ad_latency"])
        self.feed = FeedRanker(cfg, self.personas, self.state, self.log,
                               self.rngs["feed"])

        # DSA non-personalised option: per-agent opt-out (EU mode only)
        if "EU" in cfg.jurisdictions:
            self.optout = self.rngs["optout"].random(cfg.n_agents) < cfg.eu_optout_rate
        else:
            self.optout = np.zeros(cfg.n_agents, dtype=bool)

        self.recent_posts: list = []
        self.scores_by_item: dict = {}

        # Red-team adversary populations (Spec §3.10): 1% of agents each.
        rt_rng = tree.generator("redteam", rep)
        n_adv = max(cfg.n_agents // 100, 1)
        self.spammers: set = set()
        self.amplifiers: set = set()
        self.brigaders: set = set()
        if "spammer" in cfg.red_team:
            self.spammers = set(rt_rng.choice(cfg.n_agents, n_adv,
                                              replace=False).tolist())
            # Spam bots are hyperactive by construction.
            ids = list(self.spammers)
            self.personas.activity[ids] = np.maximum(
                self.personas.activity[ids], 0.8)
        if "misinfo_amplifier" in cfg.red_team:
            self.amplifiers = set(rt_rng.choice(cfg.n_agents, n_adv,
                                                replace=False).tolist())
        if "brigading_ring" in cfg.red_team:
            self.brigaders = set(rt_rng.choice(cfg.n_agents, n_adv,
                                               replace=False).tolist())
        self._rt_rng = rt_rng

    def _classify(self, item) -> dict:
        """Platform belief about an item's categories: a real trained classifier
        on the item text (trained mode) or the calibrated noise model (default)."""
        if self.cfg.classifier_mode == "trained":
            return self.classifier.predict_scores(item.text)
        return self.classifier.classify_one(item.true_categories)

    def _follow_candidate(self, a: int, rng) -> int:
        """Triadic closure: a friend-of-a-friend if possible, else a random
        node (preferential-ish via the giant component). Deterministic."""
        nbrs = sorted(self._adj[a])
        if nbrs:
            mid = nbrs[int(rng.integers(0, len(nbrs)))]
            cands = sorted(self._adj[mid] - self._adj[a] - {a})
            if cands:
                return cands[int(rng.integers(0, len(cands)))]
        return int(rng.integers(0, self.cfg.n_agents))

    def _evolve_graph(self, tick: int):
        """Daily follow/unfollow/churn. Deterministic: a dedicated RNG stream is
        drawn in fixed agent order; ties are undirected (both endpoints updated).
        Emitted as follow/unfollow/churn events -> part of the hashed stream."""
        rng = self.rngs["graph_dynamics"]
        cfg = self.cfg
        changed: set[int] = set()
        for a in range(cfg.n_agents):
            if a in self.churned:
                continue
            if cfg.churn_rate > 0 and rng.random() < cfg.churn_rate:
                self.churned.add(a)
                self.log.append(tick=tick, kind="churn", actor_id=a,
                                content_id=None,
                                data={"degree": len(self._adj[a])})
                continue
            if (cfg.unfollow_rate > 0 and self._adj[a]
                    and rng.random() < cfg.unfollow_rate):
                ties = sorted(self._adj[a])
                b = ties[int(rng.integers(0, len(ties)))]
                self._adj[a].discard(b)
                self._adj[b].discard(a)
                changed.update((a, b))
                self.log.append(tick=tick, kind="unfollow", actor_id=a,
                                content_id=None, data={"target": int(b)})
            if cfg.follow_rate > 0 and rng.random() < cfg.follow_rate:
                c = self._follow_candidate(a, rng)
                if c != a and c not in self.churned and c not in self._adj[a]:
                    self._adj[a].add(c)
                    self._adj[c].add(a)
                    changed.update((a, c))
                    self.log.append(tick=tick, kind="follow", actor_id=a,
                                    content_id=None, data={"target": int(c)})
        for c in changed:
            self.neighbors[c] = np.array(sorted(self._adj[c]), dtype=int)

    def _log_degradation(self, reason: str):
        self.log.append(tick=self._current_tick, kind="degradation",
                        actor_id=-1, content_id=None, data={"reason": reason})

    # ------------------------------------------------------------------
    def run(self, write: bool = False, progress_callback=None) -> RunResult:
        """Run the tick loop.

        progress_callback(tick, n_ticks) is invoked each tick (e.g. for a web
        progress bar). It must not mutate simulation state; it is excluded from
        determinism (logs/replay are unaffected by it).
        """
        cfg = self.cfg
        for tick in range(cfg.n_ticks):
            self._current_tick = tick
            hour = (tick * cfg.tick_hours) % 24
            if hour == 0:
                self.state.reset_daily_counters()
                # Daily social-graph evolution (follow/unfollow/churn) BEFORE the
                # day's baseline/feeds so new ties take effect same day.
                if self._dynamic_graph and tick > 0:
                    self._evolve_graph(tick)
                # Organic (non-ad) conversion opportunity for every agent, so
                # the holdout has a measurable baseline rate (valid lift).
                if cfg.ads_enabled:
                    for aid in range(cfg.n_agents):
                        self.ads.simulate_baseline(aid, tick)
            self.state.decay_fatigue(self.bp.fatigue_decay_per_tick)

            active = np.flatnonzero(
                self.personas.active_mask(hour, self.rngs["activity"]))
            if self.churned:
                active = active[~np.isin(active,
                                         np.fromiter(self.churned, dtype=int))]

            self._do_posting(active, tick)
            self.moderation.process_queues(tick)
            self._do_feeds(active, tick)

            cutoff = tick - self.bp.recent_window_ticks
            self.recent_posts = [p for p in self.recent_posts if p.tick > cutoff]

            if progress_callback is not None:
                progress_callback(tick + 1, cfg.n_ticks)

        llm_cache_hash = (self.generator.cache_hash()
                          if hasattr(self.generator, "cache_hash") else None)
        manifest = Manifest.create(cfg, self.policy.pack_versions(),
                                   llm_cache_hash=llm_cache_hash,
                                   campaign_specs=self._campaign_specs)
        manifest.stream_hash = self.log.stream_hash()
        manifest.event_count = len(self.log.events)

        if write:
            out = Path(cfg.out_dir)
            out.mkdir(parents=True, exist_ok=True)
            persist = EventLog(path=out / "events.jsonl")
            for e in self.log.events:
                persist.append(**e)
            persist.close()
            manifest.save(out / "manifest.json")

        if self._dynamic_graph:
            import networkx as nx
            final = nx.Graph()
            final.add_nodes_from(range(cfg.n_agents))
            for u, nbrs in self._adj.items():
                for v in nbrs:
                    if u < v:
                        final.add_edge(u, v)
            initial = {k: v for k, v in self.graph_stats.items()
                       if k not in ("graph_sample", "initial", "final")}
            final_stats = graph_summary(final)
            self.graph_stats["initial"] = initial
            self.graph_stats["final"] = final_stats
            self.graph_stats.update(final_stats)

        return RunResult(log=self.log, manifest=manifest, personas=self.personas,
                         campaigns=self.campaigns, graph_stats=self.graph_stats,
                         config=cfg, ads=self.ads)

    # ------------------------------------------------------------------
    def _do_posting(self, active: np.ndarray, tick: int):
        posting_rng = self.rngs["posting"]
        for agent_id in active:
            is_spammer = int(agent_id) in self.spammers
            p_post = (self.bp.spammer_post_prob if is_spammer
                      else self.bp.p_post_given_active)
            if posting_rng.random() >= p_post:
                continue
            item = self.generator.generate(int(agent_id), self.personas, tick)
            if is_spammer:
                item.text = f"LIMITED OFFER!!! Click now -> bit.ly/{item.id}"
                if self._rt_rng.random() < 0.5:
                    item.true_categories.add("fraud")
            if int(agent_id) in self.amplifiers \
                    and self._rt_rng.random() < self.bp.amplifier_misinfo_prob:
                item.true_categories.add("misinfo")
                item.stance = float(np.clip(
                    item.stance * self.bp.amplifier_stance_gain, -1, 1))
            if self.cfg.content_mode in LLM_CONTENT_MODES:
                self.log.append(tick=tick, kind="llm_call", actor_id=int(agent_id),
                                content_id=item.id, data={
                                    "backend": self.cfg.content_mode,
                                    "model": getattr(self.generator, "model",
                                             getattr(self.generator, "MODEL", "n/a")),
                                    "text_preview": item.text[:60],
                                    "provenance": "generated_presentation_text",
                                    "state_mutation_allowed": False,
                                    "llm_cache_hash": (
                                        self.generator.cache_hash()
                                        if hasattr(self.generator, "cache_hash")
                                        else None),
                                })
            scores = self._classify(item)
            self.scores_by_item[item.id] = scores
            self.log.append(tick=tick, kind="post", actor_id=int(agent_id),
                            content_id=item.id, data={
                                "topic": item.topic,
                                "stance": round(item.stance, 4),
                                "media_type": item.media_type,
                                "true_categories": sorted(item.true_categories),
                                "ai_generated": item.ai_generated,
                                "parent_id": item.parent_id})
            self.log.append(tick=tick, kind="classify", actor_id=-1,
                            content_id=item.id, data={
                                "scores": {k: round(v, 4)
                                           for k, v in scores.items()
                                           if v >= 0.5}})
            self.moderation.handle(item, scores, tick)
            self.recent_posts.append(item)

    # ------------------------------------------------------------------
    def _do_feeds(self, active: np.ndarray, tick: int):
        eng = self.rngs["engagement"]
        feed_rng = self.rngs["feed"]
        n_topics = self.cfg.n_topics
        exposure = np.zeros((self.cfg.n_agents, n_topics))
        exposure_count = np.zeros((self.cfg.n_agents, n_topics))

        # Index posts by author ONCE per tick (was an O(recent_posts) scan per
        # active agent -> the dominant cost at scale). Candidate order is
        # irrelevant downstream: FeedRanker.serve sorts by (-score, id), a total
        # order, and candidates are not sampled — so building them by author
        # changes nothing in the output. The exploration POOL is sampled, so its
        # construction did change (oversample indices from recent_posts instead
        # of materialising the full non-neighbour list); that is an intentional
        # behaviour change and the locked determinism baselines were regenerated.
        recent = self.recent_posts
        n_recent = len(recent)
        posts_by_author: dict = {}
        for p in recent:
            posts_by_author.setdefault(p.author_id, []).append(p)
        pool_size = self.bp.exploration_pool_size

        for agent_id in active:
            aid = int(agent_id)
            neigh = self.neighbors[aid]
            if len(neigh) == 0 and not recent:
                continue
            neigh_set = set(neigh.tolist())
            candidates = []
            for n in neigh_set:
                if n == aid:
                    continue
                lst = posts_by_author.get(n)
                if lst:
                    candidates.extend(lst)
            # Exploration pool: a random sample of non-neighbour posts, drawn by
            # oversampling recent_posts indices (O(k)) then filtering — avoids the
            # per-agent O(recent_posts) scan.
            pool = []
            if n_recent:
                k = min(n_recent, pool_size * 3)
                idx = (sorted(feed_rng.choice(n_recent, k, replace=False).tolist())
                       if n_recent > k else range(n_recent))
                for i in idx:
                    p = recent[i]
                    if p.author_id not in neigh_set and p.author_id != aid:
                        pool.append(p)
                        if len(pool) >= pool_size:
                            break

            ads = []
            if self.cfg.ads_enabled:
                creative = self.ads.run_auction(aid, tick)
                if creative is not None:
                    # Creatives pass through moderation (FTC disclosure etc.)
                    self.moderation.handle(creative, {}, tick,
                                           context={"is_ad": True})
                    ads = [creative]

            feed = self.feed.serve(aid, candidates, ads, tick,
                                   opted_out=bool(self.optout[aid]),
                                   exploration_pool=pool)
            if not feed:
                continue

            self.state.add_fatigue(np.bincount(
                [aid], weights=[self.bp.impression_fatigue * len(feed)],
                minlength=self.cfg.n_agents))

            for item in feed:
                if item.sponsored and item.campaign_id:
                    self.ads.simulate_response(aid, item, tick)
                    continue
                interest = float(self.personas.interests[aid, item.topic])
                belief = float(self.state.beliefs[aid, item.topic])
                match = 1.0 - abs(item.stance - belief) / 2.0
                p_engage = np.clip(
                    self.bp.engagement_base * interest * match
                    / (1.0 + float(self.state.fatigue[aid])),
                    0, 1)
                if eng.random() < p_engage:
                    item.likes += 1
                    self.feed.record_engagement(aid, item.author_id)
                    self.log.append(tick=tick, kind="engagement", actor_id=aid,
                                    content_id=item.id,
                                    data={"type": "like", "topic": item.topic})
                    exposure[aid, item.topic] += item.stance
                    exposure_count[aid, item.topic] += 1
                    if eng.random() < self.bp.p_share_given_engaged:
                        self._do_share(aid, item, tick)

                # Brigading ring: coordinated bad-faith flags on influencers.
                if aid in self.brigaders \
                        and 0 <= item.author_id < self.personas.n \
                        and self.personas.influencer[item.author_id] \
                        and eng.random() < self.bp.brigade_flag_prob:
                    self.log.append(tick=tick, kind="flag", actor_id=aid,
                                    content_id=item.id,
                                    data={"brigade": True})
                    scores = self.scores_by_item.get(item.id, {})
                    self.moderation.handle(item, scores, tick,
                                           context={"user_flagged": True})

                # Flagging of perceived-harmful content (user easy-flag path)
                if item.true_categories & HARMFUL_CATEGORIES:
                    attitude = float(self.personas.moderation_attitude[aid])
                    if eng.random() < self.bp.p_flag_scale * attitude:
                        trusted = bool(self.personas.trusted_flagger[aid])
                        self.log.append(tick=tick, kind="flag", actor_id=aid,
                                        content_id=item.id,
                                        data={"trusted_flagger": trusted})
                        scores = self.scores_by_item.get(item.id, {})
                        self.moderation.handle(item, scores, tick,
                                               context={"user_flagged": True,
                                                        "trusted_flagger": trusted})

        engaged = exposure_count.sum(axis=1) > 0
        if engaged.any():
            mean_exposure = np.where(exposure_count > 0,
                                     exposure / np.maximum(exposure_count, 1), 0.0)
            self.state.update_beliefs(mean_exposure, self.personas.trust)

    def _do_share(self, agent_id: int, item, tick: int):
        share = self.generator.generate(agent_id, self.personas, tick)
        # A share propagates the original content's payload and ground truth.
        share.topic = item.topic
        share.stance = item.stance
        share.true_categories = set(item.true_categories)
        share.ai_generated = item.ai_generated
        share.parent_id = item.id
        share.text = f"RT: {item.text}"
        item.shares += 1
        scores = self._classify(share)
        self.scores_by_item[share.id] = scores
        self.log.append(tick=tick, kind="post", actor_id=agent_id,
                        content_id=share.id, data={
                            "topic": share.topic,
                            "stance": round(share.stance, 4),
                            "media_type": share.media_type,
                            "true_categories": sorted(share.true_categories),
                            "ai_generated": share.ai_generated,
                            "parent_id": share.parent_id})
        self.moderation.handle(share, scores, tick)
        self.recent_posts.append(share)
