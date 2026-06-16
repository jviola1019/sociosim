# SocioSim Usage

## Install

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (source .venv/bin/activate on POSIX)
pip install -e .[dev]
pytest                            # 110+ tests; -m "not slow" to skip stats tests
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
  replay toggle.
- **Network** — agent/tick overrides, topic count, graph model (BA / WS / SBM)
  and its parameters, homophily rewiring.
- **Content** — generator (template / local LLM), model, and per-category
  ground-truth prevalence sliders (hate, harassment, misinfo, fraud, adult,
  self-harm, illegal goods, AI-generated).
- **Moderation** — jurisdiction packs + FTC toggle, classifier precision/recall,
  human-review accuracy and delay, appeal grant rate.
- **Feed & Ads** — ranking strategy, EU opt-out, exploration ε, feed size,
  holdout fraction, frequency cap, disclosure compliance.
- **Red Team** — adversary toggles.

The simulation runs **only when Run Simulation is clicked**, after settings are
tuned. The engine runs in a background thread with a live progress meter
(`GET /api/job/<id>`); results render as a tabbed dashboard:

- **Overview** — metric cards with confidence-interval bars.
- **Feed** — a sampled slice of generated content, each post shown as a card with
  a **unique, deterministically generated cover image and avatar** (procedural SVG
  seeded by content id — offline, reproducible), persona, category tags, and the
  moderation action applied.
- **Charts** — diurnal posting, degree distribution, activity timeline, cascade
  sizes (hand-built SVG).
- **Fairness** (confusion grid + FPR/FNR by group), **Ads** (each campaign with a
  **unique generated ad creative** + lift/CTR table), **Calibration** (benchmark
  whisker plot), **Log** (full markdown report + manifest).

Outputs for each run are also written under `out/web/<timestamp>/`.

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
`holdout_fraction`, `ad_frequency_cap_per_day`, `graph_kind` (`ba|ws|sbm`),
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
from socio_sim.experiments.runner import compare
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
- `validation.sensitivity.first_order_indices` -> variance-based first-order
  sensitivity (Sobol-style approximation).

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

`llm_base_url` defaults to `http://localhost:11434`. Recommended ≤1,000 agents
with live generation (each post is one local inference call).

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
