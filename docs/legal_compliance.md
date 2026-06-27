# Legal Compliance Mapping (research approximation — not legal advice)

How policy packs implement each regime (Spec §1, §3.6). Rules live in
`socio_sim/policy/packs/*.yaml`; every applied rule logs its `rule_id`,
thresholds, and a structured rationale for audit.

## US — Section 230 (`us_section230.yaml`)

| Source anchor | Simulator operationalization | Uncertainty |
|---|---|---|
| Good-Samaritan immunity for good-faith removal of objectionable content | `US-230-GS-1`: removals of hate/harassment/adult/misinfo/self-harm carry `immunity: good_samaritan`; no notice/appeal mandated federally | Section 230 immunizes some platform moderation choices; it does not require moderation. |
| Federal criminal / IP / privacy carve-outs | `US-230-CRIM-1/2`: illegal-goods & fraud removals plus escalation, deadline tracking and logging | The modelled 24h escalation clock is a simulator assumption, not a Section 230 statutory deadline. |

## EU — Digital Services Act (`eu_dsa.yaml`)

| Source anchor | Simulator operationalization | Uncertainty |
|---|---|---|
| Transparency: notice to user on removal, with reasons | `notice_required: true` on removals; `notice` events; report tracks removal-notice coverage | Research approximation; not legal advice. |
| Appeals / internal complaint handling | `appeal_allowed: true`; appeal queue with resolution events and grant rates | Appeal outcomes are synthetic scenario parameters. |
| Easy flagging of illegal content / trusted flaggers | user `flag` events trigger `EU-FLAG-1` escalation with a modelled 48h review clock | DSA requires timely/diligent handling; 48h is a simulator setting. |
| Illegal-content action | `EU-ILLEGAL-1` uses a modelled 24h clock; deadline misses measured | The DSA does not create a universal 24h removal deadline. |
| Non-personalised feed option | `eu_optout_rate` agents always receive chronological feeds | Simplifies product-specific recommender choices into one opt-out share. |
| No targeted ads to minors | `EU-ADS-MINOR-1` blocks ad auctions for minor agents | The statute targets profiling-based ads; modelled as a hard ad block. |
| No ads based on sensitive data | `EU-ADS-SENS-1`: sensitive targeting keys (ideology, health, religion, sexuality) stripped | Mapping of special-category data to synthetic fields is approximate. |

## CN — AI-content labelling measures (`cn_ai_label.yaml`)

| Obligation | Implementation |
|---|---|
| Explicit labels on AI-generated content | compliant creators set `explicit_label` + visible text notice |
| Implicit metadata watermarks | `implicit_watermark = {provider, content_ref}` on synthetic items |
| Platform must detect & label unlabeled synthetic content | `CN-AI-LABEL-1`: watermark/classifier detection -> `add_platform_label` + conspicuous notice |
| Log retention ≥ 6 months | `retention_months: 6` recorded on labelling decisions |

## US — FTC Endorsement Guides (`ftc.yaml`)

| Obligation | Implementation |
|---|---|
| Material-connection disclosure on sponsored content | creatives carry `#ad (paid partnership)` when compliant; `FTC-DISC-1` models a simulator intervention that inserts missing disclosures and flags `ftc_violation` rather than describing an FTC remedy |
| Testing non-compliance counterfactuals | `ftc_compliance` config toggle + per-campaign `ftc_override` (e.g. the `disclosure_evader` scenario) |

## Fail-closed floor

Severe categories (self-harm, illegal goods) that match no active rule always
escalate with `rule_id: POLICY-GAP` — content never silently passes because a
pack is missing or misconfigured.
