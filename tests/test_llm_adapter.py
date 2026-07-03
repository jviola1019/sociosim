import json
from types import SimpleNamespace

import numpy as np
import pytest

from socio_sim.agents.personas import Personas
from socio_sim.config import RunConfig
from socio_sim.content.generate import TemplateGenerator
from socio_sim.content.llm_adapter import LLMAdapter
from socio_sim.content.semantic_guard import check_generated_text
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
    assert list(cache.values())[0]["text"] == "local model post text"

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


def test_semantic_guard_blocks_pii_like_output(tmp_path):
    gen, personas = setup()
    degradations = []
    adapter = LLMAdapter(
        base=gen, cache_path=tmp_path / "cache.json", backend="ollama",
        transport=lambda prompt: "local news email me at a@b.com",
        on_degradation=degradations.append)
    item = adapter.generate(1, personas, tick=3)
    assert "email me" not in item.text
    assert any("semantic_mismatch" in d and "pii_like_output" in d
               for d in degradations)
    cache = json.loads((tmp_path / "cache.json").read_text())
    assert list(cache.values())[0]["status"] == "blocked"


def test_semantic_guard_flags_category_topic_and_harmful_contradictions():
    item = SimpleNamespace(true_categories=set(), topic=3, stance=0.0)
    assert "category_contradiction:fraud" in check_generated_text(
        "claimprize freemoney", item)
    assert "category_contradiction:hate" in check_generated_text(
        "slurplaceholder grouptarget", item)
    assert "topic_contradiction" in check_generated_text(
        "stock earnings crypto rally", item)


def test_blocked_result_not_served_from_cache_same_adapter(tmp_path):
    """Regression for the P0 cache-bypass bug: a cached status=='blocked'
    entry must not leak the blocked LLM text on a later identical request
    from the same adapter, and must not trigger a second remote call."""
    gen, personas = setup()
    degradations = []
    calls = []

    def emailer(prompt):
        calls.append(prompt)
        return "local news email me at a@b.com"

    adapter = LLMAdapter(
        base=gen, cache_path=tmp_path / "cache.json", backend="ollama",
        transport=emailer, on_degradation=degradations.append)

    first = adapter.generate(1, personas, tick=3)
    assert "email me" not in first.text
    assert len(calls) == 1

    second = adapter.generate(1, personas, tick=3)
    assert "email me" not in second.text
    # NOTE: text content itself need not be byte-identical across calls --
    # self.base.generate() draws fresh template/slant randomness on every
    # invocation regardless of cache hit. What matters for this regression
    # is that the blocked LLM text never leaks and no second remote call
    # is made for the same cache key.
    assert len(calls) == 1, "must not re-contact the LLM for a cached blocked prompt"
    assert len(degradations) == 2
    assert all("semantic_mismatch" in d and "pii_like_output" in d
               for d in degradations)


def test_blocked_result_not_served_from_cache_new_adapter_instance(tmp_path):
    """Same regression as above, but the cache is reloaded from disk by a
    fresh adapter instance -- the actual reported scenario: a new run
    loading a persisted cache file must not serve a previously blocked
    response as if it were accepted."""
    gen, personas = setup()
    cache_path = tmp_path / "cache.json"

    adapter1 = LLMAdapter(base=gen, cache_path=cache_path, backend="ollama",
                          transport=lambda p: "local news email me at a@b.com")
    first = adapter1.generate(1, personas, tick=3)
    assert "email me" not in first.text

    def exploding(prompt):
        raise AssertionError("must not contact the LLM for a cached blocked prompt")

    degradations2 = []
    adapter2 = LLMAdapter(base=setup()[0], cache_path=cache_path, backend="ollama",
                          transport=exploding, on_degradation=degradations2.append)
    second = adapter2.generate(1, personas, tick=3)
    assert "email me" not in second.text
    assert second.text == first.text
    assert degradations2 and "semantic_mismatch" in degradations2[0]
    assert "pii_like_output" in degradations2[0]


def test_blocked_cache_replay_is_deterministic(tmp_path):
    """Two independent adapter instances loading the same persisted
    blocked-cache entry must produce bit-identical output and must not
    rewrite the cache file (cache_hash stays stable)."""
    gen, personas = setup()
    cache_path = tmp_path / "cache.json"
    adapter = LLMAdapter(base=gen, cache_path=cache_path, backend="ollama",
                         transport=lambda p: "email me at a@b.com")
    adapter.generate(1, personas, tick=3)
    h1 = adapter.cache_hash()

    def exploding(prompt):
        raise AssertionError("must not contact the LLM for a cached blocked prompt")

    results = []
    for _ in range(2):
        fresh_adapter = LLMAdapter(base=setup()[0], cache_path=cache_path,
                                   backend="ollama", transport=exploding)
        item = fresh_adapter.generate(1, personas, tick=3)
        results.append(item.text)
        assert fresh_adapter.cache_hash() == h1
    assert results[0] == results[1]


def test_accepted_cache_entries_still_function(tmp_path):
    gen, personas = setup()
    cache_path = tmp_path / "cache.json"
    adapter = LLMAdapter(base=gen, cache_path=cache_path, backend="ollama",
                         transport=lambda p: "totally fine accepted text")
    item1 = adapter.generate(1, personas, tick=3)
    assert item1.text == "totally fine accepted text"
    cache = json.loads(cache_path.read_text())
    assert list(cache.values())[0]["status"] == "accepted"

    def exploding(prompt):
        raise AssertionError("must not call transport on an accepted cache hit")

    adapter2 = LLMAdapter(base=setup()[0], cache_path=cache_path, backend="ollama",
                          transport=exploding)
    item2 = adapter2.generate(1, personas, tick=3)
    assert item2.text == "totally fine accepted text"


def test_cn_explicit_label_preserved_for_blocked_output(tmp_path):
    gen, personas = setup(cn=True)
    adapter = LLMAdapter(base=gen, cache_path=tmp_path / "c.json", backend="ollama",
                         transport=lambda p: "email me at a@b.com")
    labelled_blocked = None
    for i in range(600):
        item = adapter.generate(i % personas.n, personas, tick=0)
        if item.explicit_label:
            labelled_blocked = item
            break
    assert labelled_blocked is not None
    assert labelled_blocked.text.startswith("[AI-generated content] ")
    assert "email me" not in labelled_blocked.text


def test_legacy_cache_entry_without_status_field_triggers_rescreen(tmp_path):
    # E1 fix: status-less dict entries (pre-schema) must be re-screened,
    # not served as accepted hits. The transport IS called for re-generation.
    gen, personas = setup()
    cache_path = tmp_path / "cache.json"
    adapter = LLMAdapter(base=gen, cache_path=cache_path, backend="ollama",
                         transport=lambda p: "legacy accepted text")
    adapter.generate(1, personas, tick=3)
    cache = json.loads(cache_path.read_text())
    key = next(iter(cache))
    # Simulate a genuine pre-schema cache record: status and record_hash
    # didn't exist yet, so a real legacy record has neither field.
    del cache[key]["status"]
    del cache[key]["record_hash"]
    cache_path.write_text(json.dumps(cache))

    rescreened_calls = []

    def rescreening_transport(prompt):
        rescreened_calls.append(prompt)
        return "freshly screened text"

    adapter2 = LLMAdapter(base=setup()[0], cache_path=cache_path, backend="ollama",
                          transport=rescreening_transport)
    item = adapter2.generate(1, personas, tick=3)
    assert len(rescreened_calls) == 1, "legacy entry must trigger re-screen transport call"
    assert item.text == "freshly screened text"


def test_legacy_bare_string_cache_entry_triggers_rescreen(tmp_path):
    # E1 fix: legacy bare-string entries must be re-screened, not served as
    # accepted hits. The transport IS called for re-generation.
    gen, personas = setup()
    cache_path = tmp_path / "cache.json"
    adapter = LLMAdapter(base=gen, cache_path=cache_path, backend="ollama",
                         transport=lambda p: "ancient bare-string cached text")
    adapter.generate(1, personas, tick=3)
    cache = json.loads(cache_path.read_text())
    key = next(iter(cache))
    cache_path.write_text(json.dumps({key: "ancient bare-string cached text"}))

    rescreened_calls = []

    def rescreening_transport(prompt):
        rescreened_calls.append(prompt)
        return "freshly screened replacement"

    adapter2 = LLMAdapter(base=setup()[0], cache_path=cache_path, backend="ollama",
                          transport=rescreening_transport)
    item = adapter2.generate(1, personas, tick=3)
    assert len(rescreened_calls) == 1, "legacy bare-string entry must trigger re-screen transport call"
    assert item.text == "freshly screened replacement"


def test_blocked_cache_invalidated_by_deliberate_guard_version_bump(tmp_path, monkeypatch):
    gen, personas = setup()
    cache_path = tmp_path / "cache.json"
    adapter = LLMAdapter(base=gen, cache_path=cache_path, backend="ollama",
                         transport=lambda p: "email me at a@b.com")
    adapter.generate(1, personas, tick=3)
    cache = json.loads(cache_path.read_text())
    assert list(cache.values())[0]["status"] == "blocked"

    from socio_sim.content import llm_cache
    monkeypatch.setattr(llm_cache, "BLOCKED_GUARD_VERSION", 2)

    calls = []

    def safe_text(prompt):
        calls.append(prompt)
        return "totally fine local news text"

    adapter2 = LLMAdapter(base=setup()[0], cache_path=cache_path, backend="ollama",
                          transport=safe_text)
    item = adapter2.generate(1, personas, tick=3)
    assert len(calls) == 1, "a guard-version bump must force re-evaluation"
    assert item.text == "totally fine local news text"


def test_tampered_cache_entry_is_discarded_and_not_served(tmp_path):
    """Regression for cache poisoning: an entry that was blocked, then had
    its status hand-edited to 'accepted' without recomputing record_hash,
    must never be served -- the tamper must be detected and the prompt
    regenerated from a fresh, re-screened call rather than trusted."""
    gen, personas = setup()
    cache_path = tmp_path / "cache.json"
    adapter = LLMAdapter(base=gen, cache_path=cache_path, backend="ollama",
                         transport=lambda p: "email me at a@b.com")
    adapter.generate(1, personas, tick=3)
    cache = json.loads(cache_path.read_text())
    key = next(iter(cache))
    assert cache[key]["status"] == "blocked"
    cache[key]["status"] = "accepted"  # forged after the fact, hash untouched
    cache_path.write_text(json.dumps(cache))

    calls = []
    degradations = []

    def safe_text(prompt):
        calls.append(prompt)
        return "totally fine local news text"

    adapter2 = LLMAdapter(base=setup()[0], cache_path=cache_path, backend="ollama",
                          transport=safe_text, on_degradation=degradations.append)
    item = adapter2.generate(1, personas, tick=3)
    assert len(calls) == 1, "a tampered entry must not be trusted -- must re-fetch"
    assert item.text == "totally fine local news text"
    assert "email me" not in item.text
    assert any("cache_tampered" in d for d in degradations)


def test_tampered_cache_text_swap_is_discarded_and_not_served(tmp_path):
    """A different tamper shape: text swapped on an accepted entry without
    recomputing record_hash. Must not be served verbatim."""
    gen, personas = setup()
    cache_path = tmp_path / "cache.json"
    adapter = LLMAdapter(base=gen, cache_path=cache_path, backend="ollama",
                         transport=lambda p: "totally fine accepted text")
    adapter.generate(1, personas, tick=3)
    cache = json.loads(cache_path.read_text())
    key = next(iter(cache))
    cache[key]["text"] = "swapped-in text the guard never screened"
    cache_path.write_text(json.dumps(cache))

    calls = []

    def safe_text(prompt):
        calls.append(prompt)
        return "regenerated safe text"

    adapter2 = LLMAdapter(base=setup()[0], cache_path=cache_path, backend="ollama",
                          transport=safe_text)
    item = adapter2.generate(1, personas, tick=3)
    assert len(calls) == 1
    assert item.text == "regenerated safe text"
    assert "swapped-in" not in item.text


def test_corrupt_cache_file_is_treated_as_empty_not_a_crash(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{not valid json at all", encoding="utf-8")
    gen, person