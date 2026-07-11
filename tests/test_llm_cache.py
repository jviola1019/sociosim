"""Unit tests for the shared LLM response-cache trust logic
(socio_sim/content/llm_cache.py), used by both LLMAdapter and ClaudeAdapter.

These exercise `resolve()` directly against synthetic cache entries so the
contract is pinned independent of either adapter's own generation logic.
"""

import pytest

from socio_sim.content import llm_cache


def test_missing_entry_is_a_plain_miss():
    lookup = llm_cache.resolve(None)
    assert lookup.hit is False
    assert lookup.text is None
    assert lookup.degradation is None


def test_legacy_bare_string_entry_triggers_rescreen():
    # E1 fix: legacy bare-string entries predate the guard schema and must
    # be re-screened, not served as unconditional accepted hits.
    lookup = llm_cache.resolve("ancient cached text")
    assert lookup.hit is False
    assert lookup.text is None
    assert lookup.degradation is None


def test_legacy_dict_without_status_triggers_rescreen():
    # E1 fix: status-less dict entries predate the guard schema and must
    # be re-screened, not served as unconditional accepted hits.
    entry = {"text": "pre-status cached text"}
    lookup = llm_cache.resolve(entry)
    assert lookup.hit is False
    assert lookup.text is None
    assert lookup.degradation is None


def test_accepted_entry_from_make_entry_is_a_hit():
    entry = llm_cache.make_entry("safe text", "accepted", [])
    lookup = llm_cache.resolve(entry)
    assert lookup.hit is True
    assert lookup.text == "safe text"
    assert lookup.degradation is None


def test_blocked_entry_matching_guard_version_is_hit_with_no_text():
    entry = llm_cache.make_entry(
        "bad text", "blocked", ["pii_like_output"],
        guard_version=llm_cache.BLOCKED_GUARD_VERSION)
    lookup = llm_cache.resolve(entry)
    assert lookup.hit is True
    assert lookup.text is None  # caller must use template, never this text
    assert "semantic_mismatch" in lookup.degradation
    assert "pii_like_output" in lookup.degradation


def test_blocked_entry_with_stale_guard_version_is_a_miss():
    entry = llm_cache.make_entry(
        "bad text", "blocked", ["pii_like_output"], guard_version=0)
    lookup = llm_cache.resolve(entry)
    assert lookup.hit is False
    assert lookup.text is None


def test_tampered_record_hash_is_discarded_as_a_miss():
    """The exact attack the P0 spec calls out: hand-edit a persisted cache
    file. Here a blocked entry's status is flipped to 'accepted' without
    recomputing record_hash -- the mismatch must be caught, not served."""
    entry = llm_cache.make_entry(
        "blocked bad text", "blocked", ["pii_like_output"],
        guard_version=llm_cache.BLOCKED_GUARD_VERSION)
    tampered = dict(entry)
    tampered["status"] = "accepted"  # forged after the fact
    lookup = llm_cache.resolve(tampered)
    assert lookup.hit is False
    assert lookup.text is None
    assert "cache_tampered" in lookup.degradation


def test_tampered_text_is_discarded_as_a_miss():
    entry = llm_cache.make_entry("original safe text", "accepted", [])
    tampered = dict(entry)
    tampered["text"] = "swapped-in text the guard never screened"
    lookup = llm_cache.resolve(tampered)
    assert lookup.hit is False
    assert lookup.text is None
    assert "cache_tampered" in lookup.degradation


def test_unknown_status_value_is_discarded_as_a_miss():
    entry = {"text": "whatever", "status": "definitely_fine_trust_me",
              "reason_codes": []}
    lookup = llm_cache.resolve(entry)
    assert lookup.hit is False
    assert lookup.text is None
    assert "cache_tampered" in lookup.degradation


def test_e01_make_entry_stamps_guard_version_on_accepted():
    # E-01: accepted entries must record which guard screened them, so a
    # guard-version bump re-screens accepted text too, not just blocked.
    entry = llm_cache.make_entry("safe text", "accepted", [])
    assert entry["guard_version"] == llm_cache.BLOCKED_GUARD_VERSION


def test_e01_accepted_entry_with_stale_guard_version_is_a_miss(monkeypatch):
    entry = llm_cache.make_entry("safe text", "accepted", [])
    monkeypatch.setattr(llm_cache, "BLOCKED_GUARD_VERSION", 2)
    lookup = llm_cache.resolve(entry)
    assert lookup.hit is False
    assert lookup.text is None
    assert lookup.degradation is None  # deliberate invalidation, not tampering


def test_e01_accepted_entry_without_guard_version_is_a_clean_miss():
    # An accepted entry written before guard_version stamping existed was
    # screened under an unknown guard: re-screen it, but do NOT report it
    # as tampered -- its record_hash (old formula, no guard_version) is valid.
    entry = {"text": "old accepted text", "status": "accepted",
             "reason_codes": [],
             "record_hash": llm_cache.record_hash(
                 "old accepted text", "accepted", [])}
    lookup = llm_cache.resolve(entry)
    assert lookup.hit is False
    assert lookup.text is None
    assert lookup.degradation is None


def test_e03_guard_version_edit_is_detected_as_tampering():
    # E-03: guard_version is inside the record_hash envelope -- silently
    # editing it (to dodge a re-screen) must read as tampering.
    entry = llm_cache.make_entry("safe text", "accepted", [])
    tampered = dict(entry)
    tampered["guard_version"] = 999
    lookup = llm_cache.resolve(tampered)
    assert lookup.hit is False
    assert lookup.text is None
    assert "cache_tampered" in lookup.degradation


def test_e03_dead_semantic_hash_field_no_longer_written():
    # E-03: semantic_hash was written but never verified anywhere -- a dead
    # integrity field giving false assurance. record_hash already binds the
    # text; the redundant field is gone.
    entry = llm_cache.make_entry("t", "accepted", [])
    assert "semantic_hash" not in entry


def test_e02_docstring_matches_safe_legacy_behavior():
    # E-02: the module docstring is the authoritative trust-model statement;
    # it must not claim legacy entries are "trusted as accepted" when the
    # code (correctly) re-screens them. A doc-faithful "fix" of resolve()
    # would reintroduce the original P0 cache bypass.
    assert "trusted as accepted" not in llm_cache.__doc__
    assert "miss" in llm_cache.__doc__.lower()


def test_record_hash_changes_with_any_field():
    a = llm_cache.record_hash("t", "accepted", [])
    assert a != llm_cache.record_hash("different", "accepted", [])
    assert a != llm_cache.record_hash("t", "blocked", [])
    assert a != llm_cache.record_hash("t", "accepted", ["x"])


def test_load_missing_file_returns_empty_dict(tmp_path):
    assert llm_cache.load(tmp_path / "nope.json") == {}


def test_load_corrupt_json_returns_empty_dict_and_reports(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("{not valid json", encoding="utf-8")
    errors = []
    result = llm_cache.load(path, on_error=errors.append)
    assert result == {}
    assert errors and "corrupt" in errors[0]


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "sub" / "cache.json"
    entry = llm_cache.make_entry("hi", "accepted", [])
    llm_cache.save(path, {"k": entry})
    assert llm_cache.load(path) == {"k": entry}


def test_save_is_atomic_a_failed_replace_leaves_old_cache_intact(tmp_path, monkeypatch):
    """Atomic persistence: save() must write a temp file and os.replace()
    it over the target, so a crash mid-save can never leave a truncated/
    corrupt cache -- the previous complete cache survives."""
    path = tmp_path / "cache.json"
    original = {"k": llm_cache.make_entry("original", "accepted", [])}
    llm_cache.save(path, original)

    def exploding_replace(src, dst):
        raise OSError("simulated crash between temp write and rename")

    monkeypatch.setattr(llm_cache.os, "replace", exploding_replace)
    with pytest.raises(OSError):
        llm_cache.save(path, {"k": llm_cache.make_entry("new", "accepted", [])})
    monkeypatch.undo()
    # The original cache file is untouched and still fully valid JSON.
    assert llm_cache.load(path) == original
    # No stray temp files accumulate next to the cache.
    leftovers = [p for p in tmp_path.iterdir() if p.name != "cache.json"]
    assert leftovers == [], leftovers


def test_concurrent_saves_never_produce_invalid_json(tmp_path):
    """Two racing writers may lose one update (last rename wins) but must
    never interleave bytes: the file is always one writer's complete JSON."""
    import threading
    path = tmp_path / "cache.json"
    payloads = [
        {f"k{i}": llm_cache.make_entry(f"text {i} " * 200, "accepted", [])}
        for i in range(2)
    ]

    def writer(payload):
        for _ in range(30):
            llm_cache.save(path, payload)

    threads = [threading.Thread(target=writer, args=(p,)) for p in payloads]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    loaded = llm_cache.load(path)
    assert loaded in payloads  # complete content from exactly one writer


def test_blocked_and_accepted_entries_survive_reload_with_same_meaning(tmp_path):
    path = tmp_path / "cache.json"
    cache = {
        "b": llm_cache.make_entry("bad text", "blocked", ["pii_like_output"],
                                  guard_version=llm_cache.BLOCKED_GUARD_VERSION),
        "a": llm_cache.make_entry("good text", "accepted", []),
    }
    llm_cache.save(path, cache)
    reloaded = llm_cache.load(path)
    blocked = llm_cache.resolve(reloaded["b"])
    assert blocked.hit is True and blocked.text is None
    accepted = llm_cache.resolve(reloaded["a"])
    assert accepted.hit is True and accepted.text == "good text"


def test_file_hash_none_when_missing_and_stable_when_present(tmp_path):
    path = tmp_path / "cache.json"
    assert llm_cache.file_hash(path) is None
    llm_cache.save(path, {"k": "v"})
    h1 = llm_cache.file_hash(path)
    assert h1 == llm_cache.file_hash(path)
    llm_cache.save(path, {"k": "v2"})
    assert llm_cache.file_hash(path) != h1
