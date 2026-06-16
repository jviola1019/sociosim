"""Minimal programmatic example: configure a run and use the shared pipeline.

For day-to-day use prefer the launcher — `python run.py` (CLI) or
`python run.py --web` (browser). This script shows how to drive SocioSim from
your own Python via `socio_sim.pipeline.run_and_analyze`, the single entry point
the CLI and web app also use, so behaviour can never diverge.

Usage: python examples/quickstart.py [--profile quick|test] [--content ollama]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from socio_sim import RESEARCH_USE_NOTICE
from socio_sim.config import RunConfig
from socio_sim.pipeline import run_and_analyze


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--profile", default="quick", choices=["quick", "test"])
    p.add_argument("--content", default="template",
                   choices=["template", "ollama", "openai_compatible", "claude"])
    p.add_argument("--model", default="", help="LLM model (e.g. qwen2.5:0.5b)")
    args = p.parse_args()

    print(f"NOTE: {RESEARCH_USE_NOTICE}\n")
    factory = RunConfig.quick if args.profile == "quick" else RunConfig.test
    cfg = factory(jurisdictions=("EU",), out_dir="out/quick_demo",
                  content_mode=args.content, llm_model=args.model)

    print(f"Running {cfg.n_agents} agents x {cfg.n_ticks} ticks "
          f"(content={cfg.content_mode})…")
    a = run_and_analyze(cfg)

    (Path(cfg.out_dir) / "report.md").write_text(a.report_md, encoding="utf-8")
    print(f"{len(a.result.log.events)} events · report at "
          f"{Path(cfg.out_dir) / 'report.md'}")
    print(f"Benchmark implausibility I = {a.implausibility:.2f} (cutoff 3.0)")
    print(f"Replay: {a.replay['msg']}")
    return 0 if (a.replay["ok"] in (True, None)) else 1


if __name__ == "__main__":
    sys.exit(main())
