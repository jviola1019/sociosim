import json
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


def test_all_presets_run_end_to_end():
    """Every shipped preset must actually run a simulation (not just validate) —
    catches non-working presets / field mappings at runtime."""
    from socio_sim.engine import Simulation
    from socio_sim.presets import PRESETS
    for name, p in PRESETS.items():
        cfg = app._build_config({"profile": "test", **p["fields"],
                                 "n_agents": 80, "n_ticks": 12})
        res = Simulation(cfg).run()
        assert res.log.by_kind("post"), f"preset {name!r} produced no posts"


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


def test_sbm_block_sizes_match_n_agents():
    """SBM must size its blocks to the agent count, not a hardcoded 1000."""
    cfg = app._build_config({"profile": "test", "graph_kind": "sbm",
                             "n_agents": 300, "jurisdictions": ["EU"]})
    assert cfg.graph_kind == "sbm"
    assert sum(cfg.graph_params["block_sizes"]) == 300
    # falls back to the profile's agent count when not overridden
    cfg2 = app._build_config({"profile": "test", "graph_kind": "sbm",
                              "jurisdictions": ["EU"]})
    assert sum(cfg2.graph_params["block_sizes"]) == cfg2.n_agents


def test_sbm_config_runs_end_to_end():
    """An SBM config must actually build (graph node count == n_agents)."""
    from socio_sim.engine import Simulation
    cfg = app._build_config({"profile": "test", "graph_kind": "sbm",
                             "n_agents": 120, "n_ticks": 6, "jurisdictions": ["EU"]})
    Simulation(cfg).run()  # raises if block sizes disagree with n_agents


def test_campaigns_fn_builds_factory_from_specs():
    fn = app._campaigns_fn({"campaigns": [
        {"id": "a", "advertiser": "A", "bid": 4.0, "budget": 500,
         "base_ctr": 0.02, "base_cvr": 0.06},
        {"id": "b", "advertiser": "B", "bid": 2.0, "budget": 200}]})
    assert fn is not None
    cfg = app._build_config({"profile": "test", "jurisdictions": ["EU"]})
    camps = fn(cfg)
    assert [c.id for c in camps] == ["a", "b"]
    assert camps[0].bid == 4.0 and camps[0].base_ctr == 0.02
    # fresh objects each call (independent budgets for Monte Carlo)
    assert fn(cfg)[0] is not camps[0]
    # no/empty spec -> default campaigns
    assert app._campaigns_fn({}) is None and app._campaigns_fn({"campaigns": []}) is None


def test_safe_static_path_blocks_traversal():
    """Static serving must contain requests within the static dir."""
    assert app.safe_static_path("app.js") is not None
    assert str(app.safe_static_path("app.js")).endswith("app.js")
    assert app.safe_static_path("style.css") is not None
    # Traversal attempts escape the static dir -> rejected.
    assert app.safe_static_path("../app.py") is None
    assert app.safe_static_path("../../config.py") is None
    assert app.safe_static_path("../store.py") is None


def test_live_server_research_mode_returns_mc_and_transparency():
    """Research mode (n_replicates>1) over HTTP returns an mc bundle + a
    transparency report; preview-only payloads carry mode/transparency too."""
    from http.server import ThreadingHTTPServer
    import threading
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        body = json.dumps({"profile": "test", "n_agents": 50, "n_ticks": 12,
                           "jurisdictions": ["EU"], "verify_replay": False,
                           "n_replicates": 2}).encode()
        req = urllib.request.Request(f"{base}/api/run", data=body,
                                     headers={"Content-Type": "application/json"})
        job_id = json.loads(urllib.request.urlopen(req).read())["job_id"]
        result = None
        for _ in range(150):
            job = json.loads(
                urllib.request.urlopen(f"{base}/api/job/{job_id}").read())
            if job["status"] == "done":
                result = job["result"]
                break
            if job["status"] == "error":
                raise AssertionError(job.get("error"))
            time.sleep(0.2)
        assert result is not None, "research job did not finish"
        assert result["mode"] == "research" and result["n_replicates"] == 2
        assert result["mc"] and "harmful_exposure_rate" in result["mc"]
        assert result["transparency"]["pack_versions"]
        assert "NaN" not in json.dumps(result)
        # in-UI transparency export endpoint returns the tally as JSON
        tx = json.loads(urllib.request.urlopen(
            f"{base}/api/runs/{job_id}/export?fmt=transparency").read())
        assert tx["pack_versions"] and "actions_by_category" in tx
    finally:
        server.shutdown()


def test_compare_endpoint_returns_crn_paired_deltas():
    """/api/compare runs baseline vs intervention (CRN-paired) and returns
    per-metric deltas with percentile CIs."""
    from http.server import ThreadingHTTPServer
    import threading
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        body = json.dumps({"profile": "test", "n_agents": 80, "n_ticks": 12,
                           "jurisdictions": ["US"],
                           "intervention": {"jurisdictions": ["EU"]},
                           "compare_replicates": 2}).encode()
        req = urllib.request.Request(f"{base}/api/compare", data=body,
                                     headers={"Content-Type": "application/json"})
        job_id = json.loads(urllib.request.urlopen(req).read())["job_id"]
        result = None
        for _ in range(300):
            job = json.loads(
                urllib.request.urlopen(f"{base}/api/job/{job_id}").read())
            if job["status"] == "done":
                result = job["result"]
                break
            if job["status"] == "error":
                raise AssertionError(job.get("error"))
            time.sleep(0.2)
        assert result is not None, "compare job did not finish"
        assert result["n_replicates"] == 2
        assert result["baseline_jurisdictions"] == ["US"]
        assert result["intervention_jurisdictions"] == ["EU"]
        c = result["compare"]
        assert "harmful_exposure_rate" in c
        m = c["harmful_exposure_rate"]
        assert "delta_median" in m and "delta_ci" in m
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
