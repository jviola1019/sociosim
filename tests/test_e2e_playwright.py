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
                out = page.evaluate(_RUN_AND_RENDER)
                assert out["events"] > 0
                assert out["cards"] >= 6                  # overview metric cards
                # the topology view renders nodes
                page.evaluate("document.querySelector('#outTabs button[data-otab=network]').click()")
                circles = page.evaluate("document.querySelectorAll('#network svg circle').length")
                assert circles > 0
                # the audit-log explorer renders rows
                page.evaluate("document.querySelector('#outTabs button[data-otab=audit]').click()")
                rows = page.evaluate("document.querySelectorAll('#audit table tbody tr').length")
                assert rows > 0
            finally:
                browser.close()
    finally:
        server.shutdown()
