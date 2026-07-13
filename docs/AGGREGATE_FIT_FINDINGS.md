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

## Second finding: against the corrected targets, the simulator does not fit

Running the `quick` profile (1,000 agents × 7 days, EU) against
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

**I = 6.03 is far outside the conventional 3σ history-matching cutoff.**
Stated plainly: *the simulator does not reproduce the real measured
aggregates it can be compared against.* Its graph is too heavy-tailed and
too sparse in triangles, its diurnal peak is three hours early, and in this
run no ad clicks and no appeal grants occurred at all.

This number is published rather than tuned away. The previous
`aggregate_matched_prototype` profile scored *below* the cutoff only because
it had been history-matched against the **unverifiable** targets; it is now
pinned to `legacy_unsupported_default` and explicitly does **not** claim
agreement with any verified measurement.

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
