# Security Review

Baseline status:

- Localhost binding is the default.
- Non-loopback bind requires `SOCIOSIM_ACCESS_TOKEN` and allowed hosts.
- Host/origin checks, JSON content-type checks, body-size limits, CSP, static
  path containment, authenticated event-log export containment, and LLM URL SSRF
  checks exist.
- This remediation adds web scale limits, active-job rejection, and immediate
  LLM URL revalidation before outbound calls.

Remaining work:

- Add dependency scanning (`pip-audit` or equivalent) and static security scan.
- Harden Docker with pinned base image digest and non-root user.
- Add rate limiting, token rotation guidance, and TLS/reverse-proxy deployment
  guidance for remote use.
- Pin resolved LLM IPs during socket connection if remote private LLM endpoints
  are ever supported beyond local research use.
