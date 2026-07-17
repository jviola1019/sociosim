# Aggregate-fit findings — source-verification pass, 2026-07-13

## What was done

Every numeric benchmark **target value** was checked against the primary
source it cited. Sources were read in full (PDF text extraction), not
recalled and not inferred from abstracts. Each surviving target now quotes
the exact sentence or table cell it came from in its
`statistic_location` field.

## Headline finding: the previous targets were not supported by their own citations

| Target | Old value | What the cited source actually says | Status |
|---|---|---|---|
| `degree_tail_exponent` | 2.5 | Barabási & Albert 1999 reports **γ_actor = 2.3 ± 0.1**; its exponents span **2.1–4**. The number 2.5 appears nowhere, and the familiar "2–3 for social networks" band is not in the paper. | **contradicted → corrected to 2.3 ± 0.1** |
| `clustering` | 0.2 (band "0.1–0.3") | Mislove et al. 2007 Table 4 measures **0.136–0.330** (Flickr 0.313, LiveJournal 0.330, Orkut 0.171, YouTube 0.136). No network measures 0.2, and two exceed the claimed upper bound. | **contradicted → corrected to 0.238 ± 0.098** |
| `clustering` (twitter set) | 0.1, cited to Kwak et al. 2010 | **Kwak et al. 2010 reports no clustering coefficient at all.** The citation did not contain the number. | **mis-attributed → removed** |
| `diurnal_peak_hour` | 16–18h ("circadian posting studies") | No defensible source found. The only match traces to a predatory-journal, five-day, COVID-keyword-filtered, timezone-unnormalised study. | **unsourced → replaced with Golder 2007 (20–21h)** |
| `ad_ctr` | 0.01 ("industry aggregates") | The only citable measurement (iPinYou RTB logs) reports **< 0.1 %** for 8 of 9 campaigns; the paper calls **0.1 % ≈ 0.001** the typical desktop-display average. | **contradicted → corrected to 0.001 ± 0.001** |
| `appeal_grant_rate` | 0.2–0.25 ("platform transparency reports") | YouTube's California AB 587 filing (H1 2024): **82,190 reinstatements / 745,707 appeals = 11.0 %** (6.0–14.8 % across policy areas). | **contradicted → corrected to 0.110 ± 0.044** |
| `posts_per_agent_day` | 0.5 ("median platform posting rates") | Pew 2019: the **median** user posts ~2 tweets/month ≈ **0.066/day**. 0.5 is defensible only as a **derived mean** over a heavily skewed distribution. | **justification wrong → kept as 0.51, relabelled a derived mean** |

The unverifiable sets are retired to
`socio_sim/data/benchmarks/legacy_unsupported_*.json`. They keep
`kind: unsupported` evidence, are excluded from the default, and remain
loadable by explicit name only so older runs can still be reproduced.

## Second finding: the BASE model does not fit; a history-matched profile does

**Base / `quick` profile** (1,000 agents × 7 days, EU, no matching) against
`sourced_aggregates_v1`:

```
Implausibility I = 6.03  (dominant: degree_tail_exponent; cutoff 3.0)

metric                     observed     target      tol       z
degree_tail_exponent         2.9029     2.3000   0.1000    6.03
clustering                   0.0385     0.2380   0.0980    2.04
diurnal_peak_hour           17.0000    20.0000   1.0000    3.00
diurnal_trough_hour          4.0000     5.5000   2.5000    0.60
posts_per_agent_day          0.5247     0.5100   0.2500    0.06
ad_ctr                       0.0000     0.0010   0.0010    1.00
appeal_grant_rate            0.0000     0.1100   0.0440    2.50
```

I = 6.03 is far outside the cutoff: the default preferential-attachment
graph is too heavy-tailed (γ→3) and too sparse in triangles, and its diurnal
peak is three hours early. **This base number is published, not tuned away.**

**History-matched profile** (`aggregate_matched_prototype`, 2026-07-14).
History matching = move MODEL parameters to minimise the target distance;
no target value or tolerance was touched. The parameters, each a principled
mechanism:

| Parameter | Set to | Why (mechanism) |
|---|---|---|
| `graph_kind` | `cm` (config model, γ_seq = 2.05) | Reproduces a specified degree exponent; preferential attachment asymptotes to 3 and cannot reach 2.3. Multi-edge collapse steepens the realized tail, so a sequence exponent of 2.05 yields an observed ~2.31. |
| `triangle_swaps` | 15 × \|E\| | Degree-preserving triangle-forming swaps inject clustering without changing the tail. |
| `homophily_rewire_fraction` | 0.0 | Homophily rewiring perturbs degrees and flattens the matched tail. |
| `diurnal_peak_shift` | 3 h | Aligns the activity peak with the source-checked Golder 2007 evening peak (~20h). |
| `campaign_ctr_multiplier` | 0.09 | Lowers the demo-ad CTR toward the source-checked display-ad measurement (iPinYou ~0.001) instead of the unsourced 0.012 assumption. |

Result (seed 42, deterministic, replay-verified):

```
Implausibility I = 2.50  (dominant: appeal_grant_rate; cutoff 3.0)

metric                     observed     target      tol       z
degree_tail_exponent         2.3145     2.3000   0.1000    0.14   in band
clustering                   0.3023     0.2380   0.0980    0.66   in band
diurnal_peak_hour           20.0000    20.0000   1.0000    0.00   in band
diurnal_trough_hour          7.0000     5.5000   2.5000    0.60   in band
posts_per_agent_day          0.5026     0.5100   0.2500    0.03   in band
ad_ctr                       0.0000     0.0010   0.0010    1.00   edge
appeal_grant_rate            0.0000     0.1100   0.0440    2.50   out of band
```

**I = 2.50, under the 3σ cutoff.** The STRUCTURAL graph and temporal
aggregates -- the properties a social-network model should reproduce -- all
land in band. The two residuals are `ad_ctr` (at the tolerance edge) and
`appeal_grant_rate` (out of band): their real sources are incompatible
surfaces (2013 China desktop-display RTB; one platform's 2024 video
appeals) and both are small-count in a single run, so they sit near the edge
rather than being genuinely reproduced.

### What a pass here does and does NOT mean

Being under the cutoff is a statement about ONE explicitly-labelled,
history-matched configuration reproducing SEVEN aggregate statistics to
within their (untouched) tolerances. It is **not** validation, calibration,
realism, or a prediction of any real platform:

- the targets are drawn from mutually incompatible populations (2007 actor
  collaboration graph; 2007 Flickr/LiveJournal crawls; 2006 US college
  Facebook; 2013 China display RTB; 2024 YouTube appeals) and definitions
  (Mislove's clustering is directed; the simulator's is undirected);
- the degree exponent and CTR were matched by SETTING a parameter to the
  target regime -- reproducing a stylized fact, not discovering it;
- the base model (no matching) still scores I ≈ 6.

Every target keeps its `applicability_limits`, and the comparison remains an
aggregate-fit DIAGNOSTIC.

## Third finding (2026-07-16): the seed-42 result does NOT generalize across seeds

The I = 2.50 above is ONE realization (root seed 42 — the seed the matching
pass used). A stochastic simulator cannot claim "matched" on one draw, so a
seed-generalization protocol was added
(`socio_sim/validation/seed_protocol.py`, evaluated by
`scripts/seed_protocol_eval.py`, committed artifact
`socio_sim/data/seed_protocol_results_v1.json`):

- **20 fitting seeds** (42 + reserved seeds parameters MAY be tuned on),
- **20 validation seeds** (generalization checks during tuning),
- **20 LOCKED holdout seeds** (hash-pinned; never used for any parameter
  decision — the profile parameters were frozen before these seeds were
  first evaluated, and that attestation is recorded in the artifact).

Every run is replay-verified. Results (implausibility I, cutoff 3.0):

| group | median | mean | p5 | p25 | p75 | p95 | max | pass (<3) | Wilson 95% |
|---|---|---|---|---|---|---|---|---|---|
| fitting seeds (20) | 2.50 | 3.05 | 1.25 | 2.41 | 2.86 | 5.80 | 10.77 | 15/20 = 75% | [0.53, 0.89] |
| validation seeds (20) | 2.50 | 3.10 | 1.07 | 2.03 | 3.18 | 7.56 | 10.49 | 11/20 = 55% | [0.34, 0.74] |
| **holdout seeds (20)** | **2.50** | **2.89** | 1.99 | 2.50 | 3.26 | **4.64** | **5.08** | **12/20 = 60%** | [0.39, 0.78] |

Per-metric failure rates on the holdout seeds (fraction of seeds with
z ≥ 3): appeal_grant_rate 30%, ad_ctr 5%, clustering 5%,
degree_tail_exponent 5%, diurnal peak/trough and posting volume 0%.
All 60 runs replayed byte-identically; no runtime failures.

**Acceptance verdict: FAILED.** The provisional criteria require ≥80% of
locked holdout seeds under the cutoff; the observed rate is 60%
(median 2.50 does pass; no structural metric fails in >20% of seeds; all
replays pass). Per protocol, no target value or tolerance was touched and
no parameter was retuned on holdout results. Instead the label is
downgraded: the profile is the **seed-42 aggregate demonstration
profile** — a demonstration that these mechanisms CAN reach the target
regime on the fitting seed, not a distributionally matched model.

Why it fails: the dominant failures are the small-count behavioural rates.
`appeal_grant_rate` is a handful of appeals per run, so its observed rate
jumps between 0 and 0.25 across seeds (z 2.05–3.18 straddling the cutoff),
and a couple of chance ad clicks push `ad_ctr` far past its ±0.001
tolerance (z up to 7.4 on one fitting seed). The structural graph/temporal
aggregates are stable across seeds — exactly what the per-metric table
shows. Fixing this honestly requires larger runs or mechanism work, not
wider tolerances.

## Fourth finding (2026-07-17): the failing rates are not statistically estimable at this scale

Event-support measurement on FITTING and VALIDATION seeds only (the locked
holdout stayed untouched; seeds 42, 101–103, 201–204):

| rate | events per run (measured) | needed for the 95% interval at the target rate to be as tight as the tolerance |
|---|---|---|
| `appeal_grant_rate` (target 0.110 ± 0.044) | **3–12 appeals filed**, 0–2 granted | **≥195 appeals** |
| `ad_ctr` (target 0.001 ± 0.001) | **119–451 impressions**, 0–1 clicks | **≥3,838 impressions** |

A single chance event moves either observed rate by several tolerances
(one click at 119 impressions = CTR 0.0084 → z = 7.4 — exactly the
outlier the multi-seed distribution showed). An ordinary z-distance is not
meaningful at this event support, so:

- every run now carries a **support record** per rate
  (`socio_sim/validation/support.py`, surfaced in the web payload and the
  Target Comparison tab): numerator, denominator, effective sample size,
  zero-denominator indicator, Wilson-95 interval, minimum-support
  threshold, and an acceptance-inclusion flag with rationale;
- **protocol v1 is untouched**: its committed verdict (holdout FAILED,
  60% pass) keeps both rates in its score exactly as evaluated;
- **protocol v2 is PREDECLARED, not evaluated**
  (`seed_protocol.PROTOCOL_V2`): acceptance on the five structural
  metrics only; both sparse rates demoted to descriptive diagnostics with
  mandatory support records; a brand-new hash-pinned holdout seed list
  (17001–17020, disjoint from every v1 list) that has never been run.
  Whether the profile passes v2 is unknown until a future evaluation —
  nothing here re-scores v1.

## What this does and does not license

- It **does** support: aggregate-fit diagnostics; sensitivity and mechanism
  analysis; scenario exploration under stated assumptions.
- It **does not** support: validation, calibration, realism, backtesting, or
  prediction of any real platform — and now there is a measured number
  (I ≈ 6) making that concrete rather than rhetorical.
- Even a *good* fit would not license those claims: the sourced targets
  measure different populations (2006 US college students; 2007 Flickr/
  LiveJournal crawls; 2013 Chinese display RTB; 2024 YouTube appeals),
  different metric definitions (Mislove's clustering is **directed**; the
  simulator's is undirected), and different periods. Each target carries its
  own `applicability_limits`.
