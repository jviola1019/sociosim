import json
import math
import time
import urllib.request

import numpy as np

from socio_sim.web import app


def test_jsonable_handles_numpy_and_nonfinite():
    out = app._jsonable({
        "a": np.float64(1.5),
        "b": np.int64(3),
        "c": float("nan"),
        "d": float("inf"),
        "e": (np.bool_(True), [np.float32(2.0)]),
        "ci": (np.float64(0.1), np.float64(0.2)),
    })
    assert out["a"] == 1.5 and isinstance(out["a"], float)
    assert out["b"] == 3 and isinstance(out["b"], int)
    assert out["c"] is None and out["d"] is None
    assert out["e"] == [True, [2.0]]
    # round-trips through json without error
    assert json.loads(json.dumps(out))["ci"] == [0.1, 0.2]


def test_build_config_maps_granular_body():
    cfg = app._build_config({
        "profile": "test",
        "jurisdictions": ["US", "EU"],
        "ftc_enabled": False,
        "red_team": ["spammer", "bogus_adversary"],
        "n_agents": 60, "root_seed": 9,
        "graph_kind": "ws", "graph_k": 8, "graph_p": 0.1,
        "classifier_precision": 0.8, "classifier_recall": 0.7,
        "rate_misinfo": 0.12, "human_review_accuracy": 0.85,
        "feed_strategy": "chronological", "holdout_fraction": 0.25,
    })
    assert cfg.n_agents == 60 and cfg.root_seed == 9
    assert cfg.jurisdictions == ("US", "EU") and cfg.ftc_enabled is False
    assert cfg.red_team == ("spammer",)            # invalid filtered out
    assert cfg.graph_kind == "ws" and cfg.graph_params["k"] == 8
    assert cfg.classifier_targets["hate"]["precision"] == 0.8
    assert cfg.category_base_rates["misinfo"] == 0.12
    assert cfg.human_review_accuracy == 0.85
    assert cfg.feed_strategy == "chronological" and cfg.holdout_fraction == 0.25


def test_build_config_filters_invalid_jurisdiction():
    # Unknown jurisdictions are dropped (not an error); falls back to EU.
    cfg = app._build_config({"jurisdictions": ["MARS"]})
    assert cfg.jurisdictions == ("EU",)


def test_build_config_rejects_out_of_range_value():
    import pytest
    with pytest.raises(Exception):
        app._build_config({"holdout_fraction": 1.5})


def test_all_presets_build_valid_configs():
    from socio_sim.presets import PRESETS
    for name, p in PRESETS.items():
        cfg = app._build_config({"profile": "test", **p["fields"]})
        cfg.validate()  # raises on any invalid combination


def _free_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_live_server_runs_simulation_end_to_end():
    """Boot the real stdlib server, POST a run, poll to completion, and
    assert the dashboard payload is well-formed and replay-verified."""
    from http.server import ThreadingHTTPServer
    import threading

    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    try:
        # meta endpoint
        meta = json.loads(urllib.request.urlopen(f"{base}/api/meta").read())
        assert "spammer" in meta["adversaries"]
        assert "eu_dsa" in meta["presets"]
        assert "misinfo" in meta["harmful_categories"]
        assert "llm_available" in meta

        # index served
        html = urllib.request.urlopen(f"{base}/").read().decode()
        assert "SocioSim" in html

        body = json.dumps({
            "profile": "test", "n_agents": 60, "n_ticks": 24,
            "jurisdictions": ["EU"], "verify_replay": True,
        }).encode()
        req = urllib.request.Request(f"{base}/api/run", data=body,
                                     headers={"Content-Type": "application/json"})
        job_id = json.loads(urllib.request.urlopen(req).read())["job_id"]

        result = None
        for _ in range(120):  # up to ~24s
            job = json.loads(
                urllib.request.urlopen(f"{base}/api/job/{job_id}").read())
            if job["status"] == "done":
                result = job["result"]
                break
            if job["status"] == "error":
                raise AssertionError(job.get("error"))
            time.sleep(0.2)
        assert result is not None, "job did not finish"

        # payload shape the dashboard relies on
        s = result["summary"]
        assert "harmful_exposure" in s and "ci" in s["harmful_exposure"]
        assert "moderation" in s and "fairness" in s and "ads" in s
        assert result["replay"]["checked"] and result["replay"]["ok"]
        assert isinstance(result["implausibility"], (int, float))
        assert "report_md" in result and "RUN REPORT" not in result  # report present
        # chart series present for the dashboard
        ch = result["charts"]
        assert len(ch["diurnal"]) == 24
        assert ch["degree_hist"] and ch["timeline_posts"]
        # entire payload is valid JSON (no NaN leaked)
        assert "NaN" not in json.dumps(result)
    finally:
        server.shutdown()


def test_bad_job_id_404():
    from http.server import ThreadingHTTPServer
    import threading
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/job/nope")
            raised = False
        except urllib.error.HTTPError as e:
            raised = (e.code == 404)
        assert raised
    finally:
        server.shutdown()
