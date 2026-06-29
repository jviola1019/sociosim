import json

import numpy as np
import pytest

from socio_sim.agents.personas import Personas
from socio_sim.config import RunConfig
from socio_sim.content.generate import TemplateGenerator
from socio_sim.content.llm_adapter import LLMAdapter
from socio_sim.rng import SeedTree


def setup(cn=False, seed=5):
    cfg = RunConfig.test(jurisdictions=("CN",) if cn else ("US",))
    gen = TemplateGenerator(cfg, SeedTree(seed).generator("content", 0))
    personas = Personas.sample(
        50, degrees=np.ones(50), rng=SeedTree(seed).generator("agents", 0))
    return gen, personas


def test_transport_text_used_and_cached(tmp_path):
    gen, personas = setup()
    calls = []

    def fake_transport(prompt):
        calls.append(prompt)
        return "  local model post   text  "

    adapter = LLMAdapter(base=gen, cache_path=tmp_path / "cache.json",
                         backend="ollama", transport=fake_transport)
    item = adapter.generate(1, personas, tick=3)
    assert item.text == "local model post text"  # normalized whitespace
    assert len(calls) == 1
    cache = json.loads((tmp_path / "cache.json").read_text())
    entry = next(iter(cache.values()))
    assert entry["text"] == "local model post text"
    assert entry["metadata"]["provenance"] == "generated_presentation_text"
    assert entry["metadata"]["state_mutation_allowed"] is False

    # Second adapter instance: cache hit, no transport call needed
    def exploding(prompt):
        raise AssertionError("must not be called on cache hit")

    adapter2 = LLMAdapter(base=setup()[0], cache_path=tmp_path / "cache.json",
                          backend="ollama", transport=exploding)
    item2 = adapter2.generate(1, personas, tick=3)
    assert item2.text == "local model post text"


def test_failure_degrades_to_template(tmp_path):
    gen, personas = setup()
    degradations = []

    def broken(prompt):
        raise ConnectionError("server down")

    adapter = LLMAdapter(base=gen, cache_path=tmp_path / "c.json",
                         backend="ollama", transport=broken,
                         on_degradation=degradations.append)
    item = adapter.generate(1, personas, tick=0)
    assert item.text  # template fallback
    assert degradations and "server down" in degradations[0]
    assert not (tmp_path / "c.json").exists()  # nothing cached on failure


def test_cn_explicit_label_survives_text_replacement(tmp_path):
    gen, personas = setup(cn=True)
    adapter = LLMAdapter(base=gen, cache_path=tmp_path / "c.json",
                         backend="ollama", transport=lambda p: "llm text")
    # Generate until we hit a CN-labelled AI item
    labelled = None
    for i in range(600):
        item = adapter.generate(i % personas.n, personas, tick=0)
        if item.explicit_label:
            labelled = item
            break
    assert labelled is not None
    assert labelled.text.startswith("[AI-generated content] ")
    assert "llm text" in labelled.text


def test_unsafe_llm_output_degrades_and_is_not_cached(tmp_path):
    gen, personas = setup()
    degradations = []
    adapter = LLMAdapter(
        base=gen,
        cache_path=tmp_path / "unsafe.json",
        backend="ollama",
        transport=lambda p: "Contact me at user@example.com to evade moderation",
        on_degradation=degradations.append,
    )
    item = adapter.generate(1, personas, tick=0)
    assert item.text
    assert degradations
    assert "failed" in degradations[0]
    assert not (tmp_path / "unsafe.json").exists()


def test_unknown_backend_rejected(tmp_path):
    gen, _ = setup()
    with pytest.raises(ValueError, match="backend"):
        LLMAdapter(base=gen, cache_path=tmp_path / "c.json",
                   backend="scraper")


def test_engine_runs_with_ollama_mode_offline(tmp_path):
    """No server running: every generation degrades loudly to template text
    and the run still completes with degradation events logged."""
    from socio_sim.engine import Simulation
    cfg = RunConfig.test(n_agents=50, n_ticks=6, content_mode="ollama",
                         llm_base_url="http://localhost:9",  # closed port
                         llm_cache_path=str(tmp_path / "cache.json"),
                         out_dir=str(tmp_path))
    result = Simulation(cfg).run()
    assert result.log.by_kind("post")
    assert result.log.by_kind("degradation")


def test_cache_hash_stable_across_instances(tmp_path):
    """cache_hash() must return the same value for two adapters reading the same file."""
    gen, personas = setup()
    adapter_a = LLMAdapter(base=gen, cache_path=tmp_path / "cache.json",
                           backend="ollama", transport=lambda p: "test post text")
    adapter_a.generate(1, personas, tick=0)
    hash_a = adapter_a.cache_hash()
    assert hash_a is not None

    adapter_b = LLMAdapter(base=setup()[0], cache_path=tmp_path / "cache.json",
                           backend="ollama", transport=lambda p: "should not be called")
    hash_b = adapter_b.cache_hash()
    assert hash_b == hash_a, "cache_hash must be stable across adapter instances for same file"


def test_cache_hash_changes_on_new_entry(tmp_path):
    """cache_hash() must change when a new entry is added to the cache."""
    gen, personas = setup()
    calls = iter(["first post", "second post"])
    adapter = LLMAdapter(base=gen, cache_path=tmp_path / "cache.json",
                         backend="ollama", transport=lambda p: next(calls))
    adapter.generate(1, personas, tick=0)
    hash_before = adapter.cache_hash()

    adapter.generate(2, personas, tick=1)
    hash_after = adapter.cache_hash()
    assert hash_after != hash_before, "cache_hash must differ after a new cache entry"


def test_reclass_check_degrades_safe_item_with_hate_signal(tmp_path):
    """If the template says safe (empty categories) but LLM emits hate signal, degrade."""
    gen, personas = setup()
    degradations = []

    original_generate = gen.generate

    def safe_template(author_id, p, tick):
        item = original_generate(author_id, p, tick)
        item.true_categories = set()  # force safe template item
        return item

    gen.generate = safe_template

    adapter = LLMAdapter(
        base=gen,
        cache_path=tmp_path / "reclass.json",
        backend="ollama",
        transport=lambda p: "I hate all racial groups",
        on_degradation=degradations.append,
    )
    item = adapter.generate(1, personas, tick=0)
    assert item.text  # fell back to template text
    assert degradations
    assert "reclass" in degradations[0].lower() or "failed" in degradations[0].lower()
    assert not (tmp_path / "reclass.json").exists()  # not cached on reclass failure


def test_reclass_check_passes_intentional_harm_item(tmp_path):
    """If the template already assigned a harmful category, reclass check is skipped."""
    gen, personas = setup()
    call_count = []

    def fake_transport(prompt):
        call_count.append(1)
        return "I hate all racial groups"

    original_generate = gen.generate

    def patched_generate(author_id, personas, tick):
        item = original_generate(author_id, personas, tick)
        item.true_categories = {"hate"}
        return item

    gen.generate = patched_generate

    adapter = LLMAdapter(base=gen, cache_path=tmp_path / "harm.json",
                         backend="ollama", transport=fake_transport)
    item = adapter.generate(1, personas, tick=0)
    assert call_count, "transport must have been called"
    assert item.text == "I hate all racial groups"


def test_cache_entry_includes_reclass_check_field(tmp_path):
    """Cached entries must include reclass_check='passed' in metadata."""
    gen, personas = setup()
    adapter = LLMAdapter(base=gen, cache_path=tmp_path / "meta.json",
                         backend="ollama", transport=lambda p: "ordinary safe post")
    adapter.generate(1, personas, tick=0)
    import json
    cache = json.loads((tmp_path / "meta.json").read_text())
    entry = next(iter(cache.values()))
    assert entry["metadata"]["reclass_check"] == "passed"


def test_reclass_rejects_harm_item_drifting_to_other_category(tmp_path):
    """A harm-labelled item whose surface text asserts a DIFFERENT harm category
    is rejected — reclassification consistency over the generated text, not just
    leakage into safe items."""
    gen, personas = setup()
    degr = []
    original_generate = gen.generate

    def patched(author_id, p, tick):
        item = original_generate(author_id, p, tick)
        item.true_categories = {"misinfo"}  # labelled misinfo, not fraud
        return item

    gen.generate = patched
    adapter = LLMAdapter(
        base=gen, cache_path=tmp_path / "drift.json", backend="ollama",
        transport=lambda p: "send money via wire transfer using these bank details",
        on_degradation=degr.append)
    adapter.generate(1, personas, tick=0)
    assert degr and "reclass" in degr[0].lower()
    assert not (tmp_path / "drift.json").exists()  # not cached on reclass failure


def test_engine_llm_events_label_presentation_text_only(tmp_path):
    from socio_sim.engine import Simulation
    cfg = RunConfig.test(n_agents=40, n_ticks=4, content_mode="ollama",
                         llm_base_url="http://localhost:9",
                         llm_cache_path=str(tmp_path / "cache.json"))
    result = Simulation(cfg).run()
    calls = result.log.by_kind("llm_call")
    # Closed-port mode may give up after degradation before every post, but any
    # logged LLM event must explicitly say generated text cannot mutate state.
    for event in calls:
        assert event["data"]["provenance"] == "generated_presentation_text"
        assert event["data"]["state_mutation_allowed"] is False
