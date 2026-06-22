"""Web-console hardening (OWASP-aligned): security headers, CSRF/Origin guard,
access token, body/content-type limits, and the SSRF allow-list on llm_base_url."""

import json
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


def test_build_config_rejects_ssrf_llm_url():
    with pytest.raises(Exception):
        app._build_config({"profile": "test", "jurisdictions": ["EU"],
                           "llm_base_url": "http://169.254.169.254"})
