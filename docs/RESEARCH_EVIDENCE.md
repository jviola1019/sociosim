# Research Evidence Base (Sprint 5)

Authoritative, cited grounding for the marketing suite, moderation/settings, and
web-app security. Compiled from a structured literature/standards review (June
2026; ~130 distinct sources across the two parts). **Caveat:** platform
transparency numbers are self-reported and not independently audited; KPI
"benchmarks" vary by industry/channel/year. Treat all figures as *sweepable
scenario anchors with provenance*, not ground truth — consistent with the
simulator's research-only, projections-not-predictions posture.

---

## Part A — Advertising measurement & marketing science

**Headline findings**
- **RCTs are the causal ground truth; observational/last-touch attribution is
  unreliable** — in half of 15 large Facebook field experiments the
  observational estimate was off by ~3× and generally *overstated* effectiveness.
  Gordon, Zettelmeyer, Bhargava & Chapsky (2019), *Marketing Science* 38(2)
  https://www.kellogg.northwestern.edu/faculty/gordon_b/files/fb_comparison.pdf ;
  confirmed against double-ML in Gordon, Moakler & Zettelmeyer (2023).
- **Ghost ads** beat PSA/ITT holdouts for measuring lift. Johnson, Lewis &
  Nubbemeyer (2017), *JMR* 54(6) https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2620078
- **Powering an ad RCT is hard** — sales CV≈10; median ROI CI >100pp; informative
  tests can need >10M person-weeks. Lewis & Rao (2015), *QJE* 130(4)
  https://gwern.net/doc/economics/advertising/2015-lewis.pdf
- **CUPED** cuts variance ~50% (covariate adjustment). Deng, Xu, Kohavi & Walker
  (2013), *WSDM*.
- **Peeking inflates false positives**; use always-valid/mSPRT or pre-committed
  group-sequential boundaries. Johari, Pekelis & Walsh (2015/2022), arXiv:1512.04922.
- **MMM is weakly identified**; use Bayesian informative priors and calibrate to
  experiments; triangulate MMM + experiments + attribution. Chan & Perry (2017),
  Jin et al. (2017), Google Research; IPA triangulation.
- **Newcombe** difference-of-proportions CI + **Benjamini–Hochberg** FDR are the
  recommended interval/multiple-testing methods. Newcombe (1998) *Stat. Med.*
  17(8); Benjamini & Hochberg (1995) *JRSS-B* 57(1).

**Standards / brand safety**
- **MRC viewability:** display ≥50% pixels ≥1s; video ≥50% ≥2s; large display
  (>242k px) ≥30% ≥1s. MRC Viewable Ad Impression Guidelines.
- **IAB Tech Lab Content Taxonomy 3.x** (4-tier) for contextual + brand-safety mapping.
- **WFA/GARM Brand Safety Floor + Suitability** — 11 categories (+Misinformation),
  High/Med/Low risk tiers, + Adjacency Standards (Feed/Stories/In-stream/Display).
  GARM disbanded Aug 2024; frameworks persist as de-facto standard.

**Recommended defaults (marketing)** — value · source

| Decision | Recommended | Source |
|---|---|---|
| Causal method | RCT holdout (ghost ads); not last-touch | Gordon 2019; Johnson 2017 |
| Difference CI | Newcombe score-hybrid | Newcombe 1998 |
| Variance reduction | CUPED (~50%) | Deng 2013 |
| Power / α | 80% power, α=0.05 two-sided | Cohen 1988 |
| MDE | set pre-launch; power smallest actionable lift | Lewis & Rao 2015 |
| Holdout fraction | 10% default; 10–20% preferred; 20–50% low base rate — **derive from power calc** | Meta CL (secondary) |
| Continuous monitoring | always-valid / mSPRT, not fixed-horizon | Johari 2015/2017 |
| Multiple testing | Benjamini–Hochberg FDR | B&H 1995 |
| Effective frequency | ~3 (disputed 1–3); cap 3–7/user/window | Krugman 1972; Naples/ARF 1979 |
| ROAS benchmark | "good" 2:1–4:1; median e-comm ~2:1 — **set by margins** | Triple Whale/WebFX (secondary) |
| LTV:CAC | ≥3:1 (best ~5:1); CAC payback <12mo — **lifecycle-dependent** | Skok ~2010 |
| Drivers of incremental sales | creative ~49%, brand ~21%, reach ~14%, targeting ~11%, recency ~5% | NCSolutions/ARF 2023 |

*The suite's existing stack (organic-baseline RCT holdout + Newcombe CI + CUPED +
two-proportion p + BH-FDR + MDE/power) is well-aligned with this literature.*

---

## Part B — Moderation/settings grounding + web-app security

**Regulatory frameworks (encode in presets)**
- **EU DSA** Reg. (EU) 2022/2065 — Art. 16 notice&action, Art. 17 statement of
  reasons, Art. 20 internal appeals (≥6 months; not solely automated), Art. 22
  trusted-flagger priority, Art. 40 vetted-researcher data access.
  https://eur-lex.europa.eu/eli/reg/2022/2065/oj/eng
- **US §230** (47 U.S.C. §230) — (c)(1) publisher immunity, (c)(2) Good Samaritan,
  carve-outs (federal crime, IP, ECPA, FOSTA-SESTA sex-trafficking).
- **China** AI-content labelling (CAC, eff. 2025-09-01; GB 45438-2025) — explicit
  + implicit labels; builds on Deep Synthesis Provisions (2023).
- **US FTC** 16 CFR Part 255 endorsements (rev. 2023) + Part 465 fake-reviews rule
  (eff. 2024-10-21); clear & conspicuous disclosure of material connections.
- **NIST AI RMF 1.0** (Govern/Map/Measure/Manage) + Generative AI Profile (AI 600-1).

**Settings ranges (transparency reports + academic; treat as sweepable anchors)**

| Setting | Default | Sweep range | Anchor |
|---|---|---|---|
| Proactive-detection rate | 0.95 | 0.90–0.99 | Meta/TikTok/YouTube reports |
| Classifier precision (hate) | 0.85 | 0.77–0.92 | arXiv 2505.18927 / CoPE |
| Classifier recall (hate) | 0.85 | 0.72–0.93 | same |
| Human-review accuracy (IAA) | 0.78 | 0.70–0.85 | summarize-from-feedback; Sigma |
| Appeal reversal rate | 0.20 | 0.002 (X) – 0.30 (DSA-wide) | ITIF/DSA; X report |
| Hate-speech prevalence | 0.0002 | 0.0001–0.0003 | Meta CSER |
| Overall removal share | 0.01 | <0.01–0.02 | Meta/TikTok |
| Appeal window | 180 days | ≥180 (legal floor) | DSA Art. 20 |
| Exploration ε | 0.05 | 0.01–0.10 | bandit/recsys lit |
| Homophily strength | 0.6 | 0.3–0.8 | echo-chamber lit |
| Ad/promo frequency | 1 in 6 | 1 in 4–10 | industry practice |

*Prevalence ordering to model: spam ≫ fake accounts > hate ≈ harassment > misinfo
> self-harm ≈ CSAM (rare-but-severe).*

**Web-app security (localhost research tool) — the 4 cheapest high-impact controls**
1. **Bind 127.0.0.1** (loopback isolation) — default. OWASP A05.
2. **Access token + Origin/Host check** — defeats browser CSRF & DNS-rebinding
   (loopback is reachable from a browser page). OWASP A01; ASVS V2/V4.
3. **Security headers** — CSP `default-src 'self'; frame-ancestors 'none'; base-uri
   'none'; object-src 'none'`, `X-Content-Type-Options: nosniff`,
   `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`. MDN; OWASP Secure Headers;
   CWE-79/1021.
4. **SSRF allow-list on the LLM `base_url`** — scheme+host+port allow-list,
   resolve-then-validate, block cloud metadata (169.254.169.254), no cross-host
   redirects. OWASP SSRF Cheat Sheet; CWE-918.
Plus: JSON body-size limit + `Content-Type` check (ASVS V5, DoS); never reflect
client input into headers (stdlib CRLF caveat, bpo-32084); path jail (CWE-22, done).

**Threat model (STRIDE):** assets = sim data/config, served console, local LLM
endpoint, filesystem, availability. Primary threats: CSRF/DNS-rebinding from a
browser page hitting loopback (→ token + Origin check); XSS/clickjacking (→ CSP +
XFO); SSRF via `base_url` (→ allow-list); DoS via oversized JSON (→ body limit).
Out of scope (single-user localhost): multi-tenant authz, TLS, WAF, SIEM.

**Key disagreements flagged** (both parts): observational-vs-experiment adequacy
(experiments win); classifier "solved" myth (F1≈0.9 collapses on implicit/long-tail);
holdout/ROAS/effective-frequency are context-dependent, not constants; platform
self-reported numbers are unaudited; "loopback is safe" is only partial (browser
can still reach 127.0.0.1).

*(Full per-claim citations — ~130 sources — were gathered in the Sprint-5 review;
the highest-value primary sources and standards bodies are listed inline above.)*
