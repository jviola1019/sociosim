# SocioSim Usage

## Install

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (source .venv/bin/activate on POSIX)
pip install -e ".[dev]"           # quote the extras so zsh/PowerShell don't glob
python -m pytest                  # full test suite; -m "not slow" to skip stats tests
# `python -m pytest` (not bare `pytest`) binds to THIS interpreter — important on
# Windows, where the Microsoft-Store `pytest.exe` shim can miss the venv packages.
```

## Web console (browser dashboard)

```bash
python run.py --web              # opens http://127.0.0.1:8765 in your browser
python run.py --web --port 9000 --no-open
```

The server is Python stdlib only — no Flask/FastAPI, nothing extra to install.
It binds to `127.0.0.1` (localhost, single-user). The interface is a clean,
light, editorial design (Swiss-inspired restraint — generous whitespace,
hairline rules, a single accent, no gradients or status lights) with subtle
motion (blur-in reveals, count-up metrics, sliding tab indicators).

**Configuration is organised by concept across tabs**, not just by country:

- **Scenario** — a preset (EU DSA, US §230, CN labelling, multi-jurisdiction,
  marketing experiment, misinformation stress test, fairness audit, or Custom)
  populates the other tabs; then scale profile, seed, tick length, run label,
  replay toggle, and **Monte Carlo Replicates** (1 = Preview / within-run
  intervals; >1 = Research run with mc-replicated percentile intervals).
- **Network** — agent/tick overrides, topic count, graph model (BA / PLC / WS / SBM)
  and its parameters, homophily rewiring.
- **Content** — generator (template / local LLM), model, and per-category
  ground-truth prevalence sliders (hate, harassment, misinfo, fraud, adult,
  self-harm, illegal goods, AI-generated).
- **Moderation** — jurisdiction packs + FTC toggle, classifier precision/recall,
  human-review accuracy and delay, appeal grant rate.
- **Feed & Ads** — ranking strategy, EU opt-out, exploration ε, feed size,
  holdout fraction, frequency cap, disclosure compliance, and a **campaign
  editor** (add/remove campaigns with bid / budget / base CTR / base CVR /
  conversion value / LTV multiplier / attribution window / segment / market;
  blank = three default campaigns).
Red-team adversaries are folded into cited Research/Business presets rather
than a standalone tab; selecting those presets shows the active adversaries in
the "what this changes" summary.

The simulation runs **only when Run Simulation is clicked**, after settings are
tuned. The engine runs in a background thread with a live progress meter
(`GET /api/job/<id>`); results render as a tabbed dashboard:

- **Overview** — metric cards with confidence-interval bars.
- **Feed** — a sampled slice of generated content, each post shown as a card with
  a **unique, deterministic cover image and avatar** (generated bitmap topic
  atlas + seeded SVG avatar — offline, reproducible), persona, category tags, and the
  moderation action applied.
- **Charts** — diurnal posting, degree distribution, activity timeline, cascade
  sizes (hand-built SVG).
- **Network** — sampled social-graph topology (top hubs + edges, force-directed,
  coloured by ideology).
- **Cascade** — the largest share tree, nodes revealed in posting-time order
  (propagation replay).
- **Fairness** (confusion grid + FPR/FNR by group), **Ads** (each campaign with a
  **unique fictional v3 ad creative** + table incl. CUPED-adjusted lift, MDE,
  ROAS/iROAS/CAC/LTV and Benjamini-Hochberg discovery screen), **Calibration**
  (benchmark whisker plot), **Log** (markdown report + Monte Carlo intervals +
  transparency tally; **Export** as Markdown / full JSON / transparency JSON).

Outputs for each run are also written under `out/web/<timestamp>/`.

### CLI flags (`run.py`)

```bash
python run.py --profile quick                    # Preview run (single replicate)
python run.py --replicates 20                    # Research run: Monte Carlo 95% intervals
python run.py --validate [--sens-samples 24]     # sensitivity + calibration -> VALIDATION_REPORT.md
python run.py --web [--port 8765 --bind 0.0.0.0 --no-open]   # browser console
python run.py --llm [--model qwen2.5:0.5b]       # free local Ollama content
```

`--bind` defaults to `127.0.0.1` (localhost only). Non-loopback bind requires
`SOCIOSIM_ACCESS_TOKEN` and explicit `SOCIOSIM_ALLOWED_HOSTS` for the Host
allow-list; protected exports and history calls use the `X-SocioSim-Token`
header rather than tokenized URLs. Use non-loopback bind only behind trusted
network controls (see `SECURITY.md`).

When a run requests the local-LLM content mode, the server **bootstraps Ollama
on demand** (starts the server, pulls the model) and shows the phase; if the
server is unreachable and cannot start, generation degrades to template text
after a few attempts rather than hanging. Replay verification runs automatically
for ≤2,000-agent runs (toggleable); it is skipped by default on larger runs
because it doubles runtime.

### Run history (database) and export

Every completed run is saved to a local **SQLite database** at
`out/sociosim.db` (stdlib `sqlite3`, no install). The **History** button in the
masthead opens a drawer listing past runs with their label, age, scale, key
metrics, and replay status; each entry can be **reopened** (re-renders the full
dashboard from the stored result), **exported**, or **deleted**. History
persists across server restarts. Give a run a **Run Label** on the Scenario tab
to name it. Export a finished run from the **Export** menu in the report header
as Markdown (`report.md`) or full JSON (`result.json`); the raw event log is
written per run under `out/web/<timestamp>/events.jsonl`.

Programmatic access: `GET /api/runs` (list), `GET /api/runs/<id>` (full result),
`GET /api/runs/<id>/export?fmt=report|json`, `DELETE /api/runs/<id>`.

## Run profiles

| Profile  | Agents | Ticks (hourly) | Replicates | Use |
|----------|--------|----------------|------------|-----|
| standard | 10,000 | 672 (28 days)  | 100        | research runs |
| quick    | 1,000  | 168 (7 days)   | 20         | iteration/demos |
| test     | 200    | 48             | 2          | CI/unit tests |

```python
from socio_sim.config import RunConfig
from socio_sim.engine import Simulation

cfg = RunConfig.quick(jurisdictions=("EU",), root_seed=7, out_dir="out/myrun")
result = Simulation(cfg).run(write=True)   # writes events.jsonl + manifest.json
```

Key config knobs (all validated eagerly): `jurisdictions` (any of US/EU/CN),
`ftc_enabled`, `feed_strategy` (`personalized|chronological|random`),
`eu_optout_rate`, `content_mode` (`template|claude|ollama|openai_compatible`), `classifier_targets`
(per-category precision/recall), `category_base_rates`, `ads_enabled`,
`holdout_fraction`, `ad_frequency_cap_per_day`, `graph_kind` (`ba|plc|ws|sbm`),
`red_team` (adversary names).

## Reports and metrics

```python
from socio_sim.analytics.metrics import summarize_run
from socio_sim.analytics.report import render

summary = summarize_run(result)            # key aggregates carry a provenance-labelled 95% interval
markdown = render(summary, result.manifest)
```

## Experiments (baseline vs intervention, CRN-paired)

```python
from socio_sim.experiments.compare import compare
from socio_sim.experiments.scenarios import policy_stress_eu_vs_us

baseline, intervention = policy_stress_eu_vs_us("quick")
res = compare(baseline, intervention, n_replicates=20, metric_fn=my_metrics)
```

`compare` pairs replicates with common random numbers, so deltas isolate the
intervention. Red-team scenarios: `experiments.scenarios.red_team_suite()`.

## Monte Carlo + calibration

```python
from socio_sim.validation.montecarlo import run_replicates
from socio_sim.validation.calibrate import history_match, abc_posterior
from socio_sim.validation.targets import load_targets, compute_observed
```

- `run_replicates` -> outcome distributions (median + 95% percentile interval).
- `history_match` (LHS, implausibility < 3) then `abc_posterior` (closest
  fraction) -> parameter credible intervals.
- `validation.sensitivity.first_order_indices` -> first-order (correlation-ratio)
  sensitivity; `saltelli_indices` / `study.saltelli_study` -> gold-standard
  Saltelli **S1 + total-effect ST** (interactions). `study.multi_output_sensitivity`
  sweeps several outputs over a Sobol design across seeds.
- `study.posterior_calibrated_mc` chains history-match -> ABC posterior -> output
  interval (parameter-uncertainty propagation). All written to
  `VALIDATION_REPORT.md` via `run.py --validate`.

### Validation ladder (research-only -> measured)
SocioSim is honest about *how* validated a claim is. The provenance ladder:
`synthetic-exploratory` < `uncalibrated` < `calibration-consistent` (I<3 vs
published aggregates) < **`stylized-fact-validated`** < **`held-out-aggregate`** < `measured-on-benchmark`. No claim may exceed its label.

- **Stylized facts** (`validation.stylized`, provenance `stylized-fact-validated`):
  does the calibrated world reproduce documented empirical regularities? — heavy-
  tailed degree, clustering >> random, right-skewed cascades, participation
  inequality, diurnal cycle (each cited).
- **Held-out aggregate backtest** (`validation.backtest`, provenance `held-out-aggregate`): calibrate the graph on a train subset of public aggregates, then validate held-out aggregate metrics within tolerance. This is an aggregate sanity check, not platform-level prediction.
- **Measured on real benchmarks** (`validation.benchmark_eval`, provenance
  `measured-on-benchmark`, the top rung): `python run.py --measure-classifier`
  trains the classifier on a deterministic split of bundled, license-clean,
  de-identified datasets and reports REAL precision/recall/F1/ROC-AUC — Civil
  Comments toxicity (CC0) and Deysi spam (Apache-2.0) -> `BENCHMARK_REPORT.md`.
- `python run.py --backtest` runs the aggregate backtest + stylized facts -> `BACKTEST_REPORT.md`.
- Data governance for every dataset is recorded in `docs/DATA_MANIFEST.md`
  (aggregate/public only, no PII, no scraping). Real-person decisions / point-
  prediction of a specific platform are out of scope by design.

## Models & engineered features

Every option below is reachable from the CLI (`run.py`), the web console, and
`RunConfig`. Defaults keep runs deterministic; opt-in features never change the
default event stream.

- **Calibrated profile** — `--profile calibrated` / `RunConfig.calibrated()`.
  History-matched Holme-Kim (`plc`) graph (p=0.7) that is
  calibration-consistent under the bundled benchmark cutoff (current default
  implausibility I=1.25 < 3; see `CALIBRATION_REPORT.md`). Keep its tuned scale
  when comparing calibration scores.
- **Benchmark target sets** — `--benchmark default|twitter_like|facebook_like` /
  `RunConfig.benchmark`. Bundled *published aggregate* statistics (cited, no PII);
  affects calibration scoring only, not the event stream.
- **Moderation classifier** — `--classifier noise|trained` / `classifier_mode`.
  `noise` = calibrated noise model (default). `trained` = a real pure-numpy
  logistic-regression classifier (`content/ml_classifier.py`) trained on
  category-signal content with **measured** held-out precision/recall.
- **Dynamic social graph** — `--dynamic-graph` or `follow_rate` / `unfollow_rate`
  / `churn_rate`. Daily follow (triadic closure) / unfollow / churn, emitted as
  events, deterministic + bit-identically replayable. Default rates 0 = static.
- **Network models** — `graph_kind = ba | plc | ws | sbm`. `plc` (Holme–Kim) adds
  tunable clustering via triad prob `p`. Average clustering is exact for
  n≤5000, a deterministic sampled estimate above that.
- **Media synthesis** — `--media N` writes N real procedural PNG images plus one
  animated-PNG (APNG) video to `out/<run>/media/` (`content/media.py`, offline,
  zero-dep, deterministic). `set_image_backend()` plugs in an external model.
- **Distributed / GPU** — `--workers N` or `run_replicates(executor=...)` (any
  `concurrent.futures` executor: ProcessPool / Dask / Ray) for Monte Carlo;
  `accel.py` routes the classifier's training matmuls to CuPy when a GPU is
  present, else NumPy (GPU path is opt-in/unverified without a device).

## Replay & audit

Every run writes a manifest (config hash, root seed, package + policy-pack
versions, content mode, LLM cache hash). To verify:

```python
from socio_sim.logs.replay import verify
ok, msg = verify(manifest, original_stream_hash, run_fn)
```

Replays are bit-identical: same manifest -> same event-stream SHA-256. Event
logs are append-only JSONL with structured `decision_rationale` fields
(rule ids, scores, thresholds) — never chain-of-thought, never PII.

## LLM content adapters (optional)

The default `content_mode="template"` needs no LLM at all. Three optional
backends generate post text with an LLM; all of them cache responses by prompt
hash (so completed runs replay bit-identically offline) and degrade loudly to
template text on any failure — runs never fail silently.

### Free, keyless: local Ollama (recommended)

No API key, no account, no cost. Install Ollama, pull a small model, run:

```bash
# one-time setup
winget install Ollama.Ollama        # or download from https://ollama.com
ollama serve                        # starts local server on :11434
ollama pull qwen2.5:0.5b            # ~400MB; bigger models = better text
```

```python
cfg = RunConfig.quick(content_mode="ollama", llm_model="qwen2.5:0.5b",
                      llm_cache_path="out/llm_cache.json")
```

`llm_base_url` defaults to `http://localhost:11434`. Loopback LLM URLs are
accepted by default. Private/RFC1918 hosts must be explicitly allowed with
`SOCIOSIM_LLM_ALLOWED_HOSTS=host-or-ip` to avoid SSRF into corporate networks.
Recommended ≤1,000 agents with live generation (each post is one local
inference call).

### Free, keyless: any OpenAI-compatible local server

Works with LM Studio, llamafile, vLLM, or llama.cpp's server:

```python
cfg = RunConfig.quick(content_mode="openai_compatible",
                      llm_base_url="http://localhost:1234/v1",
                      llm_model="local-model")
```

### Anthropic Claude (needs a key)

```python
cfg = RunConfig.quick(content_mode="claude")
```

Requires `pip install -e .[llm]` and `ANTHROPIC_API_KEY`.
