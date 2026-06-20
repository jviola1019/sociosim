"""SocioSim one-command launcher.

Runs a full simulation end-to-end: builds the world, runs the tick loop, writes
audit logs + manifest, renders a report, scores it against benchmark targets,
and verifies deterministic replay. With --llm it also bootstraps a FREE, keyless
local LLM (Ollama): it locates the binary, starts the server if needed, pulls the
model if missing, then generates post text locally — no API key, no account.

Examples
--------
    python run.py                         # template mode (no LLM, fastest)
    python run.py --llm                   # auto Ollama: start + pull + run
    python run.py --llm --profile quick   # 1,000 agents x 7 days
    python run.py --llm --model qwen2.5:3b --agents 300 --ticks 72

Everything is reproducible: outputs land in out/<run-name>/ with an
events.jsonl audit log and a manifest.json that replays bit-identically.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from socio_sim import RESEARCH_USE_NOTICE  # noqa: E402
from socio_sim.config import RunConfig  # noqa: E402
from socio_sim.llm_bootstrap import (DEFAULT_HOST, ensure_model,  # noqa: E402
                                     ensure_server, find_ollama, server_up)
from socio_sim.pipeline import run_and_analyze  # noqa: E402


def bootstrap_ollama(model: str, host: str):
    """Start a local Ollama server + ensure the model, for CLI runs."""
    print("Bootstrapping free local LLM (Ollama):")
    if not find_ollama():
        print("  Ollama is not installed. Install it (one time) with:\n"
              "    winget install Ollama.Ollama        # Windows\n"
              "    brew install ollama                 # macOS\n"
              "    curl -fsSL https://ollama.com/install.sh | sh   # Linux\n"
              "  Then re-run this command. Falling back to template mode now.")
        return None
    proc = ensure_server(host, log=lambda m: print("  " + m))
    ensure_model(model, host, log=lambda m: print("  " + m))
    print("  LLM ready.")
    return proc


# --------------------------------------------------------------------------
# Simulation run
# --------------------------------------------------------------------------
def run_sim(cfg: RunConfig, n_replicates: int = 1, workers: int = 1, media: int = 0):
    mode = "Research" if n_replicates > 1 else "Preview"
    extra = f", {n_replicates} replicates" if n_replicates > 1 else ""
    print(f"\nRunning {cfg.n_agents} agents x {cfg.n_ticks} hourly ticks "
          f"(jurisdictions={cfg.jurisdictions}, content={cfg.content_mode}, "
          f"mode={mode}{extra})...")
    # Single source of truth — same pipeline the web app and examples use.
    a = run_and_analyze(cfg, n_replicates=n_replicates, workers=workers)
    result = a.result
    print(f"Done. {len(result.log.events)} events. "
          f"Stream hash {result.log.stream_hash()[:16]}...")

    if cfg.content_mode != "template":
        calls = result.log.by_kind("llm_call")
        degr = result.log.by_kind("degradation")
        print(f"LLM backend: {cfg.content_mode} | llm_call events: {len(calls)} "
              f"| degradation (fallback) events: {len(degr)}")
        if calls:
            print(f"  sample generated post: "
                  f"{calls[0]['data']['text_preview']!r}")

    out = Path(cfg.out_dir)
    (out / "report.md").write_text(a.report_md, encoding="utf-8")
    print(f"\nReport:   {out / 'report.md'}")
    print(f"Logs:     {out / 'events.jsonl'}")
    print(f"Manifest: {out / 'manifest.json'}")

    if media > 0:
        import zlib

        from socio_sim.content.media import synth_image, synth_video
        mdir = out / "media"
        mdir.mkdir(parents=True, exist_ok=True)
        posts = [e for e in result.log.events if e["kind"] == "post"][:media]
        for e in posts:
            seed = zlib.crc32(str(e["content_id"]).encode())  # stable per content id
            (mdir / f"{e['content_id']}.png").write_bytes(synth_image(seed, 256, 256))
        if posts:  # one real animated-PNG (APNG) video sample
            vseed = zlib.crc32(str(posts[0]["content_id"]).encode())
            (mdir / "sample_video.png").write_bytes(synth_video(vseed, 10, 192, 192))
        print(f"Synthesized {len(posts)} real PNG images + 1 APNG video -> {mdir}")

    print(f"\nCalibration vs published benchmarks "
          f"(implausibility I={a.implausibility:.2f}, cutoff 3.0):")
    for name, value in a.observed.items():
        spec = a.targets.get(name)
        if spec and value == value:  # skip NaN
            print(f"  {name:22s} observed {value:8.4f}  target "
                  f"{spec['value']} +/- {spec['tolerance']}")

    if a.mc:
        print(f"\nMonte Carlo intervals (provenance: mc-replicated, "
              f"{n_replicates} replicates):")
        for name, d in a.mc.items():
            lo, hi = d["ci"]
            print(f"  {name:24s} median {d['median']:8.4f}  "
                  f"95% [{lo:.4f}, {hi:.4f}]")

    if a.transparency:
        t = a.transparency
        print(f"\nTransparency report: notices {t['notices_sent']} | appeals "
              f"filed {t['appeals']['filed']}/granted {t['appeals']['granted']} "
              f"| human reviews {t['human_reviews']} | deadline misses "
              f"{t['deadline_misses']} | max retention {t['max_retention_months']}mo")
        ri = t.get("rights_impact", {})
        print(f"  rights-impact: {ri.get('appealable_actions', 0)}/"
              f"{ri.get('actions_total', 0)} actions appealable · "
              f"{ri.get('removals_without_notice', 0)} removals without notice")
        for cat, v in t["actions_by_category"].items():
            print(f"  {cat:26s} {v['actions']:4d} actions {v['by_action']}")

    if a.replay["checked"]:
        print(f"\nDeterministic replay: {a.replay['msg']}")
        return 0 if a.replay["ok"] else 1
    print(f"\nDeterministic replay: {a.replay['msg']}")
    return 0


# --------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="SocioSim one-command launcher (free local LLM optional).")
    p.add_argument("--web", action="store_true",
                   help="launch the browser dashboard instead of a CLI run")
    p.add_argument("--port", type=int, default=8765, help="web server port")
    p.add_argument("--bind", default="127.0.0.1",
                   help="web bind host (default 127.0.0.1; use 0.0.0.0 only on a "
                        "trusted host/container — exposes the local console)")
    p.add_argument("--no-open", action="store_true",
                   help="with --web, do not auto-open the browser")
    p.add_argument("--llm", action="store_true",
                   help="generate post text with a free local Ollama model "
                        "(auto starts server + pulls model)")
    p.add_argument("--profile", default="quick", choices=["quick", "test", "standard"],
                   help="quick=1k/7d (default), test=200/48t, standard=10k/28d")
    p.add_argument("--jurisdictions", default="EU",
                   help="comma list of US,EU,CN (default EU)")
    p.add_argument("--benchmark", default="default",
                   help="calibration target set: default | twitter_like | facebook_like")
    p.add_argument("--classifier", default="noise", choices=["noise", "trained"],
                   help="moderation classifier: noise model (default) or a real trained one")
    p.add_argument("--model", default="qwen2.5:0.5b",
                   help="Ollama model for --llm (default qwen2.5:0.5b, ~400MB)")
    p.add_argument("--host", default=DEFAULT_HOST, help="Ollama host:port")
    p.add_argument("--agents", type=int, help="override agent count")
    p.add_argument("--ticks", type=int, help="override hourly tick count")
    p.add_argument("--seed", type=int, default=42, help="root seed")
    p.add_argument("--replicates", type=int, default=1,
                   help="Research run: N Monte Carlo replicates for percentile "
                        "intervals (default 1 = Preview, single run)")
    p.add_argument("--workers", type=int, default=1,
                   help="parallel processes for Research Monte Carlo replicates "
                        "(default 1; results are identical to sequential)")
    p.add_argument("--validate", action="store_true",
                   help="run a BehaviorParams sensitivity + calibration study, "
                        "write VALIDATION_REPORT.md, and exit")
    p.add_argument("--sens-samples", type=int, default=24,
                   help="LHS samples for --validate sensitivity (default 24)")
    p.add_argument("--media", type=int, default=0,
                   help="synthesize real PNG images for the first N posts into "
                        "<out>/media/ (deterministic, offline procedural)")
    p.add_argument("--out", default="out/run", help="output directory")
    args = p.parse_args()

    print(f"NOTE: {RESEARCH_USE_NOTICE}\n")

    if args.validate:
        from socio_sim.validation.study import (render_validation_report,
                                                run_validation_study)
        print(f"Validation study: profile={args.profile}, "
              f"{args.sens_samples} sensitivity samples, seed {args.seed}...")
        study = run_validation_study(profile=args.profile,
                                     n_samples=args.sens_samples, seed=args.seed)
        (ROOT / "VALIDATION_REPORT.md").write_text(
            render_validation_report(study), encoding="utf-8")
        print(f"Wrote VALIDATION_REPORT.md  (implausibility I = "
              f"{study['calibration']['implausibility']:.2f}, cutoff 3.0)")
        return 0

    if args.web:
        # If --llm is also set, bootstrap Ollama first so the dashboard's
        # 'ollama' content mode works without separate setup.
        if args.llm:
            bootstrap_ollama(args.model, args.host)
        from socio_sim.web.app import serve
        serve(host=args.bind, port=args.port, open_browser=not args.no_open)
        return 0

    server_proc = None
    content_mode = "template"
    base_url = ""
    if args.llm:
        server_proc = bootstrap_ollama(args.model, args.host)
        if server_proc is not None or server_up(args.host):
            content_mode = "ollama"
            base_url = f"http://{args.host}"

    factory = {"quick": RunConfig.quick, "test": RunConfig.test,
               "standard": RunConfig.standard}[args.profile]
    overrides = dict(
        jurisdictions=tuple(j.strip() for j in args.jurisdictions.split(",")),
        root_seed=args.seed, out_dir=args.out, content_mode=content_mode,
        llm_model=args.model if content_mode != "template" else "",
        llm_base_url=base_url, benchmark=args.benchmark,
        classifier_mode=args.classifier,
    )
    if args.agents:
        overrides["n_agents"] = args.agents
    if args.ticks:
        overrides["n_ticks"] = args.ticks
    cfg = factory(**overrides)

    try:
        return run_sim(cfg, n_replicates=args.replicates, workers=args.workers,
                       media=args.media)
    finally:
        if server_proc is not None:
            print("\nStopping the Ollama server we started.")
            server_proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
