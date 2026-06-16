import json

import numpy as np

from socio_sim.agents.personas import Personas
from socio_sim.config import RunConfig
from socio_sim.content.claude_adapter import ClaudeAdapter
from socio_sim.content.classify import NoisyClassifier, confusion
from socio_sim.content.generate import TemplateGenerator
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
    key = adapter.prompt_key(author_id=2, personas=p, tick=0)
    cache.write_text(json.dumps({key: "cached post text"}), encoding="utf-8")
    adapter2 = ClaudeAdapter(base=gen, cache_path=cache, api_key=None,
                             on_degradation=lambda r: None)
    item2 = adapter2.generate(author_id=2, personas=p, tick=0)
    assert item2.text == "cached post text"
