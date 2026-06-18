# SocioSim — Design Document

Date: 2026-06-12
Status: Approved (clarifications resolved via Q&A; scale and architecture grounded in cited literature)
Requirements source: "SocioSim: A Rigorous Social-Interaction Simulator" specification (provided by user; referred to below as "the Spec")

## 1. Purpose and resolved clarifications (Spec §2)

| Question | Resolution |
|---|---|
| Purpose & scope | Both flagship uses: (a) moderation-policy stress tests across jurisdiction packs, (b) marketing/ad experiments with holdout measurement. |
| Jurisdictions | US (Section 230), EU (DSA), CN (AI-labelling measures), plus FTC endorsement-disclosure logic. All encoded as policy-as-code packs; active packs chosen per run config. |
| Calibration data | Built-in benchmark target sets encoding published, aggregated platform statistics (degree distributions, clustering, diurnal activity, engagement rates, ad CTRs), plus loaders so anonymised empirical datasets can replace them later. No real-person data is ever bundled or accepted at the individual level. |
| Scale & horizon | Standard profile: **10,000 agents × hourly ticks × 28 simulated days × 100 Monte Carlo replicates.** Quick profile: 1,000 agents × 7 days (dev/CI). With the live LLM adapter enabled, ≤1,000 agents recommended. All knobs configurable. |
| Persona diversity | Age group (minors flagged — drives DSA ad ban), 2-axis ideology, trust propensity, activity level (heavy-tailed), ad responsiveness, moderation attitude, influencer flag. Vulnerable-group flags supported for fairness diagnostics. |
| Experiment design | Baseline-vs-intervention scenario pairs sharing seed trees (common random numbers); randomised holdout groups for ad measurement. |
| Output metrics | Harmful-content exposure, moderation FP/FN rates, appeal volumes/outcomes, DSA-notice compliance, ad CTR/CVR/CPM/CPC/ROI, cascade sizes, welfare proxies (defined as: mean session satisfaction = engagement-weighted content affinity minus harmful-exposure penalty and fatigue), fairness disparities — all with 95% CIs. |
| Resources | Single laptop-class machine; speed achieved by vectorisation, not distribution. Python 3.11+. |

### Evidence base for scale defaults

- Group-level emergent phenomena require thousands of agents, and 100k-agent live-LLM runs took five A100 GPUs ~2 days in OASIS (arXiv:2411.11581) — so live-LLM generation cannot be the default engine; offline deterministic generation at 10k agents is the tractable sweet spot. S³ (arXiv:2307.14984) used reconstructed real networks of thousands of users.
- Canonical opinion-dynamics ABMs use N≈5,000 scale-free networks with hub cutoff k_max=√N; N=10⁴ yields hubs of degree ~100 (influencer dynamics representable).
- Circadian literature: posting peaks ~16–18h, troughs ~04–06h; hourly is the coarsest resolution capturing the cycle, and DSA 24-hour deadlines need sub-day ticks.
- Ad experimentation practice: ≥2 weeks, ≤~4 weeks, ≥1 full week for day-of-week effects; 80% power / 95% confidence standard → 28-day horizon, ≥100 replicates.

### Evidence base for architecture

Published framework benchmarks (Agents.jl comparison paper, SAGE Simulation 2024; FLAMEGPU ABM_Framework_Comparisons) show object-per-agent pure Python (Mesa) is the slowest mainstream approach, while columnar/vectorised agent storage (mesa-frames) achieves ~10× speedups at 10k+ agents with near-constant scaling. Compiled engines (Agents.jl, Rust) win raw speed but cost researcher accessibility and 3–5× build effort, targeting scales (100k+) we do not need. Decision: **modular Python package with columnar NumPy agent state**, per-event logic only where decisions are inherently per-item (policy, moderation, ads, logging).

## 2. Architecture

```
socio_sim/
  config.py        # Typed RunConfig; validation; profiles (standard, quick); config hash
  rng.py           # SeedSequence tree -> independent numpy Generators per module/replicate
  engine.py        # Hourly tick loop orchestrating all modules; emits events
  graph/           # Generators: Barabási-Albert, Watts-Strogatz, SBM, homophily mixing;
                   # metrics: degree dist, clustering, homophily index, churn
  agents/          # Persona sampling (columnar arrays); diurnal activity curve;
                   # belief state + Bayesian-style updates; fatigue
  content/         # ContentItem schema; TemplateGenerator (default, seeded);
                   # ClaudeAdapter (optional, response-cached for replay);
                   # NoisyClassifier with configurable precision/recall per category;
                   # CN synthetic-media labelling (explicit label + implicit metadata)
  feed/            # Strategies: chronological, personalized (weighted features),
                   # random baseline; epsilon-greedy bandit exploration;
                   # per-impression feature logging; EU non-personalised opt-out
  policy/          # Policy-as-code engine; RulePack YAML schema exactly per Spec §3.6
                   # packs: us_section230.yaml, eu_dsa.yaml, cn_ai_label.yaml, ftc.yaml
  moderation/      # Triggers (classifier, user flag); thresholds; escalation queue;
                   # simulated human review; appeals with outcomes and deadlines
  ads/             # Second-price auction; targeting constraints enforced via policy
                   # engine (minor/sensitive-data bans in EU mode); frequency caps +
                   # fatigue; FTC disclosure insertion w/ compliance toggle;
                   # holdout assignment; Beta-Binomial calibrated click/conversion
  analytics/       # Metrics with bootstrap + Monte Carlo percentile CIs;
                   # fairness diagnostics (FPR/FNR by group); report generation
  logs/            # Append-only JSONL event log; run manifest (config hash, seeds,
                   # versions, pack versions); replay verifier (event-stream hash)
  validation/      # Benchmark target sets; KS-distance scoring; history matching
                   # (implausibility); ABC rejection sampling; Sobol sensitivity
  experiments/     # Scenario definitions: baseline/intervention pairs, holdouts,
                   # Monte Carlo runner
tests/             # pytest unit tests per module + integration + determinism tests
data/benchmarks/   # Named target sets (published aggregate statistics, cited)
examples/          # Example configs + notebook-style demo scripts
docs/              # Usage, limitations, ethics, legal-compliance notes, NIST AI RMF map
```

### Data flow per tick
1. `agents` computes active agents (diurnal curve × activity propensity, vectorised).
2. Active agents act: post (via `content` generator), react, share. (Dynamic follow/unfollow and graph churn are NOT implemented in v1 — the social graph is static; see KNOWN_LIMITATIONS.md.)
3. `content` classifies new items (noisy classifier → category scores).
4. `policy` + `moderation` evaluate flagged/classified items → actions (label, downrank, remove, escalate, notify; appeals enqueued where allowed), all logged with rule_id and rationale.
5. `ads` runs auctions for eligible impression slots (respecting jurisdiction constraints + holdouts).
6. `feed` assembles each active agent's feed (strategy per config; ads interleaved).
7. Exposure → engagement sampling → belief/fatigue updates → events appended.

### Determinism & replay
- Single root seed → `numpy.random.SeedSequence` spawns one child per (module, replicate). No module shares a Generator.
- Run manifest records: config (canonical JSON + SHA-256), root seed, package version, policy pack versions, content-generator mode (+ LLM cache file hash if used).
- Replay = rerun from manifest; verifier asserts equality of the SHA-256 hash of the canonical event stream. LLM adapter writes a response cache on first run; replay reads the cache, guaranteeing bit-identical replays even with a live LLM.

### Error handling
- Config validated eagerly with explicit errors (no silent defaults beyond documented profile values).
- Policy engine fails closed: unmatched severe categories escalate to the human-review queue and log a `moderation` event with `rule_id: POLICY-GAP`; never silently pass. (A separate `policy_gap` event kind was considered but not used — the escalation is a `moderation` record.)
- LLM adapter failure → logged degradation event + fallback to TemplateGenerator for that call; run continues, manifest records the degradation.
- Logs are append-only; writer flushes per tick; partial-run logs remain readable.

## 3. Module design highlights

- **Policy rule schema (YAML)**: exactly the Spec §3.6 fields — `rule_id, jurisdiction, trigger, action, notice_required, appeal_allowed, deadline, evidence_threshold, log_required`. Engine composes by severity/priority; supports §230 Good-Samaritan mode (good-faith removals immune, criminal/IP carve-outs flagged), DSA mode (notices, appeals, easy flagging, non-personalised option, minor/sensitive-ad bans), CN mode (explicit + implicit AI labels; platforms add notices to unlabelled synthetic media; ≥6-month log retention flag).
- **Content**: v1 simulates media items as typed objects (`media_type`: text/image/video) with labelling metadata — no actual image/video generation. CN labelling logic operates on metadata fields (explicit_label, implicit_watermark: provider code + content reference number).
- **Classifier realism**: ground-truth categories assigned at generation; the NoisyClassifier corrupts them with configurable per-category precision/recall, producing genuine FP/FN dynamics whose costs are adjustable; confusion matrices reported.
- **Ads**: second-price auction per impression slot; advertisers as configured campaign objects with budgets, bids, targeting; RCT holdouts assigned at agent level per campaign; CTR/CVR posterior = Beta-Binomial updated against benchmark priors; all ad metrics reported with credible intervals.
- **Uncertainty**: Monte Carlo across replicates (parameter sets sampled from calibrated posteriors or priors); outputs reported as median + 2.5/97.5 percentiles; Sobol-style first-order sensitivity indices over a Latin-hypercube design (variance-based, per Spec §1).
- **Logging**: structured rationale fields only (`decision_rationale` = template-built short string with rule ids, thresholds, scores). Never chain-of-thought, never PII.

## 4. Ethics, safety, misuse prevention
- Research-only banner in README and run output; prohibited-use list per Spec (no targeting/ranking of real individuals, no protest prediction, no enforcement decisions).
- Personas are synthetic; benchmark targets are aggregate statistics only.
- Fairness diagnostics standard in every analytics report (moderation FP/FN by persona group).
- Red-team scenario library: spammer, brigading ring, misinfo amplifier, auction gamer, disclosure evader; shipped as experiment configs.
- NIST AI RMF mapping table in docs (Govern/Map/Measure/Manage → SocioSim features).

## 5. Testing strategy
- Unit tests per module (graph statistics, persona sampling distributions, rule-pack semantics per jurisdiction, auction correctness incl. second-price property, disclosure insertion, classifier noise rates, CI coverage of analytics).
- Integration: 200 agents × 48 ticks end-to-end smoke producing a valid manifest, logs, and report.
- Determinism: same seed → identical event-stream hash; different seed → different.
- Statistical (marked `slow`): generated graphs within KS tolerance of targets; diurnal activity matches curve; calibration loop reduces implausibility.

## 6. Out of scope for v1 (explicit)
- Real image/video synthesis (media simulated as typed objects with labelling metadata).
- Distributed/GPU execution.
- Bundled empirical datasets (loaders + named published aggregates only).
- Real moderation-model training; classifiers are calibrated noise models plus an interface for plugging real models in.

### Addendum (post-v1, delivered)
- **Web console** (`socio_sim/web/`, `python run.py --web`): a localhost
  browser dashboard over the same engine — Python stdlib server, no extra
  dependency. Originally scoped out (markdown reports only); added on request.
- **Free keyless LLM content** (`socio_sim/content/llm_adapter.py`): local
  Ollama / OpenAI-compatible backends, so live content generation needs no API
  key. Same caching + replay + loud-degradation guarantees as the Claude path.

## 7. Definition of done (mapped to Spec §3.12)
1. All modules above implemented with passing unit + integration tests.
2. Calibration loop (history matching + ABC) demonstrated against built-in benchmark targets with documented tolerances.
3. Monte Carlo + sensitivity analyses executed in the example experiment; 95% intervals in reports.
4. Replay verifier proves bit-identical reproduction from manifests.
5. Docs: usage, limitations, ethics, legal-compliance notes (DSA/§230/CN/FTC), NIST AI RMF map, residual-risk notes.
6. Red-team scenario configs run and reported.
