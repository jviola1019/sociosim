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

All bundled data are **aggregate point targets with tolerances** — there are zero
record-level rows. Verified by `tests/test_validation.py` and packaged into the
wheel (`tests`/CI assert their presence).

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
