"""Local data lifecycle (Phase 6): retention, integrity, export, health."""

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from socio_sim import ops
from socio_sim.web import app


def _make_run(out: str, name: str, age_days: float = 0.0):
    d = out / name
    d.mkdir(parents=True)
    (d / "manifest.json").write_text('{"config_hash": "abc"}', encoding="utf-8")
    (d / "events.jsonl").write_text('{"tick": 0}\n', encoding="utf-8")
    if age_days:
        old = time.time() - age_days * 86400
        for f in d.iterdir():
            import os
            os.utime(f, (old, old))
    return d


def test_scan_runs_finds_run_dirs_newest_first(tmp_path):
    _make_run(tmp_path, "old", age_days=10)
    _make_run(tmp_path, "new")
    runs = ops.scan_runs(tmp_path)
    assert [r.path.name for r in runs] == ["new", "old"]
    assert runs[1].age_days > 9
    assert all(r.bytes > 0 for r in runs)


def test_scan_never_nominates_the_out_root_or_nested_runs(tmp_path):
    """Regression for a real footgun found in a live tree: `run.py --out out`
    leaves a manifest.json at the out/ ROOT, so a naive scan nominated the
    entire out/ tree -- run-history database included -- for deletion."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "manifest.json").write_text("{}", encoding="utf-8")   # stray root manifest
    (out / "sociosim.db").write_bytes(b"precious")
    _make_run(out, "real-run")
    _make_run(out / "real-run", "nested")      # a run inside a run

    runs = ops.scan_runs(out)
    names = {r.path.name for r in runs}
    assert names == {"real-run"}, names
    assert out.resolve() not in {r.path for r in runs}
    # Even an aggressive policy can never select the root (or the DB with it).
    doomed = ops.select_for_deletion(runs, keep_last=0)
    assert {r.path.name for r in doomed} == {"real-run"}
    assert (out / "sociosim.db").exists()


def test_retention_is_opt_in_and_selects_correctly(tmp_path):
    for i in range(5):
        _make_run(tmp_path, f"r{i}", age_days=i * 3)
    runs = ops.scan_runs(tmp_path)
    # No policy -> never delete anything (no surprise deletions).
    assert ops.select_for_deletion(runs) == []
    keep2 = ops.select_for_deletion(runs, keep_last=2)
    assert {r.path.name for r in keep2} == {"r2", "r3", "r4"}
    aged = ops.select_for_deletion(runs, max_age_days=7)
    assert {r.path.name for r in aged} == {"r3", "r4"}


def test_export_all_writes_integrity_manifest_and_verifies(tmp_path):
    out = tmp_path / "out"
    _make_run(out, "run-a")
    dest = tmp_path / "archive"
    res = ops.export_all(out, dest)
    assert res["exported"] == ["run-a"]
    manifest = json.loads((dest / "run-a" / "integrity.json").read_text())
    assert manifest["n_files"] == 2
    assert ops.verify_export(dest / "run-a") == []
    # Corrupt an archived file -> integrity check reports it.
    (dest / "run-a" / "events.jsonl").write_text("tampered", encoding="utf-8")
    problems = ops.verify_export(dest / "run-a")
    assert any("sha256 mismatch" in p for p in problems)


def test_disk_status_and_db_health(tmp_path):
    disk = ops.disk_status(tmp_path)
    assert disk["free_bytes"] > 0 and "low_disk" in disk
    absent = ops.db_health(tmp_path / "none.db")
    assert absent["present"] is False and absent["ok"] is True
    # A real store DB is healthy; a garbage file is reported, not "repaired".
    from socio_sim.web.store import RunStore
    db = tmp_path / "s.db"
    RunStore(db)
    assert ops.db_health(db)["ok"] is True
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"this is not a database")
    health = ops.db_health(bad)
    assert health["ok"] is False and "RELEASE.md" in health["detail"]


def test_prune_orphan_history_removes_rows_for_deleted_run_dirs(tmp_path):
    """Deleting run directories must not leave the history DB pointing at
    runs that can no longer be opened (and VACUUM reclaiming nothing)."""
    from socio_sim.web.store import RunStore
    out = tmp_path / "out"
    kept_dir = _make_run(out, "kept")
    gone_dir = out / "gone"
    gone_dir.mkdir(parents=True)
    (gone_dir / "manifest.json").write_text("{}", encoding="utf-8")

    db = tmp_path / "s.db"
    store = RunStore(db)
    base = {"summary": {}, "config": {"n_agents": 200, "n_ticks": 24,
                                      "jurisdictions": ["EU"]},
            "manifest": {"config_hash": "a", "stream_hash": "b"},
            "content_mode": "template",
            "replay": {"checked": False, "ok": None, "msg": ""}}
    store.save("keep1", {**base, "out_dir": str(kept_dir)})
    store.save("drop1", {**base, "out_dir": str(gone_dir)})
    import shutil
    shutil.rmtree(gone_dir)

    res = ops.prune_orphan_history(db, out)
    assert res["pruned"] == 1
    assert store.payload("keep1") is not None
    assert store.payload("drop1") is None


def test_prune_never_drops_a_row_whose_run_still_exists_under_out(tmp_path):
    """CWD-proofing: out_dir is recorded CWD-relative, so a cleanup run from
    a different working directory must NOT prune history for a run that is
    still on disk. Matching by name against the live inventory prevents it."""
    from socio_sim.web.store import RunStore
    out = tmp_path / "out"
    _make_run(out, "still-here")
    db = tmp_path / "s.db"
    store = RunStore(db)
    store.save("r1", {
        "summary": {}, "config": {"n_agents": 200, "n_ticks": 24,
                                  "jurisdictions": ["EU"]},
        "manifest": {"config_hash": "a", "stream_hash": "b"},
        "content_mode": "template",
        "replay": {"checked": False, "ok": None, "msg": ""},
        # A relative path that does NOT resolve from this process's CWD:
        "out_dir": "out/still-here",
    })
    res = ops.prune_orphan_history(db, out)
    assert res["pruned"] == 0
    assert store.payload("r1") is not None


def test_vacuum_db_roundtrip(tmp_path):
    from socio_sim.web.store import RunStore
    db = tmp_path / "s.db"
    RunStore(db)
    res = ops.vacuum_db(db)
    assert res["vacuumed"] is True and res["bytes_after"] > 0
    assert ops.vacuum_db(tmp_path / "missing.db")["vacuumed"] is False


def _boot():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    srv = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{port}"


def test_health_and_ready_endpoints():
    srv, base = _boot()
    try:
        health = json.loads(urllib.request.urlopen(base + "/api/health").read())
        assert health["status"] == "ok" and health["version"]
        try:
            ready = json.loads(urllib.request.urlopen(base + "/api/ready").read())
            assert ready["ready"] is True
        except urllib.error.HTTPError as exc:      # 503 is a valid answer
            assert exc.code == 503
            ready = json.loads(exc.read())
            assert ready["ready"] is False
        assert "disk" in ready and "database" in ready
        meta = json.loads(urllib.request.urlopen(base + "/api/meta").read())
        assert "commit" in meta          # None when not a git checkout
    finally:
        srv.shutdown()


def test_graceful_shutdown_stops_serving():
    srv, base = _boot()
    assert urllib.request.urlopen(base + "/api/health").status == 200
    srv.shutdown()
    srv.server_close()
    with pytest.raises(Exception):
        urllib.request.urlopen(base + "/api/health", timeout=2)
