"""Unit tests for the shared LLM response-cache trust logic
(socio_sim/content/llm_cache.py), used by both LLMAdapter and ClaudeAdapter.

These exercise `resolve()` directly against synthetic cache entries so the
contract is pinned independent of either adapter's own generation logic.
"""

from socio_sim.content import llm_cache


def test_missing_entry_is_a_plain_miss():
    lookup = llm_cache.resolve(None)
    assert lookup.hit is False
    assert lookup.text is None
    assert lookup.degradation is None


def test_legacy_bare_string_entry_is_trusted_accepted_hit():
    lookup = llm_cache.resolve("ancient cached text")
    assert lookup.hit is True
    assert lookup.text == "ancient cached text"
    assert lookup.degradation is None


def test_legacy_dict_without_status_is_trusted_accepted_hit():
    entry = {"text": "pre-status cached text"}
    lookup = llm_cache.resolve(entry)
    assert lookup.hit is True
    assert lookup.text == "pre-status cached text"
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


def test_file_hash_none_when_missing_and_stable_when_present(tmp_path):
    path = tmp_path / "cache.json"
    assert llm_cache.file_hash(path) is None
    llm_cache.save(path, {"k": "v"})
    h1 = llm_cache.file_hash(path)
    assert h1 == llm_cache.file_hash(path)
    llm_cache.save(path, {"k": "v2"})
    assert llm_cache.file_hash(path) != h1
