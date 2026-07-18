"""Persona sandbox flows: a first-time MARKETING user and a first-time
GOVERNMENT analyst drive the console end-to-end through the real API, across
different preset sandboxes, and must reach useful, honestly-labelled outputs
without ever seeing a raw error.

These are navigability tests (can someone who has never used the product get
from a preset to a readable result?), not empirical-validity claims: every
asserted surface carries its scenario/diagnostic labelling.

Skipped automatically where Playwright/Chromium isn't installed (CI installs
both).
"""

import socket
import threading
from http.server import ThreadingHTTPServer

import pytest

sync_playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright not installed").sync_playwright

from socio_sim.web import app  # noqa: E402


def _serve():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    server = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{port}"


_RUN_SMALL = """async (extra) => {
  const body = Object.assign(
    {profile:"test", n_agents:80, n_ticks:12, verify_replay:false}, extra);
  const j = await (await fetch("/api/run",{method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body)})).json();
  if (j.error) throw new Error(j.error);
  for (let i=0;i<600;i++){
    const s = await (await fetch("/api/job/"+j.job_id)).json();
    if (s.status==="done"){render(s.result);return true;}
    if (s.status==="error") throw new Error(s.error);
    await new Promise(r=>setTimeout(r,150)); }
  throw new Error("timeout");
}"""


@pytest.mark.parametrize("preset,vertical,market_idx", [
    ("performance_campaign", "telecom", 2),     # tech market, telecom vertical
    ("brand_launch", "apparel_footwear", 5),    # entertainment market
])
def test_marketing_user_sandbox_flow(preset, vertical, market_idx):
    """Marketing persona: pick a Business preset, add a campaign with a
    NAMED vertical + NAMED content market, run, and read the Ads tab —
    campaign table, lift diagnostic language, and honest footnotes."""
    server, base = _serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_context(bypass_csp=True).new_page()
                page.emulate_media(reduced_motion="reduce")
                page.goto(base)
                page.wait_for_function(
                    "document.querySelectorAll('#preset option').length > 0")
                # preset may not exist under this key; fall back to the first
                # Business optgroup entry so the flow tests real UI state.
                page.evaluate(f"""() => {{
                  const ps = document.querySelector('#preset');
                  const want = {preset!r};
                  const opt = [...ps.options].find(o => o.value === want)
                        || [...ps.options].find(o => (o.closest('optgroup')?.label) === 'Business');
                  ps.value = opt.value; ps.dispatchEvent(new Event('change'));
                }}""")
                # the preset summary explains what changed (first-time users)
                assert page.evaluate(
                    "!document.querySelector('#presetSummary').hidden")
                # campaign editor: labeled fields, named vertical + market
                page.evaluate(
                    "document.querySelector('#cfgTabs button[data-tab=feedads]').click()")
                page.evaluate("document.querySelector('#addCampaign').click()")
                row_ok = page.evaluate(f"""() => {{
                  const row = document.querySelector('#campaigns .camp-row');
                  if (!row) return 'no row';
                  if (row.scrollWidth > row.clientWidth + 1) return 'overflow';
                  const labels = [...row.querySelectorAll('.cf > span')].map(e => e.textContent);
                  if (!labels.some(t => /Vertical/.test(t))) return 'no vertical label';
                  const vert = row.querySelector('.cf-vert');
                  vert.value = {vertical!r}; vert.dispatchEvent(new Event('change'));
                  const ctr = +row.querySelector('.cf-ctr').value;
                  const mkt = row.querySelector('.cf-mkt');
                  mkt.value = String({market_idx});
                  const mktName = mkt.selectedOptions[0].textContent;
                  if (/^Topic \\d/.test(mktName)) return 'market not named';
                  return {{ctr, mktName}};
                }}""")
                assert isinstance(row_ok, dict), row_ok
                assert 0 < row_ok["ctr"] < 0.01   # sourced anchor adopted
                # run with the campaign the persona just configured
                page.evaluate(_RUN_SMALL, {
                    "jurisdictions": ["US"],
                    "campaigns": [{"advertiser": "Persona Brand",
                                   "vertical": vertical,
                                   "bid": 2, "budget": 100,
                                   "segment": "25-34",
                                   "market": str(market_idx)}]})
                page.evaluate(
                    "document.querySelector('#outTabs button[data-otab=ads]').click()")
                ads_text = page.locator("#ads").inner_text()
                assert "Persona Brand" in ads_text
                assert "Synthetic scenario output" in ads_text  # honest footnote
                assert "not a budget recommendation" in ads_text.lower() \
                    or "not an estimate" in ads_text.lower() \
                    or "diagnostic" in ads_text.lower()
            finally:
                browser.close()
    finally:
        server.shutdown()


@pytest.mark.parametrize("preset,jurisdictions", [
    ("eu_dsa", ["EU"]),
    ("cn_label", ["CN"]),
])
def test_government_user_sandbox_flow(preset, jurisdictions):
    """Government persona: pick a Regulatory preset, run a localized sandbox,
    and read how simulated citizens respond — fairness table, transparency
    tally, audit log, and the honest status chips on Target Comparison."""
    server, base = _serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_context(bypass_csp=True).new_page()
                page.emulate_media(reduced_motion="reduce")
                page.goto(base)
                page.wait_for_function(
                    "document.querySelectorAll('#preset option').length > 0")
                page.evaluate(f"""() => {{
                  const ps = document.querySelector('#preset');
                  const want = {preset!r};
                  const opt = [...ps.options].find(o => o.value === want)
                        || [...ps.options].find(o => (o.closest('optgroup')?.label) === 'Regulatory');
                  ps.value = opt.value; ps.dispatchEvent(new Event('change'));
                }}""")
                page.evaluate(_RUN_SMALL, {"jurisdictions": jurisdictions})
                # fairness surface: FPR/FNR by group with sufficiency labels
                page.evaluate(
                    "document.querySelector('#outTabs button[data-otab=fairness]').click()")
                fair = page.locator("[data-opanel=fairness]").inner_text()
                assert "FPR" in fair and "FNR" in fair
                # audit log explorer renders sampled events
                page.evaluate(
                    "document.querySelector('#outTabs button[data-otab=audit]').click()")
                assert page.locator("#auditRows table tbody tr").count() > 0
                # honesty chips on Target Comparison
                page.evaluate(
                    "document.querySelector('#outTabs button[data-otab=calib]').click()")
                chips = page.locator("#fitStatus").inner_text()
                assert "Synthetic scenario" in chips
                assert "Not empirically validated" in chips
                # transparency export is offered
                assert page.evaluate(
                    "!document.querySelector('#expTransparency').hidden")
            finally:
                browser.close()
    finally:
        server.shutdown()
