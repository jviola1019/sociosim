import json
import re
import time
import urllib.request
from pathlib import Path

import numpy as np
import pytest

from socio_sim.web import app


def test_jsonable_handles_numpy_and_nonfinite():
    out = app._jsonable({
        "a": np.float64(1.5),
        "b": np.int64(3),
        "c": float("nan"),
        "d": float("inf"),
        "e": (np.bool_(True), [np.float32(2.0)]),
        "flag": False,
        "ci": (np.float64(0.1), np.float64(0.2)),
    })
    assert out["a"] == 1.5 and isinstance(out["a"], float)
    assert out["b"] == 3 and isinstance(out["b"], int)
    assert out["c"] is None and out["d"] is None
    assert out["e"] == [True, [2.0]]
    assert out["flag"] is False
    # round-trips through json without error
    assert json.loads(json.dumps(out))["ci"] == [0.1, 0.2]


def test_build_config_maps_granular_body():
    cfg = app._build_config({
        "profile": "test",
        "jurisdictions": ["US", "EU"],
        "ftc_enabled": False,
        "red_team": ["spammer"],
        "n_agents": 60, "root_seed": 9,
        "graph_kind": "ws", "graph_k": 8, "graph_p": 0.1,
        "classifier_precision": 0.8, "classifier_recall": 0.7,
        "rate_misinfo": 0.12, "human_review_accuracy": 0.85,
        "feed_strategy": "chronological", "holdout_fraction": 0.25,
    })
    assert cfg.n_agents == 60 and cfg.root_seed == 9
    assert cfg.jurisdictions == ("US", "EU") and cfg.ftc_enabled is False
    assert cfg.red_team == ("spammer",)
    assert cfg.graph_kind == "ws" and cfg.graph_params["k"] == 8
    assert cfg.classifier_targets["hate"]["precision"] == 0.8
    assert cfg.category_base_rates["misinfo"] == 0.12
    assert cfg.human_review_accuracy == 0.85
    assert cfg.feed_strategy == "chronological" and cfg.holdout_fraction == 0.25


def test_build_config_rejects_invalid_api_values():
    with pytest.raises(ValueError, match="jurisdictions"):
        app._build_config({"jurisdictions": ["MARS"]})
    with pytest.raises(ValueError, match="red_team"):
        app._build_config({"red_team": ["bogus_adversary"]})
    with pytest.raises(ValueError, match="feed_size"):
        app._build_config({"feed_size": "not-a-number"})
    with pytest.raises(ValueError, match="ftc_enabled"):
        app._build_config({"ftc_enabled": "not-a-bool"})


def test_build_config_parses_boolean_strings_and_preserves_aggregate_profile():
    cfg = app._build_config({"profile": "aggregate_matched_prototype", "ftc_enabled": "false",
                             "ads_enabled": "true"})
    assert cfg.graph_kind == "plc"
    assert cfg.graph_params == {"m": 5, "p": 0.7}
    assert cfg.ftc_enabled is False and cfg.ads_enabled is True


def test_calibrated_profile_not_publicly_advertised():
    assert "calibrated" not in app._PROFILES


def test_legacy_calibrated_profile_migrates_to_aggregate_matched_prototype():
    """Old saved requests/scripts may still send profile=='calibrated'; it
    must be silently migrated to the current name rather than exposed as a
    normal choice or rejected outright."""
    cfg = app._build_config({"profile": "calibrated"})
    cfg2 = app._build_config({"profile": "aggregate_matched_prototype"})
    assert cfg.graph_kind == cfg2.graph_kind == "plc"
    assert cfg.graph_params == cfg2.graph_params == {"m": 5, "p": 0.7}
    assert cfg.n_agents == cfg2.n_agents
    assert cfg.n_ticks == cfg2.n_ticks


def test_unknown_profile_still_rejected():
    with pytest.raises(ValueError, match="profile"):
        app._build_config({"profile": "made_up_profile"})


def test_template_classifier_ignores_precision_targets_for_identity():
    a = app._build_config({"classifier_mode": "synthetic_template_classifier",
                           "classifier_precision": 0.5, "classifier_recall": 0.5})
    b = app._build_config({"classifier_mode": "synthetic_template_classifier",
                           "classifier_precision": 0.99, "classifier_recall": 0.99})
    assert a.classifier_targets == b.classifier_targets
    assert a.config_hash() == b.config_hash()


def test_build_config_rejects_out_of_range_value():
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
        assert result["implausibility_components"]
        assert result["implausibility_dominant_metric"]
        assert "report_md" in result and "RUN REPORT" not in result  # report present
        assert not re.search(r"\bnan\b", result["report_md"].lower())
        assert "not legal advice" in result["report_md"]
        assert "no_real_person_data" in result
        # chart series present for the dashboard
        ch = result["charts"]
        assert len(ch["diurnal"]) == 24
        assert ch["degree_hist"] and ch["timeline_posts"]
        ad_metric = next(iter(result["summary"]["ads"].values()))
        for key in ("budget_configured", "budget_remaining", "lift_qvalue_bh",
                    "lift_pvalue_raw", "lift_significant_bh_fdr",
                    "economics_provenance", "economic_inputs", "lift_ci_method"):
            assert key in ad_metric
        assert ad_metric["spend"] <= ad_metric["budget_configured"] + 1e-9
        # entire payload is valid JSON (no NaN leaked)
        assert "NaN" not in json.dumps(result)
        # audit-log explorer sample present + stratified by kind
        assert result["event_sample"] and result["event_kinds"]
        assert "post" in result["event_kinds"]
    finally:
        server.shutdown()


def test_creative_endpoint_serves_registered_v4_png():
    """/api/creative returns a deterministic registered v4 PNG."""
    import struct
    from http.server import ThreadingHTTPServer
    import threading
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        r = urllib.request.urlopen(f"{base}/api/creative?key=brand-general&w=300&h=150")
        data = r.read()
        assert r.headers.get("Content-Type") == "image/png"
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", data[16:24]) == (1200, 600)
        big = urllib.request.urlopen(f"{base}/api/creative?key=x&w=9999&h=9999").read()
        assert struct.unpack(">II", big[16:24]) == (1200, 600)
        a = urllib.request.urlopen(f"{base}/api/creative?key=brand-a&w=1024&h=512").read()
        b = urllib.request.urlopen(f"{base}/api/creative?key=brand-b&w=1024&h=512").read()
        assert struct.unpack(">II", a[16:24]) == (1200, 600)
        assert a != b
        assert urllib.request.urlopen(
            f"{base}/api/creative?key=brand-a&w=1024&h=512").read() == a
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


def test_build_config_preserves_web_replicate_count():
    cfg = app._build_config({"profile": "test", "jurisdictions": ["EU"],
                             "n_replicates": 7})
    assert cfg.n_replicates == 7


def test_sbm_config_runs_end_to_end():
    """An SBM config must actually build (graph node count == n_agents)."""
    from socio_sim.engine import Simulation
    cfg = app._build_config({"profile": "test", "graph_kind": "sbm",
                             "n_agents": 120, "n_ticks": 6, "jurisdictions": ["EU"]})
    Simulation(cfg).run()  # raises if block sizes disagree with n_agents


def test_campaigns_fn_builds_factory_from_specs():
    fn = app._campaigns_fn({"campaigns": [
        {"id": "a", "advertiser": "A", "bid": 4.0, "budget": 500,
         "base_ctr": 0.02, "base_cvr": 0.06, "conversion_value": 7,
         "ltv_multiplier": 4, "attribution_window_ticks": 24},
        {"id": "b", "advertiser": "B", "bid": 2.0, "budget": 200}]})
    assert fn is not None
    cfg = app._build_config({"profile": "test", "jurisdictions": ["EU"]})
    camps = fn(cfg)
    assert [c.id for c in camps] == ["a", "b"]
    assert camps[0].bid == 4.0 and camps[0].base_ctr == 0.02
    assert camps[0].conversion_value == 7
    assert camps[0].ltv_multiplier == 4
    assert camps[0].attribution_window_ticks == 24
    # fresh objects each call (independent budgets for Monte Carlo)
    assert fn(cfg)[0] is not camps[0]
    # no/empty spec -> default campaigns
    assert app._campaigns_fn({}) is None and app._campaigns_fn({"campaigns": []}) is None


def test_campaign_specs_are_normalized_for_persistence():
    clean = app._normalize_campaign_specs({"campaigns": [
        {"id": "a", "advertiser": "A", "bid": "4", "budget": "500",
         "segment": "25-34", "market": "2", "conversion_value": "6"}]})
    assert clean[0]["id"] == "a"
    assert clean[0]["targeting"] == {"age_groups": ["25-34"], "topics": [2]}
    assert clean[0]["conversion_value"] == 6.0


def test_campaign_specs_reject_non_deliverable_or_malformed_rows():
    bad_specs = [
        {"bid": 0, "budget": 100},
        {"bid": 1, "budget": 0},
        {"bid": 1, "budget": 100, "base_ctr": 1.5},
        {"bid": 1, "budget": 100, "segment": "unknown"},
    ]
    for spec in bad_specs:
        with pytest.raises(ValueError):
            app._normalize_campaign_specs({"campaigns": [spec]})


def test_bundled_v4_assets_exist_and_are_unignored():
    root = Path(__file__).resolve().parents[1]
    assets = root / "socio_sim" / "web" / "static" / "assets"
    v4 = assets / "v4"
    assert (v4 / "registry.json").is_file()
    assert len(list(v4.glob("feed-cover-v4-*.png"))) == 48
    assert len(list(v4.glob("ad-creative-v4-*.png"))) == 32
    assert len(list(v4.glob("editorial-v4-*.png"))) == 12
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "!socio_sim/web/static/assets/v4/*.png" in gitignore


def test_dynamic_graph_chart_data_uses_final_degree_hist():
    from socio_sim.analytics.metrics import summarize_run
    from socio_sim.config import RunConfig
    from socio_sim.engine import Simulation
    cfg = RunConfig.test(jurisdictions=("EU",), n_ticks=72,
                         follow_rate=0.1, unfollow_rate=0.1, churn_rate=0.04)
    result = Simulation(cfg).run()
    charts = app._chart_data(result, summarize_run(result))
    assert charts["degree_hist"] == result.graph_stats["final"]["degree_hist"]


def test_campaign_segment_market_map_to_targeting():
    """Creative-studio segment/market fields map into engine Campaign.targeting
    so each variant reaches a real audience (a genuine A/B by segment/market)."""
    fn = app._campaigns_fn({"campaigns": [
        {"id": "a", "advertiser": "A", "bid": 3, "budget": 500,
         "segment": "18-24", "market": "2"},
        {"id": "b", "advertiser": "B", "bid": 3, "budget": 500,
         "segment": "all", "market": "any"}]})
    cfg = app._build_config({"profile": "test", "jurisdictions": ["EU"]})
    camps = fn(cfg)
    assert camps[0].targeting == {"age_groups": ["18-24"], "topics": [2]}
    assert camps[1].targeting == {}                      # 'all'/'any' -> untargeted
    from socio_sim.engine import Simulation
    Simulation(app._build_config({"profile": "test", "n_agents": 120, "n_ticks": 12,
                                  "jurisdictions": ["EU"]})).run()  # arms run


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
        assert result["transparency"]["not_legal_advice"]
        assert result["transparency"]["no_real_person_data"]
        assert result["transparency"]["provenance"] == "deterministic_audit_tally"
        assert "NaN" not in json.dumps(result)
        # in-UI transparency export endpoint returns the tally as JSON
        tx = json.loads(urllib.request.urlopen(
            f"{base}/api/runs/{job_id}/export?fmt=transparency").read())
        assert tx["pack_versions"] and "actions_by_category" in tx
        assert tx["not_legal_advice"] and tx["research_use_notice"]
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
        assert "ad_impressions" in c
        assert "ad_ctr" in c
        assert "ad_lift_itt" in c
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
