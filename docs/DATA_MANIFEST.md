# Data Manifest & Governance

Every dataset SocioSim ships or calibrates against is recorded here with its
source, license/provenance, a **no-individual-level-data assertion**, and
redistribution basis. This is the gate for moving up the validation ladder
(`docs/usage.md`): any new dataset MUST be added here, satisfy the governance
rules below, and be license-clean and free of personal data before use.

## Governance rules (non-negotiable)
1. **Aggregate / public only.** No individual-level records, no PII, no content
   that could re-identify a person. Published aggregate statistics, synthetic
   data, or de-identified research datasets with explicit redistribution rights.
2. **No scraping.** Use sanctioned exports, official APIs, transparency-report
   downloads, or research datasets — never scraping (ToS / CFAA-adjacent risk).
3. **License recorded.** Each entry states its license and redistribution basis.
4. **Real platform microdata** (if ever needed) requires **DSA Art. 40 vetted-
   researcher** access or a formal data-use agreement — a governed, documented
   act, not an ad-hoc fetch. Such data is NOT bundled in this repo.
5. **Provenance flows through.** Outputs computed from a dataset carry a
   provenance label no stronger than the dataset warrants (see ladder below).

## Bundled datasets

| Dataset | Path | Content | Source / basis | PII? | License |
|---|---|---|---|---|---|
| Default benchmark targets | `socio_sim/data/benchmarks/default_targets.json` | ~7 aggregate target metrics (degree-tail, clustering, diurnal, posts/agent, ad CTR, appeal-grant) | Compiled from published aggregates (Barabási–Albert; Watts–Strogatz; circadian/transparency literature) — see `docs/RESEARCH_EVIDENCE.md` | **None** (aggregate point values + tolerances) | Project's own compilation of public figures (citations included) |
| Twitter-like targets | `socio_sim/data/benchmarks/twitter_like.json` | microblog aggregate targets | Kwak et al. 2010; Myers et al. 2014 (cited in file) | **None** | as above |
| Facebook-like targets | `socio_sim/data/benchmarks/facebook_like.json` | social-network aggregate targets | Ugander et al. 2011 (cited; degree-tail omitted — not power-law) | **None** | as above |

The benchmark *target* files above are **aggregate point targets with tolerances**
— zero record-level rows. Verified by `tests/test_validation.py` and packaged.

### Measured-classifier benchmarks (Rung 4 — real labeled text)
These power `run.py --measure-classifier` (real precision/recall/F1/ROC-AUC; see
`BENCHMARK_REPORT.md`). Both licenses permit redistribution + business/government
use. Text was **PII-scrubbed** (emails/URLs/phones/@handles redacted) on top of
each source's own de-identification, truncated to 400 chars, and a balanced
sample bundled (1,500 positive / 1,500 negative). Fetched once via the
HuggingFace Dataset Viewer API (official API, not scraping); provenance script:
`scripts/fetch_moderation_benchmarks.py`.

| Dataset | Path | Task | Source | License | PII? |
|---|---|---|---|---|---|
| Civil Comments | `socio_sim/data/benchmarks/moderation/civil_comments.jsonl.gz` | toxicity | Google/Jigsaw "Civil Comments" (`google/civil_comments`) | **CC0-1.0** (public domain) | De-identified comments; scrubbed; **no PII** |
| Spam detection | `socio_sim/data/benchmarks/moderation/spam_detection.jsonl.gz` | spam | `Deysi/spam-detection-dataset` | **Apache-2.0** | Short messages; scrubbed; **no PII** |

Licenses verified via the HF dataset API on insertion (`cardData.license` =
`cc0-1.0` / `apache-2.0`). SMS-Spam (UCI) was rejected during selection because
its HF license is `unknown` — it is **not** bundled.

## Candidate future datasets (NOT yet bundled — listed for governed addition)
| Dataset | Why | Governance to satisfy first |
|---|---|---|
| SNAP public network graphs (e.g. ego-Facebook, ego-Twitter) | Rung-3 structural backtest of degree/clustering distributions | de-identified + redistribution terms; add aggregate distributions only |
| EU DSA Transparency Database (aggregate CSV exports) | Rung-3 backtest of moderation/appeal time series | official export, aggregate; record license |
| A CC-licensed, de-identified toxic-comment benchmark | Rung-4 *measured* classifier F1/AUC on real text | re-identification review; redistribution rights; explicit user decision (currently declined — synthetic only) |

## Validation-ladder provenance labels
`synthetic-exploratory` < `uncalibrated` < `calibration-consistent` (I<3 vs
aggregates) < **`stylized-fact-validated`** (reproduces documented regularities)
< **`backtested-out-of-sample`** (held-out aggregates within tolerance) <
`measured-on-benchmark` (component measured on a real public dataset — gated by
the row above). No claim may exceed its label.
