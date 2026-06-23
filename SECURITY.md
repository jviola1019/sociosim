# Security Posture & Threat Model — SocioSim web console

SocioSim is a **single-user, localhost research tool**. The web console is a
Python stdlib (`http.server`) app serving a vanilla-JS UI over a JSON API. This
document states what is protected, how, and what is explicitly out of scope.
Grounded in OWASP Top 10 (2021), OWASP ASVS, the OWASP Secure Headers & SSRF
Prevention cheat sheets, and MDN security-header guidance (see
`docs/RESEARCH_EVIDENCE.md` Part B for citations).

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
| 1 | **Bind `127.0.0.1`** by default; warn on non-loopback bind | LAN/internet exposure (OWASP A05) | `serve()` / `run.py --bind` |
| 2 | **Per-session access token** (`secrets.token_urlsafe(32)`), required on state-changing POSTs, constant-time compare; served via same-origin `/api/meta` (cross-origin pages cannot read the response) | Browser CSRF / forged POSTs (A01) | `Handler._token_ok` |
| 3 | **Origin/Host allow-list** on POST (loopback only; foreign Origin → 403) | CSRF & **DNS-rebinding** (loopback is reachable from a browser page) | `Handler._origin_ok` |
| 4 | **Security headers** on every response: CSP (`default-src 'self'`, `frame-ancestors 'none'`, `base-uri 'none'`, `object-src 'none'`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` | XSS blast-radius, MIME sniffing, clickjacking (CWE-79/1021) | `Handler._security_headers` |
| 5 | **JSON body-size limit** (2 MB) + `Content-Type: application/json` required | Oversized-body DoS, type confusion (ASVS V5) | `Handler.do_POST` |
| 6 | **SSRF allow-list** on `llm_base_url`: http(s) only; resolve-then-validate; loopback/private hosts only; block link-local incl. cloud-metadata `169.254.169.254`, multicast, reserved | SSRF to internal/metadata services (A10 / CWE-918) | `_validate_llm_url` |
| 7 | **Path jail** on `/static/` (canonicalize + contain to dir) | Path traversal / symlink escape (CWE-22) | `safe_static_path` |
| 8 | No client input reflected into response headers | CRLF/header injection (stdlib caveat, bpo-32084) | response builders |

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
console beyond loopback and is supported only on a trusted host/container — the
access token and headers still apply but TLS and network ACLs become your
responsibility.

## Verification (Sprint 9)
- **No committed secrets** — full tracked-tree scan (api keys / tokens / passwords
  / private keys / AWS / `sk-`/`ghp_` patterns) finds only parameter names, env
  reads, and docs. The web access token is **runtime-generated**
  (`secrets.token_urlsafe(32)`), the Anthropic key is read from `ANTHROPIC_API_KEY`
  env only (never stored/committed), and no `.env`/`.pem`/credential files are
  tracked.
- **Accessibility (WCAG 2.1 / ADA):** `lang` set; every control has an accessible
  label (incl. prevalence sliders); images carry alt text; results region is
  `aria-live` + `role=status`; keyboard `:focus-visible` indicator on all
  interactive elements; reduced-motion fallbacks. Browser-verified.

## Reporting
This is research software (not production). For issues, open a GitHub issue;
do not include sensitive data (the simulator stores none — synthetic only).
