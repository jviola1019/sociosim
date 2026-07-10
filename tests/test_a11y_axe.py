"""Automated accessibility gate (audit G-02): axe-core scans the dashboard
and fails on any serious/critical violation.

Scope honesty: axe-core checks only machine-checkable WCAG rules (roughly a
third of the success criteria), so a passing scan is an automated-scan
result, NOT a WCAG-AA conformance claim. The manual keyboard/contrast/ARIA
pass is recorded in SECURITY.md. Two states are scanned: the initial
configuration view and the rendered results view after a real (tiny)
simulation. Skipped automatically where Playwright/Chromium or
axe-playwright-python isn't installed; CI installs both (ci.yml).
"""

import socket
import threading
from http.server import ThreadingHTTPServer

import pytest

sync_playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright not installed").sync_playwright
Axe = pytest.importorskip(
    "axe_playwright_python.sync_playwright",
    reason="axe-playwright-python not installed").Axe

from socio_sim.web import app  # noqa: E402

#: Gate on the WCAG 2.0/2.1 A+AA rule tags; violations of other best-practice
#: rules are reported but do not fail the build.
_AXE_OPTIONS = {
    "runOnly": {"type": "tag",
                "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]},
    "resultTypes": ["violations"],
}

_RUN_AND_RENDER = """async () => {
  const body = {profile:"test", n_agents:80, n_ticks:12, jurisdictions:["EU"], verify_replay:false};
  const j = await (await fetch("/api/run",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})).json();
  let res = null;
  for (let i=0;i<400;i++){ const s=await (await fetch("/api/job/"+j.job_id)).json();
    if (s.status==="done"){res=s.result;break;} if (s.status==="error") throw new Error(s.error);
    await new Promise(r=>setTimeout(r,200)); }
  if (!res) throw new Error("run did not finish");
  render(res);
  return res.n_events;
}"""


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _serious_or_critical(results):
    return [v for v in results.response["violations"]
            if v.get("impact") in ("serious", "critical")]


def test_dashboard_has_no_serious_axe_violations():
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                # bypass_csp: the app's script-src 'self' CSP would block the
                # injected axe-core script; bypassing it for the SCANNER does
                # not weaken the app itself (the CSP still ships to users and
                # is asserted by the security tests).
                context = browser.new_context(bypass_csp=True)
                page = context.new_page()
                # Scan under prefers-reduced-motion (which the CSS honors):
                # entrance animations otherwise leave elements mid-opacity
                # when axe samples colors, producing phantom contrast
                # readings lighter than the real tokens.
                page.emulate_media(reduced_motion="reduce")
                page.goto(f"http://127.0.0.1:{port}")
                page.wait_for_function(
                    "document.querySelectorAll('#preset option').length > 0")
                axe = Axe()

                initial = axe.run(page, options=_AXE_OPTIONS)
                bad = _serious_or_critical(initial)
                assert not bad, (
                    "serious/critical axe violations on the initial view:\n"
                    + initial.generate_report())

                # Rendered results view: real run through the real API.
                n_events = page.evaluate(_RUN_AND_RENDER)
                assert n_events > 0
                rendered = axe.run(page, options=_AXE_OPTIONS)
                bad = _serious_or_critical(rendered)
                assert not bad, (
                    "serious/critical axe violations on the results view:\n"
                    + rendered.generate_report())
            finally:
                browser.close()
    finally:
        server.shutdown()
