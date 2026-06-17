import json
import urllib.request

from socio_sim.web.store import RunStore


def sample_result(cfg_hash="abc", stream="def", n_agents=200):
    return {
        "summary": {"harmful_exposure": {"rate": 0.05},
                    "moderation": {"precision": 0.9, "recall": 0.2}},
        "config": {"jurisdictions": ["EU"], "n_agents": n_agents, "n_ticks": 48},
        "manifest": {"config_hash": cfg_hash, "stream_hash": stream},
        "content_mode": "template", "n_events": 1234, "elapsed_s": 1.5,
        "implausibility": 1.4, "replay": {"ok": True}, "report_md": "# report",
    }


def test_save_list_load_roundtrip(tmp_path):
    store = RunStore(tmp_path / "db.sqlite")
    store.save("run1", sample_result(n_agents=200), label="EU test")
    store.save("run2", sample_result(cfg_hash="x", stream="y", n_agents=1000))
    runs = store.list()
    assert len(runs) == 2
    assert runs[0]["id"] == "run2"  # newest first
    assert store.count() == 2
    payload = store.payload("run1")
    assert payload["manifest"]["config_hash"] == "abc"
    meta = store.meta("run1")
    assert meta["label"] == "EU test" and meta["n_agents"] == 200
    assert meta["replay_ok"] == 1 and abs(meta["harmful_rate"] - 0.05) < 1e-9


def test_auto_label_and_profile(tmp_path):
    store = RunStore(tmp_path / "db.sqlite")
    store.save("r", sample_result(n_agents=10000))
    meta = store.meta("r")
    assert "EU" in meta["label"] and meta["profile"] == "standard"


def test_delete(tmp_path):
    store = RunStore(tmp_path / "db.sqlite")
    store.save("r", sample_result())
    assert store.delete("r") is True
    assert store.count() == 0
    assert store.delete("missing") is False


def test_overwrite_same_id(tmp_path):
    store = RunStore(tmp_path / "db.sqlite")
    store.save("r", sample_result(n_agents=200))
    store.save("r", sample_result(n_agents=999))
    assert store.count() == 1
    assert store.meta("r")["n_agents"] == 999


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_history_endpoints_live(tmp_path, monkeypatch):
    """End-to-end: run via API, then list/load/export through the store."""
    from http.server import ThreadingHTTPServer
    import threading
    import time
    from socio_sim.web import app

    monkeypatch.setattr(app, "_STORE", RunStore(tmp_path / "db.sqlite"))
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        body = json.dumps({"profile": "test", "n_agents": 60, "n_ticks": 24,
                           "jurisdictions": ["EU"], "verify_replay": True,
                           "label": "my run"}).encode()
        req = urllib.request.Request(f"{base}/api/run", data=body,
                                     headers={"Content-Type": "application/json"})
        job_id = json.loads(urllib.request.urlopen(req).read())["job_id"]
        for _ in range(150):
            j = json.loads(urllib.request.urlopen(f"{base}/api/job/{job_id}").read())
            if j["status"] == "done":
                break
            if j["status"] == "error":
                raise AssertionError(j.get("error"))
            time.sleep(0.2)

        runs = json.loads(urllib.request.urlopen(f"{base}/api/runs").read())
        assert runs["count"] == 1
        assert runs["runs"][0]["label"] == "my run"

        loaded = json.loads(urllib.request.urlopen(
            f"{base}/api/runs/{job_id}").read())
        assert "summary" in loaded["result"]

        report = urllib.request.urlopen(
            f"{base}/api/runs/{job_id}/export?fmt=report").read().decode()
        assert "SocioSim Run Report" in report
    finally:
        server.shutdown()
