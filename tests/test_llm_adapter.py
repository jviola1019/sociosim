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
