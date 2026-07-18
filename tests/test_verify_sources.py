"""Fail-closed source-verification tests (audit Phase 2/3).

The old verifier skipped quote verification with a warning when pypdf was
missing or extraction was empty, yet still exited 0 claiming targets were
verified. These tests pin the fail-closed contract and the hardened
retrieval policy. No test touches the network: retrieval is exercised
through an injected connection factory / fetcher.
"""

import importlib.util
import io
import sys
import zlib
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "verify_sources",
    Path(__file__).resolve().parents[1] / "scripts" / "verify_sources.py")
vs = importlib.util.module_from_spec(_spec)
sys.modules["verify_sources"] = vs
_spec.loader.exec_module(vs)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_pdf(text: str) -> bytes:
    """A minimal valid one-page PDF whose page stream draws `text`, so the
    REAL pypdf path (not a stub) extracts it."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_at = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(b"trailer\n<< /Size " + str(len(objs) + 1).encode()
              + b" /Root 1 0 R >>\nstartxref\n"
              + str(xref_at).encode() + b"\n%%EOF\n")
    return out.getvalue()


def target(sha256: str, *, stability="immutable_versioned_arxiv_pdf",
           kind="pdf", quotes=("gamma = 2\\.3",), derivation=None,
           url="https://example.org/paper.pdf"):
    t = {"value": 2.3, "tolerance": 0.1,
         "source_artifact": {"artifact_url": url, "sha256": sha256,
                             "stability": stability, "content_kind": kind,
                             "verified_quotes": list(quotes)}}
    if derivation:
        t["derivation"] = derivation
    return t


def sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def fetcher_for(data: bytes, url="https://example.org/paper.pdf",
                ctype="application/pdf"):
    def _f(u):
        return data, url, ctype
    return _f


# ---------------------------------------------------------------------------
# verification-level semantics
# ---------------------------------------------------------------------------

def test_pdf_with_pypdf_and_matching_quote_reaches_fully_verified():
    pytest.importorskip("pypdf")
    pdf = make_pdf("measured gamma = 2.3 in the actor graph")
    t = {"t": target(sha(pdf))}
    rep = vs.verify_targets(t, fetcher=fetcher_for(pdf))
    r = rep["targets"][0]
    assert rep["ok"] and r["met_required"]
    for lv in ("artifact_retrieved", "artifact_hash_matched",
               "text_extracted", "statistic_quote_matched", "fully_verified"):
        assert lv in r["levels"], lv


def test_missing_pypdf_is_a_failure_not_a_skip(monkeypatch):
    pdf = make_pdf("gamma = 2.3")
    monkeypatch.setattr(vs, "_load_pypdf",
                        lambda: (_ for _ in ()).throw(ImportError("no pypdf")))
    rep = vs.verify_targets({"t": target(sha(pdf))}, fetcher=fetcher_for(pdf))
    assert rep["ok"] is False
    r = rep["targets"][0]
    assert any("pypdf" in f for f in r["failures"])
    assert "statistic_quote_matched" not in r["levels"]
    assert "fully_verified" not in r["levels"]


def test_empty_pdf_extraction_is_a_failure(monkeypatch):
    pdf = make_pdf("gamma = 2.3")

    class _EmptyPage:
        def extract_text(self):
            return ""

    class _EmptyReader:
        def __init__(self, *_a, **_k):
            self.pages = [_EmptyPage()]

    monkeypatch.setattr(vs, "_load_pypdf",
                        lambda: type("M", (), {"PdfReader": _EmptyReader}))
    rep = vs.verify_targets({"t": target(sha(pdf))}, fetcher=fetcher_for(pdf))
    assert rep["ok"] is False
    assert any("empty text" in f for f in rep["targets"][0]["failures"])


def test_hash_match_plus_missing_quote_fails():
    pytest.importorskip("pypdf")
    pdf = make_pdf("this artifact no longer contains the statistic")
    rep = vs.verify_targets({"t": target(sha(pdf))}, fetcher=fetcher_for(pdf))
    r = rep["targets"][0]
    assert "artifact_hash_matched" in r["levels"]     # hash alone...
    assert rep["ok"] is False                          # ...is not verification
    assert any("NOT found" in f for f in r["failures"])


def test_mutable_hash_mismatch_with_matching_quote_warns_but_passes():
    pytest.importorskip("pypdf")
    pdf = make_pdf("still says gamma = 2.3 today")
    t = target("0" * 64, stability="mutable_html_hash_valid_only_at_retrieval")
    rep = vs.verify_targets({"t": t}, fetcher=fetcher_for(pdf))
    r = rep["targets"][0]
    assert rep["ok"] is True and r["met_required"]
    assert any("sha256 mismatch" in w for w in r["warnings"])
    assert "artifact_hash_matched" not in r["levels"]
    assert "fully_verified" not in r["levels"]   # never full with a mismatch


def test_immutable_hash_mismatch_fails():
    pytest.importorskip("pypdf")
    pdf = make_pdf("gamma = 2.3")
    rep = vs.verify_targets({"t": target("0" * 64)}, fetcher=fetcher_for(pdf))
    assert rep["ok"] is False
    assert any("IMMUTABLE" in f for f in rep["targets"][0]["failures"])


def test_derivation_is_reproduced_not_asserted():
    pytest.importorskip("pypdf")
    pdf = make_pdf("reinstated 82,190 of 745,707 appeals; gamma = 2.3")
    good = {"kind": "ratio", "inputs": [82190, 745707],
            "expected_value_round": 3}
    t = target(sha(pdf), derivation=good)
    t["value"], t["tolerance"] = 0.110, 0.044
    rep = vs.verify_targets({"t": t}, fetcher=fetcher_for(pdf))
    assert rep["ok"] and "derivation_reproduced" in rep["targets"][0]["levels"]
    # a wrong recorded value must fail the derivation check
    t_bad = dict(t)
    t_bad["value"] = 0.2
    rep = vs.verify_targets({"t": t_bad}, fetcher=fetcher_for(pdf))
    assert rep["ok"] is False
    assert any("derivation NOT reproduced" in f
               for f in rep["targets"][0]["failures"])
    # unknown derivation kinds fail closed
    t_unk = dict(t)
    t_unk["derivation"] = {"kind": "trust_me"}
    rep = vs.verify_targets({"t": t_unk}, fetcher=fetcher_for(pdf))
    assert rep["ok"] is False


def test_duplicate_artifact_url_is_fetched_once():
    pytest.importorskip("pypdf")
    pdf = make_pdf("gamma = 2.3")
    calls = []

    def counting(u):
        calls.append(u)
        return pdf, u, "application/pdf"

    ts = {"a": target(sha(pdf)), "b": target(sha(pdf))}
    rep = vs.verify_targets(ts, fetcher=counting)
    assert rep["ok"] and len(calls) == 1


def test_success_output_reports_exact_level_counts(capsys):
    pytest.importorskip("pypdf")
    pdf = make_pdf("gamma = 2.3")
    mutable = target("0" * 64,
                     stability="mutable_html_hash_valid_only_at_retrieval")
    rep = vs.verify_targets({"full": target(sha(pdf)), "mut": mutable},
                            fetcher=fetcher_for(pdf))
    vs._print_report(rep)
    import re as _re
    out = capsys.readouterr().out
    assert _re.search(r"fully_verified\s+1/2", out)      # never 2/2: one had
    assert _re.search(r"statistic_quote_matched\s+2/2", out)  # a hash mismatch
    assert _re.search(r"artifact_hash_matched\s+1/2", out)


# ---------------------------------------------------------------------------
# hardened retrieval policy
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status=200, headers=None, body=b"", chunks=None):
        self.status = status
        self._headers = {k.lower(): v for k, v in (headers or {}).items()}
        self._buf = io.BytesIO(body)
        self._chunks = chunks

    def getheader(self, name):
        return self._headers.get(name.lower())

    def read(self, n=-1):
        if self._chunks is not None:
            return self._chunks.pop(0) if self._chunks else b""
        return self._buf.read(n)


class _FakeConn:
    def __init__(self, responses):
        self._responses = responses
        self.sock = None

    def request(self, *a, **k):
        pass

    def getresponse(self):
        return self._responses.pop(0)

    def close(self):
        pass


def _allow_dns(monkeypatch, ip="93.184.216.34"):
    monkeypatch.setattr(vs.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", (ip, 443))])


def test_non_https_url_refused(monkeypatch):
    with pytest.raises(vs.RetrievalError, match="non-HTTPS"):
        vs.fetch("http://example.org/x.pdf")


def test_connection_dials_the_pinned_validated_ip(monkeypatch):
    """SSRF/rebinding TOCTOU (security-review finding): the connection must
    dial EXACTLY the IP that passed validation -- no second DNS lookup that
    a rebinding resolver could redirect to a private address."""
    _allow_dns(monkeypatch, ip="93.184.216.34")
    seen = {}

    def capture(host, port, pinned_ip):
        seen["args"] = (host, port, pinned_ip)
        return _FakeConn([_FakeResp(body=b"x", headers={"Content-Length": "1"})])

    monkeypatch.setattr(vs, "_open_connection", capture)
    data, final_url, _ = vs.fetch("https://example.org/x.pdf")
    assert data == b"x"
    assert seen["args"] == ("example.org", 443, "93.184.216.34")
    # ...and the default factory produces a pinned connection (TLS SNI on
    # the hostname, socket dialled to the validated IP)
    conn = vs._PinnedHTTPSConnection("example.org", 443, "93.184.216.34",
                                     timeout=1)
    assert conn._pinned_ip == "93.184.216.34" and conn.host == "example.org"


def test_credentials_in_url_refused():
    with pytest.raises(vs.RetrievalError, match="credentials"):
        vs.fetch("https://user:pw@example.org/x.pdf")


def test_redirect_to_non_https_fails(monkeypatch):
    _allow_dns(monkeypatch)
    conn = _FakeConn([_FakeResp(status=302,
                                headers={"Location": "http://evil.example/x"})])
    monkeypatch.setattr(vs, "_open_connection", lambda h, p, ip: conn)
    with pytest.raises(vs.RetrievalError, match="non-HTTPS"):
        vs.fetch("https://example.org/x.pdf")


def test_redirect_limit_enforced(monkeypatch):
    _allow_dns(monkeypatch)
    resp = lambda: _FakeResp(status=301,  # noqa: E731
                             headers={"Location": "https://example.org/next"})
    monkeypatch.setattr(vs, "_open_connection",
                        lambda h, p, ip: _FakeConn([resp()]))
    with pytest.raises(vs.RetrievalError, match="redirects"):
        vs.fetch("https://example.org/x.pdf")


def test_private_loopback_and_linklocal_destinations_refused(monkeypatch):
    for ip in ("127.0.0.1", "10.0.0.5", "169.254.169.254", "192.168.1.4"):
        _allow_dns(monkeypatch, ip=ip)
        with pytest.raises(vs.RetrievalError, match="non-public"):
            vs.fetch("https://example.org/x.pdf")


def test_oversized_artifact_refused_before_download(monkeypatch):
    _allow_dns(monkeypatch)
    conn = _FakeConn([_FakeResp(headers={
        "Content-Length": str(vs.MAX_BYTES + 1)})])
    monkeypatch.setattr(vs, "_open_connection", lambda h, p, ip: conn)
    with pytest.raises(vs.RetrievalError, match="too large"):
        vs.fetch("https://example.org/x.pdf")


def test_streaming_cap_enforced_without_content_length(monkeypatch):
    _allow_dns(monkeypatch)
    monkeypatch.setattr(vs, "MAX_BYTES", 100)
    conn = _FakeConn([_FakeResp(chunks=[b"x" * 64, b"x" * 64])])
    monkeypatch.setattr(vs, "_open_connection", lambda h, p, ip: conn)
    with pytest.raises(vs.RetrievalError, match="cap"):
        vs.fetch("https://example.org/x.pdf")


def test_timeout_is_a_controlled_failure(monkeypatch):
    _allow_dns(monkeypatch)

    class _TimeoutConn(_FakeConn):
        def getresponse(self):
            raise TimeoutError("simulated")

    monkeypatch.setattr(vs, "_open_connection",
                        lambda h, p, ip: _TimeoutConn([]))
    with pytest.raises(vs.RetrievalError, match="timeout"):
        vs.fetch("https://example.org/x.pdf")
    # ...and through verify_targets it becomes a failure entry, not a crash
    rep = vs.verify_targets({"t": target("0" * 64)})
    assert rep["ok"] is False
    assert any("retrieval failed" in f for f in rep["targets"][0]["failures"])


def test_compressed_response_refused(monkeypatch):
    _allow_dns(monkeypatch)
    conn = _FakeConn([_FakeResp(headers={"Content-Encoding": "gzip"},
                                body=zlib.compress(b"x"))])
    monkeypatch.setattr(vs, "_open_connection", lambda h, p, ip: conn)
    with pytest.raises(vs.RetrievalError, match="Content-Encoding"):
        vs.fetch("https://example.org/x.pdf")


# ---------------------------------------------------------------------------
# offline / deterministic modes
# ---------------------------------------------------------------------------

def test_offline_archive_mode_verifies_without_network():
    pytest.importorskip("pypdf")
    pdf = make_pdf("gamma = 2.3")
    rep = vs.verify_targets({"t": target(sha(pdf))},
                            archive={sha(pdf): pdf})
    assert rep["ok"] and "fully_verified" in rep["targets"][0]["levels"]
    # a missing artifact is a failure, never a skip
    rep = vs.verify_targets({"t": target(sha(pdf))}, archive={})
    assert rep["ok"] is False


def test_committed_derivations_all_reproduce():
    """CI-safe: every derivation recorded in the shipped targets file must
    recompute the committed value (and derived tolerance) exactly."""
    import json
    targets = json.loads(vs.TARGETS_PATH.read_text(encoding="utf-8"))["targets"]
    rep = vs.verify_derivations_only(targets)
    assert rep["ok"], rep["failures"]
    assert rep["n_derivations"] == 5
