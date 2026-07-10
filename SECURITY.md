# Security Posture & Threat Model — SocioSim web console

SocioSim is a **single-user, localhost research tool**. The web console is a
Python stdlib (`http.server`) app serving a vanilla-JS UI over a JSON API. This
document states what is protected, how, and what is explicitly out of scope.
Grounded in OWASP Top 10 (2021), OWASP ASVS, the OWASP Secure Headers & SSRF
Prevention cheat sheets, and MDN security-header guidance (framework names
cited inline below; this repo bundles no copies of those documents).

## Assets
- Simulation configuration and results; the served console (HTML/JS/CSS).
- The optional local LLM endpoint (`llm_base_url`) and the host on which it runs.
- The host filesystem reachable by the process; process availability.

## Trust boundaries
1. Browser ↔ loopback HTTP server.
2. Server ↔ user-supplied `llm_base_url` (outbound request).
3. Server ↔ filesystem (static assets, run store).

## Controls (implemented)
| # | Control | What it stops | Where |
|---|---------|---------------|-------|
| 1 | **Bind `127.0.0.1`** by default; require explicit token + allowed hosts on non-loopback bind | LAN/internet exposure (OWASP A05) | `serve()` / `run.py --bind` |
| 2 | **Per-session access token** (`secrets.token_urlsafe(32)`), required on state-changing POST/DELETE and protected GETs whenever the auto-token is not exposed, constant-time compare; served via same-origin `/api/meta` **only when bound to loopback AND no `SOCIOSIM_ACCESS_TOKEN` is configured** — setting the env var means the operator supplies the token out-of-band (e.g. a reverse-tunneled loopback console) and it is never auto-revealed; remote exports use headers, not query-token URLs | Browser CSRF / forged mutation / token leakage (A01) | `Handler._token_ok`, `serve()` `expose_token` |
| 3 | **Host allow-list on every route** plus Origin/Referer allow-list on mutations (loopback by default; foreign Host/Origin → 403) | CSRF & **DNS-rebinding** (loopback is reachable from a browser page) | `_host_allowed`, `Handler._origin_ok` |
| 4 | **Security headers** on every response: CSP (`default-src 'self'`, `frame-ancestors 'none'`, `base-uri 'none'`, `object-src 'none'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` | XSS blast-radius, MIME sniffing, clickjacking (CWE-79/1021) | `Handler._security_headers` |
| 5 | **JSON body-size limit** (2 MB), valid non-negative `Content-Length`, and `Content-Type: application/json` required | Oversized-body DoS, malformed-body hangs/crashes, type confusion (ASVS V5) | `Handler.do_POST` |
| 6 | **SSRF allow-list with IP pinning** on `llm_base_url`: http(s) only; loopback by default; private/RFC1918 hosts require explicit `SOCIOSIM_LLM_ALLOWED_HOSTS`; block link-local incl. cloud-metadata `169.254.169.254`, multicast, reserved. The allow-list check runs on every transport call and returns the exact IP it checked; the TCP connection is made to **that pinned IP** (original hostname kept for the Host header and TLS SNI/certificate checks), so no second DNS lookup exists for a rebinding server to exploit. Any 3xx response is a hard error, never followed | SSRF to internal/metadata services incl. DNS-rebind TOCTOU (A10 / CWE-918) | `validate_llm_url`, `_PinnedHTTP(S)Connection` |
| 7 | **Path jail** on `/static/` (canonicalize + contain to dir) | Path traversal / symlink escape (CWE-22) | `safe_static_path` |
| 8 | No client input reflected into response headers | CRLF/header injection (stdlib caveat, bpo-32084) | response builders |

## LLM response-cache trust model (summary)

Cached LLM responses are tamper-evident records: `record_hash` binds
text + status + reason codes + guard version, and both adapters share one
decision module (`socio_sim/content/llm_cache.py`). A `status: "blocked"`
entry is never served as content; an `accepted` entry is served only while
its stored guard version matches the current one, so tightening the
semantic guard re-screens previously accepted text too. Legacy entries
(pre-schema) are treated as cache misses and re-screened. Full rules in
the module docstring.

## Threats → mitigations (STRIDE)
- **Spoofing / Elevation (CSRF, DNS-rebinding):** access token + Origin/Host check + loopback bind (controls 1–3).
- **Tampering / Info disclosure (XSS, traversal, MIME):** CSP + `nosniff` + output escaping in the JS + path jail (4, 7).
- **SSRF via `llm_base_url`:** scheme/host allow-list, resolve-then-validate, metadata block (6).
- **DoS:** body-size limit + content-type gate (5); runs execute in background threads.
- **Clickjacking:** `frame-ancestors 'none'` / `X-Frame-Options: DENY` (4).

## Explicitly out of scope (single-user localhost research tool)
Multi-tenant authN/authZ, TLS/cert management (loopback only), enterprise
rate-limiting/WAF, secrets-vault integration, full audit-logging/SIEM, and
dependency supply-chain attestation. Running with `--bind 0.0.0.0` exposes the
console beyond loopback and is supported only with `SOCIOSIM_ACCESS_TOKEN`,
`SOCIOSIM_ALLOWED_HOSTS`, and trusted network controls. The built-in token is not
a substitute for enterprise authentication, and **there is no TLS in this
stack: on any non-loopback bind the token travels as a cleartext HTTP
header — put a TLS-terminating reverse proxy in front on untrusted
networks** (the server prints this warning at startup).

## Verification (Sprint 9)
- **No committed secrets** — full tracked-tree scan (api keys / tokens / passwords
  / private keys / AWS / `sk-`/`ghp_` patterns) finds only parameter names, env
  reads, and docs. The web access token is **runtime-generated**
  (`secrets.token_urlsafe(32)`), the Anthropic key is read from `ANTHROPIC_API_KEY`
  env only (never stored/committed), and no `.env`/`.pem`/credential files are
  tracked.
- **Accessibility (WCAG 2.1 / ADA-oriented):** `lang` set; every control has an
  accessible label (incl. prevalence sliders); sliders expose `aria-valuetext`;
  images carry alt text; results region is `aria-live` + `role=status`; keyboard
  `:focus-visible` indicator on all interactive elements; history is a modal
  dialog with Escape/focus trapping; reduced-motion fallbacks; light-theme
  secondary text meets contrast targets. Browser-verified, and CI runs an
  automated axe-core gate (`tests/test_a11y_axe.py`) failing on any
  serious/critical WCAG 2.0/2.1 A+AA violation on the initial and rendered
  views (an automated-scan result, not a WCAG-AA conformance claim).

## Reporting
This is research software (not production). For issues, open a GitHub issue;
do not include sensitive data (the simulator stores none — synthetic only).
