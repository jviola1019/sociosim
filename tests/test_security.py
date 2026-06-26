"""Web-console hardening (OWASP-aligned): security headers, CSRF/Origin guard,
access token, body/content-type limits, and the SSRF allow-list on llm_base_url."""

import json
import http.client
import socket
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from socio_sim.web import app


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _boot(token=None):
    port = _free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), app.Handler)
    if token:
        srv.access_token = token
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{port}"


def _post(base, path="/api/run", body=None, headers=None):
    data = json.dumps(body or {"profile": "test", "n_agents": 40, "n_ticks": 6,
                               "jurisdictions": ["EU"]}).encode()
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(base + path, data=data, headers=h)
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


def test_security_headers_on_every_response():
    srv, base = _boot()
    try:
        r = urllib.request.urlopen(base + "/api/meta")
        assert "default-src 'self'" in r.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors 'none'" in r.headers.get("Content-Security-Policy", "")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert r.headers.get("Referrer-Policy") == "no-referrer"
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/nope")
        assert e.value.code == 404
        assert "default-src 'self'" in e.value.headers.get("Content-Security-Policy", "")
    finally:
        srv.shutdown()


def test_access_token_required_when_server_sets_one():
    srv, base = _boot(token="s3cret-token")
    try:
        code, _ = _post(base)                                   # no token
        assert code == 403
        code, payload = _post(base, headers={"X-SocioSim-Token": "s3cret-token"})
        assert code == 200 and "job_id" in payload              # correct token
        code, _ = _post(base, headers={"X-SocioSim-Token": "wrong"})
        assert code == 403
    finally:
        srv.shutdown()


def test_cross_origin_post_rejected():
    srv, base = _boot()
    try:
        code, _ = _post(base, headers={"Origin": "http://evil.example"})
        assert code == 403                                      # CSRF guard
        code, payload = _post(base, headers={"Origin": base})   # same-origin ok
        assert code == 200 and "job_id" in payload
    finally:
        srv.shutdown()


def test_get_rejects_non_loopback_host_header():
    srv, base = _boot()
    try:
        req = urllib.request.Request(base + "/api/meta", headers={"Host": "evil.example"})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        assert e.value.code == 403
    finally:
        srv.shutdown()


def test_delete_requires_token_when_server_sets_one(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "_STORE", app.RunStore(tmp_path / "db.sqlite"))
    app._STORE.save("r1", {
        "summary": {"harmful_exposure": {}, "moderation": {}},
        "config": {"jurisdictions": ["EU"], "n_agents": 1, "n_ticks": 1},
        "manifest": {"config_hash": "cfg", "stream_hash": "stream"},
        "content_mode": "template",
        "n_events": 0,
        "elapsed_s": 0.0,
        "implausibility": 0.0,
        "replay": {"ok": True},
    })
    srv, base = _boot(token="s3cret-token")
    try:
        req = urllib.request.Request(base + "/api/runs/r1", method="DELETE")
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req)
        assert e.value.code == 403
        req = urllib.request.Request(
            base + "/api/runs/r1", method="DELETE",
            headers={"X-SocioSim-Token": "s3cret-token"})
        assert json.loads(urllib.request.urlopen(req).read())["deleted"] is True
    finally:
        srv.shutdown()


def test_remote_mode_protects_history_gets(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "_STORE", app.RunStore(tmp_path / "db.sqlite"))
    app._STORE.save("r1", {
        "summary": {"harmful_exposure": {}, "moderation": {}},
        "config": {"jurisdictions": ["EU"], "n_agents": 1, "n_ticks": 1},
        "manifest": {"config_hash": "cfg", "stream_hash": "stream"},
        "content_mode": "template",
        "n_events": 0,
        "elapsed_s": 0.0,
        "implausibility": 0.0,
        "replay": {"ok": True},
    })
    srv, base = _boot(token="s3cret-token")
    srv.expose_token = False
    try:
        meta = json.loads(urllib.request.urlopen(base + "/api/meta").read())
        assert meta["token"] is None and meta["token_required"] is True
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/api/runs")
        assert e.value.code == 403
        req = urllib.request.Request(base + "/api/runs",
                                     headers={"X-SocioSim-Token": "s3cret-token"})
        assert json.loads(urllib.request.urlopen(req).read())["count"] == 1
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/api/runs/r1/export?fmt=json&token=s3cret-token")
        assert e.value.code == 403
        req = urllib.request.Request(
            base + "/api/runs/r1/export?fmt=json",
            headers={"X-SocioSim-Token": "s3cret-token"})
        assert json.loads(urllib.request.urlopen(req).read())["config"]
    finally:
        srv.shutdown()


def test_remote_mode_protects_creative_endpoint():
    srv, base = _boot(token="s3cret-token")
    srv.expose_token = False
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/api/creative?key=x&w=1024&h=512")
        assert e.value.code == 403
        req = urllib.request.Request(
            base + "/api/creative?key=x&w=1024&h=512",
            headers={"X-SocioSim-Token": "s3cret-token"})
        r = urllib.request.urlopen(req)
        assert r.headers.get("Content-Type") == "image/png"
        assert r.read(8) == b"\x89PNG\r\n\x1a\n"
    finally:
        srv.shutdown()


def test_non_loopback_serve_requires_explicit_allowed_hosts(monkeypatch):
    class DummyServer:
        instances = []

        def __init__(self, *args, **kwargs):
            self.args = args
            DummyServer.instances.append(self)

        def serve_forever(self):
            return None

        def shutdown(self):
            return None

    monkeypatch.setattr(app, "ThreadingHTTPServer", DummyServer)
    monkeypatch.setenv("SOCIOSIM_ACCESS_TOKEN", "remote-token")
    monkeypatch.delenv("SOCIOSIM_ALLOWED_HOSTS", raising=False)
    with pytest.raises(RuntimeError, match="SOCIOSIM_ALLOWED_HOSTS"):
        app.serve(host="0.0.0.0", port=9876, open_browser=False)

    monkeypatch.setenv("SOCIOSIM_ALLOWED_HOSTS", "console.example,10.0.0.5")
    app.serve(host="0.0.0.0", port=9876, open_browser=False)
    assert DummyServer.instances[-1].allowed_hosts == {"console.example", "10.0.0.5"}
    assert DummyServer.instances[-1].expose_token is False


def test_wrong_content_type_415():
    srv, base = _boot()
    try:
        code, _ = _post(base, headers={"Content-Type": "text/plain"})
        assert code == 415
    finally:
        srv.shutdown()


def test_body_too_large_413(monkeypatch):
    monkeypatch.setattr(app, "MAX_BODY_BYTES", 10)              # tiny cap for the test
    srv, base = _boot()
    try:
        code, _ = _post(base)                                   # normal body > 10 bytes
        assert code == 413
    finally:
        srv.shutdown()


def test_invalid_content_length_rejected():
    srv, base = _boot()
    host, port = base.replace("http://", "").split(":")
    try:
        conn = http.client.HTTPConnection(host, int(port), timeout=2)
        conn.putrequest("POST", "/api/run")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", "abc")
        conn.endheaders()
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()

        conn = http.client.HTTPConnection(host, int(port), timeout=2)
        conn.putrequest("POST", "/api/run")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", "-1")
        conn.endheaders()
        resp = conn.getresponse()
        assert resp.status == 400
        conn.close()
    finally:
        srv.shutdown()


def test_ssrf_guard_on_llm_base_url():
    app._validate_llm_url("")                                   # template mode: ok
    app._validate_llm_url("http://127.0.0.1:11434")             # loopback: ok
    app._validate_llm_url("http://localhost:11434")             # loopback: ok
    with pytest.raises(ValueError):
        app._validate_llm_url("ftp://127.0.0.1")                # bad scheme
    with pytest.raises(ValueError):
        app._validate_llm_url("http://169.254.169.254/latest")  # cloud metadata
    with pytest.raises(ValueError):
        app._validate_llm_url("http://example.com")             # public host


def test_ssrf_guard_requires_private_host_allowlist(monkeypatch):
    with pytest.raises(ValueError, match="SOCIOSIM_LLM_ALLOWED_HOSTS"):
        app._validate_llm_url("http://192.168.1.10:11434")
    monkeypatch.setenv("SOCIOSIM_LLM_ALLOWED_HOSTS", "192.168.1.10")
    app._validate_llm_url("http://192.168.1.10:11434")


def test_build_config_rejects_ssrf_llm_url():
    with pytest.raises(Exception):
        app._build_config({"profile": "test", "jurisdictions": ["EU"],
                           "llm_base_url": "http://169.254.169.254"})
