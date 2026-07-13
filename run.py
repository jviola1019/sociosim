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
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from socio_sim import RESEARCH_USE_NOTICE  # noqa: E402
    from socio_sim.config import RunConfig  # noqa: E402
    from socio_sim.evidence import targets_metadata_complete  # noqa: E402
    from socio_sim.llm_bootstrap import (DEFAULT_HOST, ensure_model,  # noqa: E402
                                         ensure_server, find_ollama, server_up)
    from socio_sim.pipeline import run_and_analyze  # noqa: E402
except ModuleNotFoundError as _e:  # missing runtime dependency -> friendly help
    _name = getattr(_e, "name", "a dependency")
    sys.stderr.write(
        f"\n[SocioSim] Missing dependency: '{_name}'.\n"
        "SocioSim needs numpy, networkx, scipy and pyyaml. Install them from the\n"
        "project root (a virtualenv is recommended), then re-run your command:\n\n"
        "    python -m pip install -e .            # installs SocioSim + deps\n"
        "    # or:  python -m pip install -r requirements.txt\n\n"
        "Virtualenv (avoids touching system Python):\n"
        "    python -m venv .venv\n"
        "    .venv\\Scripts\\activate   (Windows)   |   source .venv/bin/activate (macOS/Linux)\n"
        "    python -m pip install -e .\n\n")
    sys.exit(1)


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
def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n / 1:.0f}{unit}"
        n /= 1024
    return f"{n:.0f}GB"


def _lifecycle_command(args) -> int | None:
    """Local data-lifecycle subcommands (Phase 6). Returns an exit code when
    one of them ran, or None to continue with a normal simulation."""
    from socio_sim import ops
    from socio_sim.web.store import DEFAULT_DB

    out_root = Path("out")

    if args.verify_export:
        problems = ops.verify_export(Path(args.verify_export))
        if problems:
            print(f"INTEGRITY FAILED for {args.verify_export}:")
            print("\n".join(f"  - {p}" for p in problems))
            return 1
        print(f"integrity OK: {args.verify_export} matches its integrity.json")
        return 0

    if args.export_all:
        res = ops.export_all(out_root, Path(args.export_all))
        print(f"exported {len(res['exported'])} run(s) to {res['dest']} "
              "(each with a sha256 integrity.json; re-check with "
              "--verify-export)")
        return 0

    if args.vacuum_db:
        res = ops.vacuum_db(DEFAULT_DB)
        if not res["vacuumed"]:
            print(f"nothing to vacuum ({res['reason']})")
        else:
            print(f"vacuumed {DEFAULT_DB}: "
                  f"{res['bytes_before']} -> {res['bytes_after']} bytes")
        return 0

    if args.status:
        runs = ops.scan_runs(out_root)
        disk = ops.disk_status(out_root)
        db = ops.db_health(DEFAULT_DB)
        total = sum(r.bytes for r in runs)
        print(f"Local runs: {len(runs)} in {out_root}/ "
              f"({total / 1e6:.1f} MB total)")
        for r in runs[:10]:
            print(f"  {r.path.name:32s} {r.age_days:6.1f}d  "
                  f"{r.bytes / 1e6:7.2f} MB")
        if len(runs) > 10:
            print(f"  ... and {len(runs) - 10} more")
        print(f"Disk: {disk['free_bytes'] / 1e9:.1f} GB free"
              + ("  *** LOW DISK ***" if disk["low_disk"] else ""))
        print(f"Run-history DB: present={db['present']} ok={db['ok']} "
              f"({db['bytes'] / 1e6:.2f} MB) — {db['detail']}")
        print("Retention is opt-in: nothing is deleted unless you run "
              "--cleanup --keep-last N / --max-age-days N --yes")
        return 0

    if args.cleanup:
        if args.keep_last is None and args.max_age_days is None:
            print("--cleanup needs a policy: --keep-last N and/or "
                  "--max-age-days N (refusing to guess)")
            return 2
        runs = ops.scan_runs(out_root)
        doomed = ops.select_for_deletion(runs, keep_last=args.keep_last,
                                         max_age_days=args.max_age_days)
        if not doomed:
            print("retention policy matches nothing; no runs to delete")
            return 0
        freed = sum(r.bytes for r in doomed)
        print(f"{'DELETING' if args.yes else 'DRY RUN — would delete'} "
              f"{len(doomed)} run(s), freeing {freed / 1e6:.1f} MB:")
        for r in doomed:
            print(f"  {r.path}  ({r.age_days:.1f}d, {r.bytes / 1e6:.2f} MB)")
        if not args.yes:
            print("\nNothing was deleted. Re-run with --yes to confirm.")
            return 0
        import shutil as _shutil
        for r in doomed:
            _shutil.rmtree(r.path)
        # Deleting directories alone would leave the history DB pointing at
        # runs that can no longer be opened (and VACUUM would reclaim
        # nothing, since the rows remain).
        orphans = ops.prune_orphan_history(DEFAULT_DB, out_root)
        vac = ops.vacuum_db(DEFAULT_DB)
        print(f"deleted {len(doomed)} run(s); pruned {orphans['pruned']} "
              "orphaned history row(s)"
              + (f"; database {vac['bytes_before']} -> {vac['bytes_after']} "
                 "bytes" if vac.get("vacuumed") else ""))
        return 0

    return None


def _print_diagnostics(a, n_replicates: int) -> None:
    """Aggregate-fit + Monte Carlo diagnostics with the same honesty gates
    the web layer applies (audit C-01/C-02/A-04): no observed-vs-target
    distance table while target evidence is 'unsupported', no "95%" label
    on a small-N percentile range, and the implausibility cutoff cites its
    convention instead of reading as a project-measured bound."""
    print(f"\nAggregate-fit diagnostics vs legacy benchmark targets "
          f"(implausibility I={a.implausibility:.2f}, cutoff 3.0 "
          f"[external_aggregate: 3-sigma history-matching convention]):")
    if targets_metadata_complete(a.targets):
        for name, value in a.observed.items():
            spec = a.targets.get(name)
            if spec and value == value:  # skip NaN
                print(f"  {name:22s} observed {value:8.4f}  target "
                      f"{spec['value']} +/- {spec['tolerance']}")
    else:
        print("  target comparison suppressed: bundled target evidence is "
              "'unsupported' (same gate as the web UI); observed values only:")
        for name, value in a.observed.items():
            if value == value:  # skip NaN
                print(f"  {name:22s} observed {value:8.4f}")

    if a.mc:
        print(f"\nMonte Carlo intervals (provenance: mc-replicated, "
              f"{n_replicates} replicates):")
        for name, d in a.mc.items():
            lo, hi = d["ci"]
            if n_replicates >= 20:
                interval = f"95% [{lo:.4f}, {hi:.4f}]"
            else:
                # A 2-point percentile range is not a 95% interval; say
                # what it actually is.
                interval = (f"percentile range over N={n_replicates} "
                            f"replicates [{lo:.4f}, {hi:.4f}]")
            print(f"  {name:24s} median {d['median']:8.4f}  {interval}")


def run_sim(cfg: RunConfig, n_replicates: int = 1, workers: int = 1, media: int = 0):
    cfg = replace(cfg, n_replicates=n_replicates)
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
        u = result.llm_usage
        if u:
            print(f"  transport usage: {u['calls']} calls "
                  f"({u['cache_hits']} cache hits, {u['blocked']} blocked, "
                  f"{u['failures']} failed) | {u['latency_s']:.1f}s total "
                  f"latency | tokens in/out "
                  f"{u['prompt_eval_tokens']}/{u['response_eval_tokens']} "
                  "(0 = backend reported none; diagnostics only, outside "
                  "the hashed event stream)")
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
        if posts:  # one deterministic animated-PNG (APNG) video sample
            vseed = zlib.crc32(str(posts[0]["content_id"]).encode())
            (mdir / "sample_video.png").write_bytes(synth_video(vseed, 10, 192, 192))
        print(f"Synthesized {len(posts)} synthetic PNG images + 1 APNG video -> {mdir}")

    _print_diagnostics(a, n_replicates)

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
    p.add_argument("--profile", default="quick",
                   choices=["quick", "test", "standard", "aggregate_matched_prototype"],
                   help="quick=1k/7d (default), test=200/48t, standard=10k/28d, "
                        "aggregate_matched_prototype=synthetic aggregate-fit prototype")
    p.add_argument("--jurisdictions", default="EU",
                   help="comma list of US,EU,CN (default EU)")
    p.add_argument("--benchmark", default="sourced_aggregates_v1",
                   help="aggregate target set. Default 'sourced_aggregates_v1' "
                        "(values verified against their primary sources). The "
                        "'legacy_unsupported_*' sets are retired: their numbers "
                        "could not be verified (several are contradicted by the "
                        "papers they cited) and they exist only to reproduce "
                        "older runs")
    p.add_argument("--classifier", default="synthetic_noise_classifier",
                   choices=["synthetic_noise_classifier", "synthetic_template_classifier"],
                   help="moderation classifier mechanics mode; both options are synthetic")
    p.add_argument("--dynamic-graph", action="store_true",
                   help="enable daily follow/unfollow/churn graph evolution "
                        "(off by default = static graph)")
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
                   help="run BehaviorParams sensitivity + aggregate-fit diagnostics, "
                        "write VALIDATION_REPORT.md, and exit")
    p.add_argument("--backtest", action="store_true",
                   help="held-out aggregate-fit diagnostics plus synthetic mechanism "
                        "checks, write BACKTEST_REPORT.md, and exit")
    p.add_argument("--measure-classifier", action="store_true",
                   help="measure classifier algorithm components on bundled "
                        "benchmark samples (license/source: docs/DATA_MANIFEST.md) "
                        "(F1/ROC-AUC) -> BENCHMARK_REPORT.md, and exit")
    p.add_argument("--sens-samples", type=int, default=24,
                   help="LHS samples for --validate sensitivity (default 24)")
    p.add_argument("--media", type=int, default=0,
                   help="synthesize deterministic PNG previews for the first N posts into "
                        "<out>/media/ (deterministic, offline procedural)")
    p.add_argument("--out", default="out/run", help="output directory")
    # -- local data lifecycle (Phase 6). Opt-in; never deletes by default.
    p.add_argument("--status", action="store_true",
                   help="show local run inventory, disk space, and run-history "
                        "database health, then exit")
    p.add_argument("--cleanup", action="store_true",
                   help="apply the retention policy to out/ (DRY RUN unless "
                        "--yes is also given); needs --keep-last and/or "
                        "--max-age-days")
    p.add_argument("--keep-last", type=int,
                   help="retention: keep the N most recent runs")
    p.add_argument("--max-age-days", type=float,
                   help="retention: delete runs older than N days")
    p.add_argument("--yes", action="store_true",
                   help="confirm a --cleanup deletion (without it, cleanup is "
                        "a dry run and deletes nothing)")
    p.add_argument("--vacuum-db", action="store_true",
                   help="VACUUM the run-history database (reclaims space after "
                        "deletions), then exit")
    p.add_argument("--export-all", metavar="DEST",
                   help="copy every run in out/ to DEST with a per-run sha256 "
                        "integrity manifest, then exit")
    p.add_argument("--verify-export", metavar="DIR",
                   help="re-check an exported run directory against its "
                        "integrity.json, then exit")
    args = p.parse_args()

    print(f"NOTE: {RESEARCH_USE_NOTICE}\n")

    lifecycle = _lifecycle_command(args)
    if lifecycle is not None:
        return lifecycle

    if args.validate:
        from socio_sim.validation.study import (render_validation_report,
                                                run_validation_study)
        print(f"Validation-ladder diagnostics: profile={args.profile}, "
              f"{args.sens_samples} sensitivity samples, seed {args.seed}...")
        study = run_validation_study(profile=args.profile,
                                     n_samples=args.sens_samples, seed=args.seed)
        (ROOT / "VALIDATION_REPORT.md").write_text(
            render_validation_report(study), encoding="utf-8")
        print(f"Wrote VALIDATION_REPORT.md  (implausibility I = "
              f"{study['aggregate_fit']['implausibility']:.2f}, cutoff 3.0)")
        return 0

    if args.backtest:
        from socio_sim.validation.backtest import (leave_out_backtest,
                                                   render_backtest_report)
        from socio_sim.validation.stylized import evaluate_stylized_facts
        prof = args.profile if args.profile in (
            "quick", "aggregate_matched_prototype", "standard") else "quick"
        print(f"Aggregate-fit diagnostics on '{args.benchmark}' legacy aggregates "
              f"(profile={prof}) + synthetic mechanism checks...")
        bt = leave_out_backtest(benchmark=args.benchmark, profile=prof, seed=args.seed)
        sf = evaluate_stylized_facts()
        (ROOT / "BACKTEST_REPORT.md").write_text(
            render_backtest_report(bt, sf), encoding="utf-8")
        print(f"Wrote BACKTEST_REPORT.md (diagnostic_test_pass={bt['test_pass']}, "
              f"I_test={bt['implausibility_test']:.2f}; mechanism checks "
              f"{sf['n_pass']}/{sf['n_total']})")
        return 0

    if args.measure_classifier:
        from socio_sim.validation.benchmark_eval import (evaluate_all,
                                                         render_benchmark_report)
        # B-01: don't assert "licensed" as bare CLI fact -- cite where the
        # license/source evidence actually lives.
        print("Running classifier component benchmark diagnostics on bundled "
              "benchmark samples (license/source: docs/DATA_MANIFEST.md)...")
        res = evaluate_all(seed=args.seed)
        (ROOT / "BENCHMARK_REPORT.md").write_text(
            render_benchmark_report(res), encoding="utf-8")
        for r in res:
            print(f"  {r['name']:16s} ({r['task']}): F1={r['f1']:.3f} "
                  f"ROC-AUC={r['auc']:.3f}")
        print("Wrote BENCHMARK_REPORT.md")
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
               "standard": RunConfig.standard,
               "aggregate_matched_prototype":
               RunConfig.aggregate_matched_prototype}[args.profile]
    overrides = dict(
        jurisdictions=tuple(j.strip() for j in args.jurisdictions.split(",")),
        root_seed=args.seed, out_dir=args.out, content_mode=content_mode,
        llm_model=args.model if content_mode != "template" else "",
        llm_base_url=base_url, benchmark=args.benchmark,
        classifier_mode=args.classifier,
    )
    if args.dynamic_graph:
        overrides.update(follow_rate=0.02, unfollow_rate=0.01, churn_rate=0.004)
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
