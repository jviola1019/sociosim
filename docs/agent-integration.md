# Agent Integration

LLM and content-generation integrations are optional presentation layers.

Requirements:

- Structured simulation state is the source of truth.
- LLM text cannot alter policy rules, scenario configuration, metrics, or event
  state.
- Cache generated outputs with provider/model/prompt/version/hash metadata.
- Scrub or reject generated text that contains PII, operational harm, evasion,
  real-person likeness, or unsafe instructions before rendering.
- Report degradation events when a backend fails and fall back to deterministic
  template content where possible.
