"""Real end-to-end browser test: a headless Chromium drives the actual stdlib
server, runs a real simulation, and asserts the dashboard renders. This is a
non-synthetic integration test of the whole stack (server + JS + render), not
mocked. Skipped automatically where Playwright/Chromium isn't installed; CI
installs it (see .github/workflows/ci.yml)."""

import socket
import threading
from http.server import ThreadingHTTPServer

import pytest

sync_playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright not installed").sync_playwright

from socio_sim.web import app  # noqa: E402


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


_RUN_AND_RENDER = """async () => {
  const body = {profile:"test", n_agents:80, n_ticks:12, jurisdictions:["EU"], verify_replay:false};
  const j = await (await fetch("/api/run",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})).json();
  let res = null;
  for (let i=0;i<400;i++){ const s=await (await fetch("/api/job/"+j.job_id)).json();
    if (s.status==="done"){res=s.result;break;} if (s.status==="error") throw new Error(s.error);
    await new Promise(r=>setTimeout(r,200)); }
  if (!res) throw new Error("run did not finish");
  render(res);
  return {events: res.n_events, cards: document.querySelectorAll("#cards .card").length};
}"""


def test_e2e_dashboard_runs_and_renders():
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(base)
                assert page.title() == "SocioSim"
                page.wait_for_function("document.querySelectorAll('#preset option').length > 0")
                page.evaluate("""() => {
                  document.querySelector('#cfgTabs button[data-tab=feedads]').click();
                  document.querySelector('#addCampaign').click();
                  document.querySelector('#graph_kind').value = 'ws';
                  document.querySelector('#content_mode').value = 'ollama';
                  document.querySelector('#follow_rate').value = '0.1';
                  document.querySelector('#preset').value = 'custom';
                  document.querySelector('#preset').dispatchEvent(new Event('change'));
                }""")
                clean = page.evaluate("collect()")
                assert "campaigns" not in clean
                assert clean["graph_kind"] == "ba"
                assert clean["content_mode"] == "template"
                assert clean["follow_rate"] == 0
                page.evaluate("document.querySelector('#classifier_mode').value = 'synthetic_template_classifier'; document.querySelector('#classifier_mode').dispatchEvent(new Event('change'))")
                assert page.locator("#classifier_precision").is_disabled()
                assert page.locator("#classifier_recall").is_disabled()
                page.evaluate("document.querySelector('#classifier_mode').value = 'synthetic_noise_classifier'; document.querySelector('#classifier_mode').dispatchEvent(new Event('change'))")
                out = page.evaluate(_RUN_AND_RENDER)
                assert out["events"] > 0
                assert out["cards"] >= 6                  # overview metric cards
                tabs = [
                    "overview", "feed", "charts", "network", "cascade", "fairness",
                    "ads", "calib", "compare", "audit", "log",
                ]
                for tab in tabs:
                    page.evaluate(
                        "(tab) => document.querySelector(`#outTabs button[data-otab=${tab}]`).click()",
                        tab)
                    page.wait_for_timeout(80)
                    has_output = page.evaluate("""(tab) => {
                      const p = document.querySelector(`[data-opanel="${tab}"]`);
                      if (!p) return false;
                      const hasText = p.innerText && p.innerText.trim().length > 0;
                      const hasVisual = p.querySelector("canvas,svg,table,.card,.post,.adcard,pre");
                      return Boolean(hasText || hasVisual);
                    }""", tab)
                    assert has_output, f"{tab} tab rendered no output"
                assert page.locator("#ads img.creative-img[alt]").count() >= 1
                assert "/static/assets/v4/ad-creative-v4-" in page.locator("#ads img.creative-img").first.get_attribute("src")
                assert page.locator("#feedWrap img.feed-img[alt]").count() >= 1
                assert "feed-cover-v4-" in page.locator("#feedWrap img.feed-img").first.get_attribute("src")
                page.evaluate("document.querySelector('#outTabs button[data-otab=feed]').click()")
                for width in (1440, 768, 390, 320):
                    page.set_viewport_size({"width": width, "height": 900})
                    page.wait_for_timeout(80)
                    layout = page.evaluate("""() => {
                      const doc = document.documentElement;
                      const outTabs = document.querySelector('#outTabs');
                      const buttons = [...outTabs.querySelectorAll('button')];
                      const feed = document.querySelector('#feedWrap .post');
                      return {
                        docOverflow: doc.scrollWidth - doc.clientWidth,
                        outTabsHeight: outTabs.getBoundingClientRect().height,
                        minButtonHeight: Math.min(...buttons.map(b => b.getBoundingClientRect().height)),
                        minButtonWidth: Math.min(...buttons.map(b => b.getBoundingClientRect().width)),
                        feedFits: !feed || feed.scrollWidth <= feed.clientWidth + 1
                      };
                    }""")
                    assert layout["docOverflow"] <= 1, (width, layout)
                    assert layout["outTabsHeight"] <= 60, (width, layout)
                    assert layout["minButtonHeight"] >= 34, (width, layout)
                    assert layout["minButtonWidth"] >= 64, (width, layout)
                    assert layout["feedFits"], (width, layout)
                page.evaluate("document.querySelector('#outTabs button[data-otab=ads]').click()")
                image_ok = page.evaluate("""() => {
                  const ads = [...document.querySelectorAll('#ads img.creative-img')];
                  const feeds = [...document.querySelectorAll('#feedWrap img.feed-img')];
                  const adBox = ads[0].getBoundingClientRect();
                  const feedSrcs = new Set(feeds.map(i => i.getAttribute('src')));
                  return {
                    adsLoaded: ads.every(i => i.complete && i.naturalWidth > 0 && i.naturalHeight > 0),
                    feedsLoaded: feeds.every(i => i.complete && i.naturalWidth === 1200 && i.naturalHeight === 800),
                    adsFit: ads.every(i => getComputedStyle(i).objectFit === 'contain'),
                    feedsFit: feeds.every(i => getComputedStyle(i).objectFit === 'contain'),
                    variedFeed: feedSrcs.size >= Math.min(3, feeds.length),
                    adRatio: Math.round((adBox.width / adBox.height) * 100) / 100,
                    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
                  };
                }""")
                assert image_ok["adsLoaded"]
                assert image_ok["feedsLoaded"]
                assert image_ok["adsFit"]
                assert image_ok["feedsFit"]
                assert image_ok["variedFeed"]
                assert abs(image_ok["adRatio"] - 2.0) < 0.08
                assert image_ok["overflow"] <= 1
                page.evaluate("document.querySelector('#cfgTabs button[data-tab=content]').click()")
                rate_ui = page.evaluate("""() => ({
                  hateMax: document.querySelector('#rate_hate').max,
                  hateLabel: document.querySelector('#rl_hate').textContent,
                  notes: [...document.querySelectorAll('#rates small')].length,
                  aria: document.querySelector('#rate_hate').getAttribute('aria-label')
                })""")
                assert rate_ui["hateMax"] == "0.1"
                assert "%" in rate_ui["hateLabel"]
                assert rate_ui["notes"] >= 8
                assert "share of all posts" in rate_ui["aria"]
                page.evaluate("document.querySelector('#cfgTabs button[data-tab=marketing]').click()")
                calc_ok = page.evaluate("""() => {
                  const before = JSON.stringify(collect());
                  const fields = [...document.querySelectorAll('#marketing input')];
                  fields.forEach((el, i) => { el.value = String(999 + i); el.dispatchEvent(new Event('input', {bubbles:true})); });
                  const after = JSON.stringify(collect());
                  return {
                    allPlanning: fields.length > 0 && fields.every(el => el.dataset.controlKind === 'planning-calculator'),
                    unchanged: before === after
                  };
                }""")
                assert calc_ok["allPlanning"]
                assert calc_ok["unchanged"]
                hrefs = page.evaluate("[...document.querySelectorAll('a[href]')].map(a => a.href)")
                assert all("token=" not in href for href in hrefs)
                # the 3D topology canvas renders (non-blank pixels)
                page.evaluate("document.querySelector('#outTabs button[data-otab=network]').click()")
                page.wait_for_timeout(150)
                drawn = page.evaluate(
                    "() => { const c=document.querySelector('#net3d'); if(!c) return 0;"
                    " const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;"
                    " let n=0; for(let i=3;i<d.length;i+=4) if(d[i]>0) n++; return n; }")
                assert drawn > 0
                # the audit-log explorer renders rows
                page.evaluate("document.querySelector('#outTabs button[data-otab=audit]').click()")
                rows = page.evaluate("document.querySelectorAll('#audit table tbody tr').length")
                assert rows > 0
                # Programmatic render paths must keep visual tabs and ARIA in sync.
                page.evaluate("""renderCompare({
                  baseline_jurisdictions:["EU"], intervention_jurisdictions:["EU"],
                  n_replicates:2, provenance:"test",
                  compare:{harmful_exposure_rate:{baseline_median:0.1, intervention_median:0.09,
                    delta_median:-0.01, delta_ci:[-0.02,-0.001]}}
                })""")
                assert page.get_attribute(
                    "#outTabs button[data-otab=compare]", "aria-selected") == "true"
                assert page.get_attribute(
                    "#outTabs button[data-otab=overview]", "aria-selected") == "false"
                page.evaluate("document.querySelector('#outTabs button[data-otab=overview]').click()")
                assert "compare-only result" in page.locator("#cards").inner_text()
                assert page.locator("#cards .card").count() == 0
                # Campaign editor should reflow within the sidebar instead of clipping.
                page.evaluate("document.querySelector('#cfgTabs button[data-tab=feedads]').click()")
                page.evaluate("document.querySelector('#addCampaign').click()")
                fits = page.evaluate("""() => {
                  const row = document.querySelector('#campaigns .camp-row');
                  return row.scrollWidth <= row.clientWidth + 1;
                }""")
                assert fits
            finally:
                browser.close()
    finally:
        server.shutdown()
