# Legal Compliance Mapping (research approximation — not legal advice)

How policy packs implement each regime (Spec §1, §3.6). Rules live in
`socio_sim/policy/packs/*.yaml`; every applied rule logs its `rule_id`,
thresholds, and a structured rationale for audit.

## US — Section 230 (`us_section230.yaml`)

| Obligation | Implementation |
|---|---|
| Good-Samaritan immunity for good-faith removal of objectionable content | `US-230-GS-1`: removals of hate/harassment/adult/misinfo/self-harm carry `immunity: good_samaritan`; no notice/appeal mandated federally |
| No immunity for federal criminal / IP / privacy matters | `US-230-CRIM-1/2`: illegal-goods & fraud removals + mandatory escalation, 24h deadline, mandatory logging |

## EU — Digital Services Act (`eu_dsa.yaml`)

| Obligation | Implementation |
|---|---|
| Transparency: notice to user on removal, with reasons | `notice_required: true` on removals; `notice` events; report tracks removal-notice coverage |
| Appeals / internal complaint handling | `appeal_allowed: true`; appeal queue with resolution events and grant rates |
| Easy flagging of illegal content | user `flag` events trigger `EU-FLAG-1` escalation with 48h deadline |
| Illegal-content removal deadlines | `EU-ILLEGAL-1` 24h deadline; deadline misses measured |
| Non-personalised feed option | `eu_optout_rate` agents always receive chronological feeds |
| No targeted ads to minors | `EU-ADS-MINOR-1` blocks ad auctions for minor agents |
| No ads based on sensitive data | `EU-ADS-SENS-1`: sensitive targeting keys (ideology, health, religion, sexuality) stripped |

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
| Material-connection disclosure on sponsored content | creatives carry `#ad (paid partnership)` when compliant; `FTC-DISC-1` inserts missing disclosures and flags `ftc_violation` |
| Testing non-compliance counterfactuals | `ftc_compliance` config toggle + per-campaign `ftc_override` (e.g. the `disclosure_evader` scenario) |

## Fail-closed floor

Severe categories (self-harm, illegal goods) that match no active rule always
escalate with `rule_id: POLICY-GAP` — content never silently passes because a
pack is missing or misconfigured.
