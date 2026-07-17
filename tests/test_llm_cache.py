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
    # No stray temp files accumulate next to the cache (the advisory
    # .lock sidecar is expected and is not a partial write).
    leftovers = [p.name for p in tmp_path.iterdir()
                 if p.name not in ("cache.json", "cache.json.lock")]
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


def test_update_two_writers_different_keys_both_survive(tmp_path):
    """The read-modify-write race save() could not solve: update() reloads
    the latest cache under an advisory lock, so concurrent writers adding
    DIFFERENT keys never lose each other's entries."""
    import threading
    path = tmp_path / "cache.json"
    n_per_writer = 25

    def writer(prefix):
        for i in range(n_per_writer):
            llm_cache.update(path, f"{prefix}{i}",
                             llm_cache.make_entry(f"{prefix} text {i}",
                                                  "accepted", []))

    threads = [threading.Thread(target=writer, args=(p,)) for p in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    loaded = llm_cache.load(path)
    assert len(loaded) == 2 * n_per_writer
    assert all(llm_cache.resolve(v).hit for v in loaded.values())


def test_update_same_key_first_writer_wins(tmp_path):
    """Documented deterministic same-key policy: the first trusted entry on
    disk is authoritative; a later writer's candidate is discarded and the
    caller receives (and must adopt) the winner."""
    path = tmp_path / "cache.json"
    first = llm_cache.make_entry("first screened text", "accepted", [])
    second = llm_cache.make_entry("second candidate text", "accepted", [])
    llm_cache.update(path, "k", first)
    merged = llm_cache.update(path, "k", second)
    assert merged["k"] == first
    assert llm_cache.load(path)["k"] == first
    # ...but an UNTRUSTED existing entry (e.g. tampered) is replaced.
    bad = dict(first)
    bad["text"] = "tampered"
    llm_cache.save(path, {"k": bad})
    merged = llm_cache.update(path, "k", second)
    assert merged["k"] == second


def test_update_failed_replace_leaves_old_cache_and_releases_lock(tmp_path, monkeypatch):
    path = tmp_path / "cache.json"
    original = llm_cache.make_entry("original", "accepted", [])
    llm_cache.update(path, "k", original)

    def exploding_replace(src, dst):
        raise OSError("simulated crash")

    monkeypatch.setattr(llm_cache.os, "replace", exploding_replace)
    with pytest.raises(OSError):
        llm_cache.update(path, "k2", llm_cache.make_entry("new", "accepted", []))
    monkeypatch.undo()
    assert llm_cache.load(path) == {"k": original}
    # The lock must have been released: a follow-up update succeeds.
    llm_cache.update(path, "k3", llm_cache.make_entry("later", "accepted", []))
    assert set(llm_cache.load(path)) == {"k", "k3"}


def test_update_reports_dir_fsync_failure_without_claiming_durability(tmp_path, monkeypatch):
    """A failed directory fsync must be REPORTED (durability across power
    loss not guaranteed), not silently swallowed and not fatal -- the
    rename itself already happened atomically."""
    path = tmp_path / "cache.json"
    notices = []

    def failing_dir_fsync(directory, on_error=None):
        if on_error is not None:
            on_error("cache directory fsync failed (simulated); the write "
                     "is atomic but durability across power loss is not "
                     "guaranteed")

    monkeypatch.setattr(llm_cache, "_dir_fsync", failing_dir_fsync)
    llm_cache.update(path, "k", llm_cache.make_entry("t", "accepted", []),
                     on_error=notices.append)
    assert llm_cache.load(path)["k"]["text"] == "t"
    assert any("durability" in n for n in notices)


def test_update_multiprocess_no_lost_entries(tmp_path):
    """Two real OS processes (not threads) racing on the same cache file:
    every key from both writers must survive with valid schema entries."""
    import subprocess
    import sys
    path = tmp_path / "cache.json"
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from socio_sim.content import llm_cache\n"
        "prefix, path = sys.argv[1], Path(sys.argv[2])\n"
        "for i in range(20):\n"
        "    llm_cache.update(path, f'{prefix}{i}',\n"
        "                     llm_cache.make_entry(f'{prefix} {i}', 'accepted', []))\n"
    )
    procs = [subprocess.Popen([sys.executable, "-c", script, prefix, str(path)])
             for prefix in ("p", "q")]
    for p in procs:
        assert p.wait(timeout=120) == 0
    loaded = llm_cache.load(path)
    assert len(loaded) == 40, sorted(loaded)
    assert all(llm_cache.resolve(v).hit for v in loaded.values())


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


def test_accepted_winner_replays_byte_identically_after_losing_update(tmp_path):
    """First-writer-wins must leave the on-disk cache BYTE-identical when a
    later candidate loses: the winner is what every future same-seed run
    replays, so even a no-op rewrite must not change the bytes."""
    path = tmp_path / "cache.json"
    llm_cache.update(path, "k", llm_cache.make_entry("winner text", "accepted", []))
    h1 = llm_cache.file_hash(path)
    llm_cache.update(path, "k", llm_cache.make_entry("loser text", "accepted", []))
    assert llm_cache.file_hash(path) == h1, "losing update must not change bytes"
    lookup = llm_cache.resolve(llm_cache.load(path)["k"])
    assert lookup.hit and lookup.text == "winner text"


def test_lock_sidecar_holds_no_cache_content_or_secrets(tmp_path):
    """The advisory .lock sidecar is a pure coordination file: it must never
    receive cache payload (a world-readable lock file must not leak text)."""
    path = tmp_path / "cache.json"
    secret = "SECRET-PAYLOAD-hunter2-do-not-leak"
    llm_cache.update(path, "k", llm_cache.make_entry(secret, "accepted", []))
    lock = tmp_path / "cache.json.lock"
    assert lock.exists()
    data = lock.read_bytes()
    assert secret.encode() not in data
    assert data == b"", "lock sidecar must stay empty (no payload, no secrets)"


def test_windows_msvcrt_lock_blocks_a_second_process(tmp_path):
    """Platform-specific coverage for the win32 locking path (msvcrt).

    Documented CI gap: GitHub CI runs ubuntu-latest, so this test is
    exercised only on Windows development machines; the POSIX flock path is
    what CI covers (test_update_multiprocess_no_lost_entries runs on both).

    A child process takes the advisory lock and holds it; update() in this
    process must block until the child releases, then complete correctly.
    """
    import subprocess
    import sys
    import time as _time
    if sys.platform != "win32":
        import pytest as _pytest
        _pytest.skip("win32-only: exercises the msvcrt.locking path")
    path = tmp_path / "cache.json"
    marker = tmp_path / "holding"
    hold_s = 1.5
    script = (
        "import sys, time\n"
        "from pathlib import Path\n"
        "from socio_sim.content import llm_cache\n"
        "path, marker, hold = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])\n"
        "with llm_cache._FileLock(path):\n"
        "    marker.write_text('held')\n"
        "    time.sleep(hold)\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(path), str(marker), str(hold_s)])
    try:
        deadline = _time.time() + 30
        while not marker.exists():
            assert _time.time() < deadline, "child never acquired the lock"
            _time.sleep(0.02)
        t0 = _time.time()
        llm_cache.update(path, "k", llm_cache.make_entry("t", "accepted", []))
        waited = _time.time() - t0
    finally:
        assert child.wait(timeout=60) == 0
    assert waited >= 0.3, (
        f"update() returned after {waited:.2f}s while the child held the "
        "lock for ~1.5s: the msvcrt lock did not actually block")
    assert llm_cache.load(path)["k"]["text"] == "t"


def test_file_hash_none_when_missing_and_stable_when_present(tmp_path):
    path = tmp_path / "cache.json"
    assert llm_cache.file_hash(path) is None
    llm_cache.save(path, {"k": "v"})
    h1 = llm_cache.file_hash(path)
    assert h1 == llm_cache.file_hash(path)
    llm_cache.save(path, {"k": "v2"})
    assert llm_cache.file_hash(path) != h1
