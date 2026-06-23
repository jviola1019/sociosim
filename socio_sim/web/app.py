"""SocioSim local web app — Python stdlib only (no Flask/FastAPI, no install).

A localhost research console: configure a run by concept (scale, network,
content, classifier, policy, moderation, feed, ads, adversaries), the server
runs the real simulation engine in a background thread, then returns the same
analytics, calibration, replay verification and chart series the CLI produces.
Binds to 127.0.0.1 only; single-user research tool. When a run requests the
local-LLM content mode, the server bootstraps Ollama on demand.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import math
import secrets
import socket
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import numpy as np

from socio_sim import RESEARCH_USE_NOTICE, __version__
from socio_sim.analytics.lens import run_lens
from socio_sim.analytics.metrics import cascade_sizes, cascade_tree
from socio_sim.config import ADVERSARIES, CATEGORIES, RunConfig
from socio_sim.llm_bootstrap import ensure_model, ensure_server, server_up
from socio_sim.pipeline import run_and_analyze
from socio_sim.presets import PRESETS
from socio_sim.web.store import RunStore

STATIC_DIR = Path(__file__).parent / "static"
_CONTENT_TYPES = {".html": "text/html; charset=utf-8",
                  ".css": "text/css; charset=utf-8",
                  ".js": "text/javascript; charset=utf-8",
                  ".svg": "image/svg+xml"}

#: Max JSON body accepted on POST (DoS guard; ASVS V5). 2 MB is ample for configs.
MAX_BODY_BYTES = 2 * 1024 * 1024
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
#: Response security headers set on EVERY response (OWASP Secure Headers; MDN).
#: CSP allows the external app.js (script-src 'self') + inline styles the UI uses
#: ('unsafe-inline' for style only) + data: images; frames denied (clickjacking).
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
        "object-src 'none'"),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def _validate_llm_url(url: str) -> None:
    """SSRF guard (OWASP A10 / CWE-918) for the user-supplied LLM base_url:
    require http(s) and a loopback/private host; resolve-then-validate; block
    public IPs and cloud metadata (169.254.169.254). Raises ValueError if unsafe.
    Empty url (template mode) is a no-op."""
    if not url:
        return
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise ValueError("llm_base_url scheme must be http or https")
    host = p.hostname or ""
    if host in _LOOPBACK_HOSTS:
        return
    try:
        infos = socket.getaddrinfo(host, p.port or 80)
    except OSError as exc:
        raise ValueError(f"llm_base_url host not resolvable: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        # Block link-local (incl. cloud metadata 169.254.169.254), multicast and
        # reserved FIRST — note ipaddress treats link-local as is_private.
        if ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError(
                f"llm_base_url host {ip} is link-local/metadata/reserved — SSRF guard")
        if not (ip.is_loopback or ip.is_private):
            raise ValueError(
                f"llm_base_url must point to a loopback/private host (got public {ip})")


def safe_static_path(suffix: str):
    """Resolve a ``/static/<suffix>`` request, contained within STATIC_DIR.

    Returns the resolved Path, or None for traversal attempts (``..`` / absolute
    paths) that would escape the static directory. Localhost-only binding does
    not make traversal safe: a page in the browser can still fetch 127.0.0.1.
    """
    base = STATIC_DIR.resolve()
    try:
        target = (base / suffix).resolve()
    except (OSError, ValueError):
        return None
    if target == base or target.is_relative_to(base):
        return target
    return None

HARMFUL_CATS = ("hate", "harassment", "fraud", "misinfo", "adult",
                "illegal_goods", "self_harm")

_JOBS: dict = {}
_LOCK = threading.Lock()
_LLM_HOST = "127.0.0.1:11434"
_STORE = RunStore()  # persistent run history (out/sociosim.db)


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    return obj


def _f(body, key, default):
    try:
        v = body.get(key, default)
        return type(default)(v) if v is not None and v != "" else default
    except (TypeError, ValueError):
        return default


def _build_config(body: dict) -> RunConfig:
    """Map the granular web form into a validated RunConfig.

    Fields are organised by concept (network / content / classifier / policy /
    moderation / feed / ads). A profile sets the scale baseline; explicit
    agents/ticks override it.
    """
    profile = body.get("profile", "quick")
    factory = {"quick": RunConfig.quick, "test": RunConfig.test,
               "standard": RunConfig.standard,
               "calibrated": RunConfig.calibrated}.get(profile, RunConfig.quick)

    jurisdictions = tuple(j for j in body.get("jurisdictions", ["EU"])
                          if j in ("US", "EU", "CN")) or ("EU",)
    red_team = tuple(a for a in body.get("red_team", []) if a in ADVERSARIES)

    # classifier: global precision/recall applied to every category
    prec = _f(body, "classifier_precision", 0.90)
    rec = _f(body, "classifier_recall", 0.85)
    classifier_targets = {c: {"precision": prec, "recall": rec}
                          for c in CATEGORIES}

    # content prevalence: per-harmful-category base rates (others keep defaults)
    base_rates = dict(RunConfig().category_base_rates)
    for cat in HARMFUL_CATS + ("ai_generated",):
        if f"rate_{cat}" in body and body[f"rate_{cat}"] not in (None, ""):
            base_rates[cat] = float(body[f"rate_{cat}"])

    graph_kind = body.get("graph_kind", "ba")
    # SBM blocks must sum to the agent count (else the graph has a different node
    # count than n_agents -> engine indexing error). Derive from the effective n.
    _prof_n = {"quick": 1000, "test": 200, "standard": 10000,
               "calibrated": 1000}.get(profile, 1000)
    _n = int(body["n_agents"]) if body.get("n_agents") else _prof_n
    _half = _n // 2
    if graph_kind == "ba":
        graph_params = {"m": int(_f(body, "graph_m", 5))}
    elif graph_kind == "plc":
        graph_params = {"m": int(_f(body, "graph_m", 5)),
                        "p": _f(body, "graph_plc_p", 0.7)}
    elif graph_kind == "ws":
        graph_params = {"k": int(_f(body, "graph_k", 10)),
                        "p": _f(body, "graph_p", 0.05)}
    else:  # sbm
        graph_params = {"block_sizes": [_half, _n - _half],
                        "p_matrix": [[0.02, 0.002], [0.002, 0.02]]}

    overrides = dict(
        jurisdictions=jurisdictions,
        ftc_enabled=bool(body.get("ftc_enabled", True)),
        feed_strategy=body.get("feed_strategy", "personalized"),
        eu_optout_rate=_f(body, "eu_optout_rate", 0.20),
        exploration_epsilon=_f(body, "exploration_epsilon", 0.10),
        feed_size=int(_f(body, "feed_size", 20)),
        ad_slot_interval=int(_f(body, "ad_slot_interval", 5)),
        content_mode=body.get("content_mode", "template"),
        classifier_mode=body.get("classifier_mode", "noise"),
        benchmark=body.get("benchmark", "default"),
        follow_rate=_f(body, "follow_rate", 0.0),
        unfollow_rate=_f(body, "unfollow_rate", 0.0),
        churn_rate=_f(body, "churn_rate", 0.0),
        n_topics=int(_f(body, "n_topics", 8)),
        classifier_targets=classifier_targets,
        category_base_rates=base_rates,
        ads_enabled=bool(body.get("ads_enabled", True)),
        holdout_fraction=_f(body, "holdout_fraction", 0.10),
        ad_frequency_cap_per_day=int(_f(body, "ad_frequency_cap_per_day", 4)),
        ftc_compliance=bool(body.get("ftc_compliance", True)),
        graph_kind=graph_kind,
        graph_params=graph_params,
        homophily_rewire_fraction=_f(body, "homophily_rewire_fraction", 0.15),
        human_review_accuracy=_f(body, "human_review_accuracy", 0.92),
        human_review_delay_ticks=int(_f(body, "human_review_delay_ticks", 6)),
        appeal_grant_fp_rate=_f(body, "appeal_grant_fp_rate", 0.70),
        red_team=red_team,
        root_seed=int(_f(body, "root_seed", 42)),
        tick_hours=int(_f(body, "tick_hours", 1)),
        out_dir=f"out/web/{int(time.time())}",
    )
    if body.get("n_agents"):
        overrides["n_agents"] = int(body["n_agents"])
    if body.get("n_ticks"):
        overrides["n_ticks"] = int(body["n_ticks"])
    if body.get("llm_model"):
        overrides["llm_model"] = str(body["llm_model"])
    if body.get("llm_base_url"):
        overrides["llm_base_url"] = str(body["llm_base_url"])
    _validate_llm_url(overrides.get("llm_base_url", ""))   # SSRF guard (A10/CWE-918)
    return factory(**overrides).validate()


def _campaigns_fn(body: dict):
    """Build a campaigns factory from a web `campaigns` spec list, or None to
    use the default campaigns. The factory returns FRESH Campaign objects each
    call (budgets mutate during a run; Monte Carlo needs independent copies)."""
    specs = body.get("campaigns")
    if not specs:
        return None
    clean = []
    for s in specs:
        try:
            # Creative-studio targeting: a 'segment' (audience age group) and
            # 'market' (topic/vertical) map into the engine's Campaign.targeting,
            # so each variant reaches a real audience -> a genuine A/B by segment.
            targeting = {}
            seg = str(s.get("segment", "") or "")
            if seg and seg.lower() != "all":
                targeting["age_groups"] = [seg]
            mkt = s.get("market", "")
            if mkt not in (None, "", "any"):
                try:
                    targeting["topics"] = [int(mkt)]
                except (TypeError, ValueError):
                    pass
            clean.append(dict(
                id=str(s.get("id") or f"camp{len(clean) + 1}"),
                advertiser=str(s.get("advertiser") or "Advertiser"),
                bid=float(s.get("bid", 2.0)),
                budget=float(s.get("budget", 100.0)),
                base_ctr=float(s.get("base_ctr", 0.012)),
                base_cvr=float(s.get("base_cvr", 0.05)),
                conversion_value=float(s.get("conversion_value", 1.0)),
                targeting=targeting,
            ))
        except (TypeError, ValueError):
            continue
    if not clean:
        return None
    from socio_sim.ads.campaigns import Campaign
    return lambda cfg: [Campaign(**c) for c in clean]


def _chart_data(result, summary) -> dict:
    """Compact, JSON-safe series for the dashboard charts."""
    cfg = result.config
    posts = result.log.by_kind("post")

    # diurnal posting (24 bins, hour of day)
    diurnal = [0] * 24
    for e in posts:
        diurnal[(e["tick"] * cfg.tick_hours) % 24] += 1

    # activity timeline: posts & removals bucketed into <=48 points
    nb = min(48, cfg.n_ticks)
    width = max(cfg.n_ticks / nb, 1)
    posts_t = [0] * nb
    removed_t = [0] * nb
    for e in posts:
        posts_t[min(int(e["tick"] / width), nb - 1)] += 1
    for e in result.log.by_kind("moderation"):
        if e["data"].get("action") in ("remove", "downrank"):
            removed_t[min(int(e["tick"] / width), nb - 1)] += 1

    # cascade size histogram
    sizes = cascade_sizes(result.log)
    smax = max(sizes) if sizes else 1
    chist = [0] * smax
    for s in sizes:
        chist[s - 1] += 1
    cascade = [[i + 1, c] for i, c in enumerate(chist)]

    return {
        "diurnal": diurnal,
        "degree_hist": result.graph_stats.get("degree_hist", []),
        "cascade": cascade,
        "timeline_posts": posts_t,
        "timeline_removed": removed_t,
        "timeline_buckets": nb,
        "cascade_tree": cascade_tree(result.log),
    }


_STANCE_WORDS = ["Critical", "Skeptical", "Measured", "Hopeful", "Enthusiastic"]


def _sample_feed(result, limit: int = 9) -> list:
    """A diverse, representative slice of generated content for the Feed
    preview: persona, topic, moderation outcome, and (LLM mode) real text."""
    from socio_sim.content.generate import TOPICS
    personas = result.personas
    posts = [e for e in result.log.by_kind("post")
             if e["data"].get("parent_id") is None]
    # text previews (LLM mode) keyed by content id
    text_by_id = {e["content_id"]: e["data"].get("text_preview")
                  for e in result.log.by_kind("llm_call")}
    action_by_id = {}
    for e in result.log.by_kind("moderation"):
        a = e["data"].get("action")
        if a in ("remove", "downrank", "label", "add_platform_label"):
            action_by_id.setdefault(e["content_id"], a)

    # rank for diversity: prefer harmful, ai-generated, and acted-on items
    harmful = set(HARMFUL_CATS)

    def score(e):
        cats = set(e["data"].get("true_categories", []))
        return (bool(cats & harmful) * 2 + e["data"].get("ai_generated", False)
                + (e["content_id"] in action_by_id) * 2)
    posts = sorted(posts, key=score, reverse=True)

    out, seen_authors = [], set()
    for e in posts:
        aid = e["actor_id"]
        if aid in seen_authors and len(out) > 3:
            continue
        seen_authors.add(aid)
        d = e["data"]
        topic = TOPICS[d.get("topic", 0) % len(TOPICS)]
        stance = d.get("stance", 0.0)
        sw = _STANCE_WORDS[min(int((stance + 1) / 2 * 5), 4)]
        text = text_by_id.get(e["content_id"]) or f"{sw} take on {topic}."
        ideo = float(personas.ideology[aid, 0]) if 0 <= aid < personas.n else 0.0
        out.append({
            "id": e["content_id"], "author": aid,
            "age": str(personas.age_group[aid]) if 0 <= aid < personas.n else "?",
            "ideology": "left" if ideo < -0.2 else ("right" if ideo > 0.2 else "center"),
            "topic": topic, "stance": round(stance, 2), "text": text,
            "categories": sorted(d.get("true_categories", [])),
            "ai_generated": bool(d.get("ai_generated")),
            "action": action_by_id.get(e["content_id"], "none"),
        })
        if len(out) >= limit:
            break
    return out


def _run_job(job_id: str, body: dict):
    job = _JOBS[job_id]
    try:
        cfg = _build_config(body)
        job["n_ticks"] = cfg.n_ticks
        # Preview (1) vs Research (N replicates -> Monte Carlo intervals).
        n_replicates = max(1, min(int(body.get("n_replicates", 1) or 1), 200))

        # On-demand local LLM bootstrap so the dashboard's ollama mode works
        # without separate setup (skip for user-supplied openai_compatible).
        if cfg.content_mode == "ollama" and not server_up(_LLM_HOST):
            job["phase"] = "starting local LLM"
            ensure_server(_LLM_HOST, log=lambda m: job.__setitem__("phase", m))
            job["phase"] = "loading model"
            ensure_model(cfg.llm_model or "qwen2.5:0.5b", _LLM_HOST,
                         log=lambda m: job.__setitem__("phase", m))
        started = time.time()

        def on_progress(tick, total):
            job["progress"] = tick / total
            job["tick"] = tick

        # Same run → analyze → verify pipeline the CLI and examples use.
        verify_replay = bool(body.get("verify_replay", cfg.n_agents <= 2000))
        a = run_and_analyze(
            cfg, verify_replay=verify_replay, n_replicates=n_replicates,
            campaigns_fn=_campaigns_fn(body), progress_callback=on_progress,
            on_phase=lambda p: job.__setitem__("phase", p))
        result = a.result

        llm_calls = result.log.by_kind("llm_call")
        # Kind-stratified event sample for the in-UI audit-log explorer (up to
        # 60 per kind, in order). The full log is on disk at out_dir/events.jsonl.
        ev_sample, _per_kind = [], {}
        for e in result.log.events:
            c = _per_kind.get(e["kind"], 0)
            if c < 60:
                ev_sample.append(e)
                _per_kind[e["kind"]] = c + 1
        job["result"] = _jsonable({
            "summary": a.summary,
            "charts": _chart_data(result, a.summary),
            "feed": _sample_feed(result),
            "report_md": a.report_md,
            "lens": run_lens(cfg.to_dict(), a.summary),
            "manifest": result.manifest.__dict__,
            "config": cfg.to_dict(),
            "observed": a.observed,
            "targets": a.targets,
            "implausibility": a.implausibility,
            "replay": a.replay,
            "mc": a.mc,
            "n_replicates": n_replicates,
            "mode": "research" if n_replicates > 1 else "preview",
            "transparency": a.transparency,
            "event_sample": ev_sample,
            "event_kinds": sorted(_per_kind),
            "elapsed_s": round(time.time() - started, 2),
            "n_events": len(result.log.events),
            "content_mode": cfg.content_mode,
            "n_llm_calls": len(llm_calls),
            "n_degradations": len(result.log.by_kind("degradation")),
            "sample_post": (llm_calls[0]["data"]["text_preview"]
                            if llm_calls else None),
            "out_dir": cfg.out_dir,
        })
        # Persist to the run database so it appears in History and can be
        # reopened, compared, or exported later.
        try:
            _STORE.save(job_id, job["result"], label=body.get("label", ""))
        except Exception:
            pass  # history is best-effort; never fail a run over it
        job["status"] = "done"
        job["progress"] = 1.0
    except Exception as exc:
        job["status"] = "error"
        job["error"] = f"{type(exc).__name__}: {exc}"


def _run_compare(job_id: str, body: dict):
    """Baseline-vs-intervention experiment (common random numbers) over the web.
    `body` is a normal run config; `body["intervention"]` holds the overrides
    that define the intervention arm; `compare_replicates` sets N."""
    job = _JOBS[job_id]
    try:
        from socio_sim.experiments.compare import compare
        from socio_sim.pipeline import _headline_metrics
        n = max(2, min(int(body.get("compare_replicates", 10) or 10), 100))
        job["phase"] = "comparing (baseline vs intervention)"
        base = _build_config(body)
        interv = _build_config({**body, **(body.get("intervention") or {})})
        res = compare(base, interv, n, _headline_metrics,
                      campaigns_fn=_campaigns_fn(body))
        job["result"] = _jsonable({
            "compare": res, "n_replicates": n,
            "baseline_jurisdictions": list(base.jurisdictions),
            "intervention_jurisdictions": list(interv.jurisdictions),
            "provenance": "crn-paired-monte-carlo",
        })
        job["status"] = "done"
        job["progress"] = 1.0
    except Exception as exc:
        job["status"] = "error"
        job["error"] = f"{type(exc).__name__}: {exc}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _security_headers(self):
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)

    def _send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path):
        if not path.is_file():
            self.send_error(404, "not found")
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",
                         _CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _origin_ok(self) -> bool:
        """Reject cross-origin state-changing requests (CSRF / DNS-rebinding):
        if an Origin/Referer is present it must be loopback. Non-browser clients
        (no Origin) are allowed. Also pins Host to loopback."""
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        if host and host not in _LOOPBACK_HOSTS:
            return False
        origin = self.headers.get("Origin") or self.headers.get("Referer")
        if origin:
            h = (urlparse(origin).hostname or "")
            if h not in _LOOPBACK_HOSTS:
                return False
        return True

    def _token_ok(self) -> bool:
        """If the server set an access token (real `serve()`), require it on
        state-changing POSTs (constant-time). Tests constructing Handler without
        a token skip this; the Origin check still applies."""
        token = getattr(self.server, "access_token", None)
        if not token:
            return True
        sent = self.headers.get("X-SocioSim-Token", "")
        return hmac.compare_digest(sent, token)

    def do_GET(self):
        route = self.path.split("?")[0]
        if route in ("/", "/index.html"):
            self._send_file(STATIC_DIR / "index.html")
        elif route == "/api/meta":
            self._send_json({
                "version": __version__,
                "notice": RESEARCH_USE_NOTICE,
                "token": getattr(self.server, "access_token", None),
                "adversaries": list(ADVERSARIES),
                "harmful_categories": list(HARMFUL_CATS),
                "defaults": RunConfig().category_base_rates,
                "presets": PRESETS,
                "llm_available": server_up(_LLM_HOST, timeout=0.4),
                "profiles": {"quick": {"n_agents": 1000, "n_ticks": 168},
                             "test": {"n_agents": 200, "n_ticks": 48},
                             "standard": {"n_agents": 10000, "n_ticks": 672}},
            })
        elif route.startswith("/api/job"):
            job = _JOBS.get(route.rsplit("/", 1)[-1])
            if not job:
                self._send_json({"error": "unknown job"}, 404)
                return
            self._send_json({k: v for k, v in job.items() if k != "body"})
        elif route == "/api/runs":
            self._send_json({"runs": _STORE.list(), "count": _STORE.count()})
        elif route.startswith("/api/runs/"):
            parts = route[len("/api/runs/"):].split("/")
            run_id = parts[0]
            if len(parts) > 1 and parts[1] == "export":
                self._export_run(run_id)
            else:
                payload = _STORE.payload(run_id)
                if payload is None:
                    self._send_json({"error": "unknown run"}, 404)
                else:
                    self._send_json({"result": payload, "meta": _STORE.meta(run_id)})
        elif route == "/api/creative":
            self._send_creative()
        elif route.startswith("/static/"):
            target = safe_static_path(route[len("/static/"):])
            if target is None:
                self.send_error(404, "not found")
            else:
                self._send_file(target)
        else:
            self.send_error(404, "not found")

    def _send_creative(self):
        """Serve a REAL, deterministic PNG ad creative (media.synth_image),
        seeded by the ?key= string so it varies by campaign/segment/market.
        Bounded dimensions (DoS guard)."""
        import zlib
        from urllib.parse import parse_qs, urlparse

        from socio_sim.content.media import synth_image
        q = parse_qs(urlparse(self.path).query)
        key = (q.get("key", ["ad"])[0] or "ad")[:200]
        try:
            w = min(max(int(q.get("w", ["320"])[0]), 16), 1024)
            h = min(max(int(q.get("h", ["200"])[0]), 16), 1024)
        except ValueError:
            self.send_error(400, "bad dimensions")
            return
        data = synth_image(zlib.crc32(key.encode("utf-8")), w, h)
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def _export_run(self, run_id: str):
        from urllib.parse import parse_qs, urlparse
        fmt = parse_qs(urlparse(self.path).query).get("fmt", ["json"])[0]
        payload = _STORE.payload(run_id)
        if payload is None:
            self._send_json({"error": "unknown run"}, 404)
            return
        if fmt == "report":
            body, ctype, name = payload.get("report_md", ""), "text/markdown", "report.md"
        elif fmt == "transparency":
            body = json.dumps(payload.get("transparency") or {}, indent=2)
            ctype, name = "application/json", "transparency.json"
        else:  # json
            body, ctype, name = json.dumps(payload, indent=2), "application/json", "result.json"
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Disposition", f'attachment; filename="sociosim-{run_id}-{name}"')
        self.send_header("Content-Length", str(len(data)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        route = self.path.split("?")[0]
        if route not in ("/api/run", "/api/compare"):
            self.send_error(404, "not found")
            return
        if not self._origin_ok():                       # CSRF / DNS-rebinding guard
            self._send_json({"error": "cross-origin request rejected"}, 403)
            return
        if not self._token_ok():                        # access-token guard
            self._send_json({"error": "missing or invalid access token"}, 403)
            return
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
        if ctype != "application/json":
            self._send_json({"error": "Content-Type must be application/json"}, 415)
            return
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY_BYTES:                     # DoS / oversized-body guard
            self._send_json({"error": "request body too large"}, 413)
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON"}, 400)
            return
        try:
            _build_config(body)  # validates the baseline arm
        except Exception as exc:
            self._send_json({"error": f"{type(exc).__name__}: {exc}"}, 400)
            return
        job_id = uuid.uuid4().hex[:12]
        with _LOCK:
            _JOBS[job_id] = {"status": "running", "progress": 0.0,
                             "tick": 0, "phase": "queued"}
        target = _run_compare if route == "/api/compare" else _run_job
        threading.Thread(target=target, args=(job_id, body), daemon=True).start()
        self._send_json({"job_id": job_id})

    def do_DELETE(self):
        route = self.path.split("?")[0]
        if route.startswith("/api/runs/"):
            ok = _STORE.delete(route[len("/api/runs/"):])
            self._send_json({"deleted": ok}, 200 if ok else 404)
        else:
            self.send_error(404, "not found")


def serve(host="127.0.0.1", port=8765, open_browser=True):
    server = ThreadingHTTPServer((host, port), Handler)
    # Per-session access token: defends state-changing POSTs against browser
    # CSRF / DNS-rebinding even on loopback. Served via /api/meta (same-origin
    # reads it; cross-origin pages cannot read the response) and required on POST.
    server.access_token = secrets.token_urlsafe(32)
    if host not in _LOOPBACK_HOSTS:
        print(f"WARNING: binding {host} exposes the console beyond loopback — "
              "use only on a trusted host/network.")
    url = f"http://{host}:{port}"
    print(f"SocioSim web console running at {url}")
    print("Research use only. Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
