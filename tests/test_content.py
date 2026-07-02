import json

import numpy as np

from socio_sim.agents.personas import Personas
from socio_sim.config import RunConfig
from socio_sim.content.claude_adapter import ClaudeAdapter
from socio_sim.content.classify import NoisyClassifier, confusion
from socio_sim.content.generate import TemplateGenerator
from socio_sim.content.items import ContentItem
from socio_sim.rng import SeedTree


def make_gen(cn_active=False, seed=5):
    cfg = RunConfig.test(jurisdictions=("CN",) if cn_active else ("US",))
    rng = SeedTree(seed).generator("content", 0)
    return TemplateGenerator(cfg, rng), cfg


def personas(n=50, seed=5):
    rng = SeedTree(seed).generator("agents", 0)
    degrees = SeedTree(seed).generator("graph", 0).integers(1, 50, size=n)
    return Personas.sample(n, degrees=degrees, rng=rng)


def test_generator_produces_valid_items():
    gen, cfg = make_gen()
    p = personas()
    items = [gen.generate(author_id=i % p.n, personas=p, tick=3) for i in range(200)]
    for it in items:
        assert it.text
        assert 0 <= it.topic < cfg.n_topics
        assert -1 <= it.stance <= 1
        assert it.media_type in ("text", "image", "video")
        assert it.status == "visible"


def test_generator_seed_determinism():
    g1, _ = make_gen(seed=9)
    g2, _ = make_gen(seed=9)
    p = personas(seed=9)
    a = [g1.generate(i % p.n, p, tick=0).text for i in range(20)]
    b = [g2.generate(i % p.n, p, tick=0).text for i in range(20)]
    assert a == b


def test_cn_watermark_only_on_ai_generated():
    gen, _ = make_gen(cn_active=True)
    p = personas()
    items = [gen.generate(i % p.n, p, tick=0) for i in range(800)]
    ai = [it for it in items if it.ai_generated]
    organic = [it for it in items if not it.ai_generated]
    assert ai, "expected some AI-generated items at 8% base rate"
    # compliant AI items carry both explicit label and implicit watermark
    labelled = [it for it in ai if it.explicit_label]
    assert labelled
    for it in labelled:
        assert it.implicit_watermark is not None
        assert "provider" in it.implicit_watermark
        assert "content_ref" in it.implicit_watermark
    for it in organic:
        assert it.implicit_watermark is None and not it.explicit_label


def test_classifier_hits_precision_recall_targets():
    cfg = RunConfig.test()
    rng = SeedTree(3).generator("classifier", 0)
    clf = NoisyClassifier(cfg.classifier_targets, cfg.category_base_rates, rng)
    n = 40_000
    true_rng = SeedTree(4).generator("truth", 0)
    cat = "misinfo"
    base = cfg.category_base_rates[cat]
    truth = true_rng.random(n) < base
    flags = np.array([clf.classify_one({cat} if t else set())[cat] >= 0.5 for t in truth])
    cm = confusion(truth, flags)
    recall = cm["tp"] / max(cm["tp"] + cm["fn"], 1)
    precision = cm["tp"] / max(cm["tp"] + cm["fp"], 1)
    assert abs(recall - cfg.classifier_targets[cat]["recall"]) < 0.05
    assert abs(precision - cfg.classifier_targets[cat]["precision"]) < 0.07


class FixedBase:
    """A base generator that always returns the same topic/stance/text, so
    ClaudeAdapter's cache key (which is derived from the realized item, not
    just author/tick) is stable across repeated calls -- unlike the real
    TemplateGenerator, which redraws topic/stance from its RNG every call."""

    def __init__(self, topic=2, stance=0.1, text="template", explicit_label=False):
        self.topic = topic
        self.stance = stance
        self.text = text
        self.explicit_label = explicit_label

    def generate(self, author_id, personas, tick):
        return ContentItem(id=f"fixed-{author_id}-{tick}", author_id=author_id,
                           tick=tick, media_type="text", topic=self.topic,
                           stance=self.stance, text=self.text,
                           explicit_label=self.explicit_label)


def test_claude_adapter_cache_and_fallback(tmp_path):
    cache = tmp_path / "llm_cache.json"
    gen, cfg = make_gen()
    p = personas()
    degradations = []
    adapter = ClaudeAdapter(
        base=gen, cache_path=cache, api_key=None,
        on_degradation=lambda reason: degradations.append(reason),
    )
    # No key, empty cache -> fallback to template text, degradation recorded
    item = adapter.generate(author_id=1, personas=p, tick=0)
    assert item.text
    assert degradations
    # Inject cache and confirm cached text is used (no network ever)
    adapter_key = ClaudeAdapter(base=FixedBase(), cache_path=cache, api_key=None,
                                on_degradation=lambda r: None)
    key = adapter_key.prompt_key(author_id=2, personas=p, tick=0, topic=2, stance=0.1)
    cache.write_text(json.dumps({key: "cached post text"}), encoding="utf-8")
    adapter2 = ClaudeAdapter(base=FixedBase(), cache_path=cache, api_key=None,
                             on_degradation=lambda r: None)
    item2 = adapter2.generate(author_id=2, personas=p, tick=0)
    assert item2.text == "cached post text"


def test_claude_cache_key_includes_model_topic_and_tick(tmp_path):
    gen, _ = make_gen()
    p = personas()
    adapter = ClaudeAdapter(base=gen, cache_path=tmp_path / "llm_cache.json",
                            api_key=None, model="model-a")
    same = adapter.prompt_key(author_id=1, personas=p, tick=0, topic=2, stance=0.1)
    assert same == adapter.prompt_key(author_id=1, personas=p, tick=0, topic=2, stance=0.1)
    assert same != adapter.prompt_key(author_id=1, personas=p, tick=24, topic=2, stance=0.1)
    assert same != adapter.prompt_key(author_id=1, personas=p, tick=0, topic=3, stance=0.1)
    other_model = ClaudeAdapter(base=gen, cache_path=tmp_path / "llm_cache.json",
                                api_key=None, model="model-b")
    assert same != other_model.prompt_key(author_id=1, personas=p, tick=0,
                                          topic=2, stance=0.1)


def _claude_adapter_with_client(base, cache_path, transport_text, on_degradation=None):
    """Build a ClaudeAdapter whose remote call is stubbed with `transport_text`
    (a callable prompt -> str, or an exception to raise), bypassing the real
    anthropic SDK/network so these tests stay offline and deterministic."""
    adapter = ClaudeAdapter(base=base, cache_path=cache_path, api_key="test-key",
                            on_degradation=on_degradation or (lambda r: None))

    class _FakeContentBlock:
        def __init__(self, text):
            self.text = text

    class _FakeResponse:
        def __init__(self, text):
            self.content = [_FakeContentBlock(text)]

    class _FakeMessages:
        def create(self, model, max_tokens, messages):
            result = transport_text(messages[0]["content"])
            if isinstance(result, Exception):
                raise result
            return _FakeResponse(result)

    class _FakeClient:
        messages = _FakeMessages()

    adapter._client = _FakeClient()
    return adapter


def test_claude_blocked_result_not_served_from_cache_same_adapter(tmp_path):
    """Regression for the P0 cache-bypass bug in ClaudeAdapter specifically:
    its cache-hit path used to read `text` with no status check at all, so a
    second identical request would leak a previously blocked LLM response.

    Uses a FixedBase (constant topic/stance, like test_claude_adapter_cache_
    and_fallback above) rather than the real TemplateGenerator: ClaudeAdapter's
    cache key includes the realized topic/stance/tone from the base item, and
    a real generator redraws those on every call -- a repeat call is only
    guaranteed to hit the cache when the base item is identical both times."""
    p = personas()
    degradations = []
    calls = []

    def emailer(prompt):
        calls.append(prompt)
        return "local news email me at a@b.com"

    cache_path = tmp_path / "cache.json"
    adapter = _claude_adapter_with_client(
        FixedBase(), cache_path, emailer, degradations.append)

    first = adapter.generate(1, p, tick=0)
    assert "email me" not in first.text
    assert len(calls) == 1

    second = adapter.generate(1, p, tick=0)
    assert "email me" not in second.text
    assert len(calls) == 1, "must not re-contact the LLM for a cached blocked prompt"
    assert len(degradations) == 2
    assert all("semantic_mismatch" in d and "pii_like_output" in d for d in degradations)


def test_claude_blocked_result_not_served_from_cache_new_adapter_instance(tmp_path):
    """Same regression, but the cache is reloaded from disk by a fresh
    adapter instance -- the actually-reported scenario."""
    gen, cfg = make_gen()
    p = personas()
    cache_path = tmp_path / "cache.json"

    adapter1 = _claude_adapter_with_client(
        gen, cache_path, lambda prompt: "local news email me at a@b.com")
    first = adapter1.generate(1, p, tick=3)
    assert "email me" not in first.text

    def exploding(prompt):
        raise AssertionError("must not contact the LLM for a cached blocked prompt")

    degradations2 = []
    adapter2 = _claude_adapter_with_client(
        make_gen()[0], cache_path, exploding, degradations2.append)
    second = adapter2.generate(1, p, tick=3)
    assert "email me" not in second.text
    assert second.text == first.text
    assert degradations2 and "semantic_mismatch" in degradations2[0]
    assert "pii_like_output" in degradations2[0]


def test_claude_accepted_cache_entry_still_functions(tmp_path):
    gen, cfg = make_gen()
    p = personas()
    cache_path = tmp_path / "cache.json"
    adapter = _claude_adapter_with_client(
        gen, cache_path, lambda prompt: "totally fine accepted text")
    item1 = adapter.generate(1, p, tick=3)
    assert item1.text == "totally fine accepted text"
    cache = json.loads(cache_path.read_text())
    assert list(cache.values())[0]["status"] == "accepted"

    def exploding(prompt):
        raise AssertionError("must not call the LLM on an accepted cache hit")

    adapter2 = _claude_adapter_with_client(make_gen()[0], cache_path, exploding)
    item2 = adapter2.generate(1, p, tick=3)
    assert item2.text == "totally fine accepted text"


def test_claude_cn_explicit_label_preserved_for_blocked_output(tmp_path):
    gen, cfg = make_gen(cn_active=True)
    p = personas()
    cache_path = tmp_path / "cache.json"
    adapter = _claude_adapter_with_client(
        gen, cache_path, lambda prompt: "email me at a@b.com")
    labelled_blocked = None
    for i in range(600):
        item = adapter.generate(i % p.n, p, tick=0)
        if item.explicit_label:
            labelled_blocked = item
            break
    assert labelled_blocked is not None
    assert labelled_blocked.text.startswith("[AI-generated content] ")
    assert "email me" not in labelled_blocked.text


def test_claude_legacy_cache_entry_without_status_field_treated_as_accepted(tmp_path):
    gen, cfg = make_gen()
    p = personas()
    cache_path = tmp_path / "cache.json"
    adapter = _claude_adapter_with_client(
        gen, cache_path, lambda prompt: "legacy accepted text")
    adapter.generate(1, p, tick=3)
    cache = json.loads(cache_path.read_text())
    key = next(iter(cache))
    # Simulate a genuine pre-schema cache record (no status, no record_hash).
    del cache[key]["status"]
    del cache[key]["record_hash"]
    cache_path.write_text(json.dumps(cache))

    def exploding(prompt):
        raise AssertionError("must not call the LLM on a legacy cache hit")

    adapter2 = _claude_adapter_with_client(make_gen()[0], cache_path, exploding)
    item = adapter2.generate(1, p, tick=3)
    assert item.text == "legacy accepted text"


def test_claude_blocked_cache_replay_is_deterministic(tmp_path):
    gen, cfg = make_gen()
    p = personas()
    cache_path = tmp_path / "cache.json"
    adapter = _claude_adapter_with_client(
        gen, cache_path, lambda prompt: "email me at a@b.com")
    adapter.generate(1, p, tick=3)
    h1 = adapter.cache_hash()

    def exploding(prompt):
        raise AssertionError("must not contact the LLM for a cached blocked prompt")

    results = []
    for _ in range(2):
        fresh = _claude_adapter_with_client(make_gen()[0], cache_path, exploding)
        item = fresh.generate(1, p, tick=3)
        results.append(item.text)
        assert fresh.cache_hash() == h1
    assert results[0] == results[1]


def test_claude_tampered_cache_entry_is_discarded_and_not_served(tmp_path):
    """Regression for cache poisoning in ClaudeAdapter: a blocked entry with
    its status hand-edited to 'accepted' (hash left stale) must never be
    served -- the tamper must be detected and the prompt regenerated."""
    gen, cfg = make_gen()
    p = personas()
    cache_path = tmp_path / "cache.json"
    adapter = _claude_adapter_with_client(
        gen, cache_path, lambda prompt: "email me at a@b.com")
    adapter.generate(1, p, tick=3)
    cache = json.loads(cache_path.read_text())
    key = next(iter(cache))
    assert cache[key]["status"] == "blocked"
    cache[key]["status"] = "accepted"
    cache_path.write_text(json.dumps(cache))

    calls = []
    degradations = []

    def safe_text(prompt):
        calls.append(prompt)
        return "totally fine local news text"

    adapter2 = _claude_adapter_with_client(
        make_gen()[0], cache_path, safe_text, degradations.append)
    item = adapter2.generate(1, p, tick=3)
    assert len(calls) == 1, "a tampered entry must not be trusted -- must re-fetch"
    assert item.text == "totally fine local news text"
    assert "email me" not in item.text
    assert any("cache_tampered" in d for d in degradations)


def test_engine_runs_with_claude_mode_without_key(tmp_path, monkeypatch):
    from socio_sim.engine import Simulation
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = RunConfig.test(n_agents=50, n_ticks=6, content_mode="claude",
                         llm_cache_path=str(tmp_path / "claude_cache.json"),
                         out_dir=str(tmp_path))
    result = Simulation(cfg).run()
    assert result.log.by_kind("post")
    degradations = result.log.by_kind("degradation")
    assert degradations
    assert "template text used" in degradations[0]["data"]["reason"]
