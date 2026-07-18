"""Fail-closed re-verification of the sourced aggregate targets.

Every target in socio_sim/data/benchmarks/sourced_aggregates_v1.json is
verified to an explicit LEVEL, and the run exits 0 only when every target
reaches its required level. Levels (ordered):

    artifact_retrieved        the recorded artifact URL was fetched safely
    artifact_hash_matched     retrieved bytes match the recorded SHA-256
    text_extracted            non-empty text was extracted (pypdf for PDFs)
    statistic_quote_matched   every recorded quote pattern found in the text
    derivation_reproduced     the recorded derivation recomputes the value
                              (and derived tolerance) from the quoted inputs
    fully_verified            all applicable checks above passed

Fail-closed rules (audit Phase 2):
- missing pypdf for a PDF is a FAILURE, never a skipped warning;
- empty extracted text is a FAILURE;
- a missing quote pattern is a FAILURE;
- a matching hash alone is NOT statistic verification;
- a MUTABLE source's hash mismatch stays a warning only while every quote
  still matches -- and such a target is never reported fully_verified;
- an immutable source's hash mismatch is a FAILURE;
- derivations are REPRODUCED by executing the recorded derivation spec,
  never asserted.

Hardened retrieval (audit Phase 3): HTTPS-only; credentials in URLs
rejected; hostnames normalized (lowercase/IDNA); DNS is resolved BEFORE
connecting and every resolved address must be public (loopback, private,
link-local, multicast, reserved, unspecified all rejected -- stricter than
the app's local-LLM policy on purpose); redirects are followed manually
(max 3) with every destination re-validated; identity encoding only (no
decompression); Content-Length is checked before reading and the download
is streamed with a hard byte cap; separate connect/read timeouts; the
final URL is recorded in the report.

Offline modes (deterministic, no network):
    --derivations-only         recompute every recorded derivation (CI-safe)
    --offline DIR              verify archived artifacts from DIR (matched
                               by SHA-256) through the same text/quote/
                               derivation pipeline

Network verification is developer tooling: run it manually or scheduled,
not in the default CI path.

Exit status: 0 = every target reached its required level, 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import ipaddress
import json
import re
import socket
import ssl
import statistics
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
TARGETS_PATH = ROOT / "socio_sim" / "data" / "benchmarks" / "sourced_aggregates_v1.json"

#: stability values whose hash mismatch is fatal (artifact claimed immutable)
IMMUTABLE_STABILITIES = {"immutable_versioned_arxiv_pdf"}

LEVELS = ("artifact_retrieved", "artifact_hash_matched", "text_extracted",
          "statistic_quote_matched", "derivation_reproduced", "fully_verified")

MAX_BYTES = 25 * 1024 * 1024          # hard artifact cap (largest is ~1 MB)
MAX_REDIRECTS = 3
CONNECT_TIMEOUT_S = 15.0
READ_TIMEOUT_S = 60.0
_CHUNK = 64 * 1024
_UA = "sociosim-source-verify/2.0"

#: content types acceptable per recorded content_kind
_CONTENT_TYPES = {
    "pdf": ("application/pdf", "application/octet-stream"),
    "html": ("text/html", "application/xhtml+xml"),
}


class RetrievalError(Exception):
    """Controlled retrieval failure (never an unhandled traceback)."""


# --------------------------------------------------------------------------
# hardened retrieval
# --------------------------------------------------------------------------

def _normalize_host(host: str) -> str:
    host = (host or "").strip().rstrip(".").lower()
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise RetrievalError(f"hostname {host!r} fails IDNA normalization: {exc}")


def _validate_url(url: str):
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise RetrievalError(f"non-HTTPS URL refused: {url}")
    if parts.username or parts.password:
        raise RetrievalError(f"credentials embedded in URL refused: {url}")
    if not parts.hostname:
        raise RetrievalError(f"URL has no hostname: {url}")
    return parts


def _resolve_public(host: str) -> str:
    """Resolve BEFORE connecting; every address must be publicly routable.
    Source verification has no business talking to private networks, so
    this is deliberately stricter than the app's local-LLM allow-list.

    Returns the first validated IP: the connection dials EXACTLY that
    address (see _PinnedHTTPSConnection). Without pinning there is a
    second DNS lookup inside http.client between this check and the
    connect -- the classic rebinding TOCTOU (flagged by security review;
    same fix as the app's E-05 LLM transport)."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise RetrievalError(f"DNS resolution failed for {host!r}: {exc}")
    if not infos:
        raise RetrievalError(f"DNS returned no addresses for {host!r}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_loopback or ip.is_private or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            raise RetrievalError(
                f"{host!r} resolves to non-public address {ip} -- refused")
    return str(infos[0][4][0])


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Dials the pre-validated IP while keeping TLS SNI + certificate
    hostname verification on the ORIGINAL hostname, so pinning does not
    weaken certificate checks and no rebindable second lookup exists."""

    def __init__(self, host, port, pinned_ip, timeout):
        super().__init__(host, port, timeout=timeout,
                         context=ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self):
        sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def _open_connection(host: str, port: int, pinned_ip: str):
    """Overridable in tests: returns an HTTPSConnection-like object that
    dials the pinned, already-validated IP."""
    return _PinnedHTTPSConnection(host, port, pinned_ip,
                                  timeout=CONNECT_TIMEOUT_S)


def fetch(url: str) -> tuple[bytes, str, str]:
    """Fetch an artifact under the hardened policy.

    Returns (bytes, final_url, content_type). Raises RetrievalError for
    every refused/failed condition (controlled, no unbounded reads)."""
    current = url
    for _hop in range(MAX_REDIRECTS + 1):
        parts = _validate_url(current)
        host = _normalize_host(parts.hostname)
        port = parts.port or 443
        pinned_ip = _resolve_public(host)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        conn = _open_connection(host, port, pinned_ip)
        try:
            conn.request("GET", path, headers={
                "User-Agent": _UA,
                "Host": parts.hostname,
                "Accept-Encoding": "identity",   # no decompression surface
            })
            resp = conn.getresponse()
            sock = getattr(conn, "sock", None)   # separate read timeout
            if sock is not None:
                sock.settimeout(READ_TIMEOUT_S)
            status = resp.status
            if 300 <= status < 400:
                loc = resp.getheader("Location")
                if not loc:
                    raise RetrievalError(
                        f"redirect ({status}) without Location from {current}")
                current = urljoin(current, loc)  # re-validated at loop top
                continue
            if status != 200:
                raise RetrievalError(f"HTTP {status} from {current}")
            enc = (resp.getheader("Content-Encoding") or "identity").lower()
            if enc not in ("", "identity"):
                raise RetrievalError(
                    f"unexpected Content-Encoding {enc!r} from {current} "
                    "(identity requested; refusing to decompress)")
            clen = resp.getheader("Content-Length")
            if clen is not None:
                try:
                    if int(clen) > MAX_BYTES:
                        raise RetrievalError(
                            f"artifact too large ({clen} bytes > {MAX_BYTES}) "
                            f"at {current} -- refused before download")
                except ValueError:
                    raise RetrievalError(
                        f"invalid Content-Length {clen!r} from {current}")
            buf = io.BytesIO()
            while True:
                try:
                    chunk = resp.read(_CHUNK)
                except (TimeoutError, socket.timeout) as exc:
                    raise RetrievalError(
                        f"read timeout after {READ_TIMEOUT_S}s from "
                        f"{current}: {exc}")
                if not chunk:
                    break
                if buf.tell() + len(chunk) > MAX_BYTES:
                    raise RetrievalError(
                        f"artifact exceeded the {MAX_BYTES}-byte cap while "
                        f"streaming from {current} -- aborted")
                buf.write(chunk)
            ctype = (resp.getheader("Content-Type") or "").split(";")[0].strip()
            return buf.getvalue(), current, ctype
        except (TimeoutError, socket.timeout) as exc:
            raise RetrievalError(f"connect/read timeout for {current}: {exc}")
        except (OSError, http.client.HTTPException) as exc:
            raise RetrievalError(f"transport failure for {current}: {exc}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
    raise RetrievalError(f"more than {MAX_REDIRECTS} redirects from {url}")


# --------------------------------------------------------------------------
# text extraction + derivation reproduction
# --------------------------------------------------------------------------

def _load_pypdf():
    """Overridable in tests; ImportError propagates to a FAILURE."""
    import pypdf
    return pypdf


def extract_text(data: bytes, content_kind: str) -> str:
    """Non-empty extracted text, or RetrievalError (fail closed: a PDF with
    no pypdf, or empty extraction, must FAIL -- never silently skip)."""
    if content_kind == "html":
        text = re.sub(r"\s+", " ", data.decode("utf-8", errors="replace"))
        if not text.strip():
            raise RetrievalError("empty HTML text")
        return text
    try:
        pypdf = _load_pypdf()
    except ImportError as exc:
        raise RetrievalError(
            f"pypdf unavailable ({exc}); PDF quote verification REQUIRES it "
            "-- install the [evidence] extra")
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        text = re.sub(r"\s+", " ",
                      " ".join((p.extract_text() or "") for p in reader.pages))
    except Exception as exc:
        raise RetrievalError(f"PDF text extraction failed: {exc}")
    if not text.strip():
        raise RetrievalError("PDF text extraction produced empty text")
    return text


def reproduce_derivation(spec: dict, target_value: float,
                         target_tolerance: float) -> tuple[bool, str]:
    """Execute the recorded derivation and compare against the target.
    Returns (ok, detail). Unknown kinds are a failure (fail closed)."""
    kind = spec.get("kind")
    try:
        if kind == "mean_and_sample_sd":
            vals = [float(x) for x in spec["inputs"]]
            value = round(statistics.mean(vals), spec["expected_value_round"])
            tol = round(statistics.stdev(vals), spec["expected_tolerance_round"])
            ok = (value == round(target_value, spec["expected_value_round"])
                  and tol == round(target_tolerance,
                                   spec["expected_tolerance_round"]))
            return ok, f"mean={value}, sample_sd={tol}"
        if kind == "midpoint_halfwidth":
            lo, hi = (float(x) for x in spec["inputs"])
            value = round((lo + hi) / 2, spec["expected_value_round"])
            tol = round((hi - lo) / 2, spec["expected_tolerance_round"])
            ok = (value == round(target_value, spec["expected_value_round"])
                  and tol == round(target_tolerance,
                                   spec["expected_tolerance_round"]))
            return ok, f"midpoint={value}, halfwidth={tol}"
        if kind == "weighted_mean_per_day":
            d = spec["inputs"]
            per_month = sum(s * m for s, m in zip(d["shares"], d["monthly"]))
            value = round(per_month / d["days_per_month"],
                          spec["expected_value_round"])
            ok = value == round(target_value, spec["expected_value_round"])
            return ok, f"weighted_mean_per_day={value}"
        if kind == "percent_to_fraction":
            value = round(float(spec["inputs"][0]) / 100.0,
                          spec["expected_value_round"])
            ok = value == round(target_value, spec["expected_value_round"])
            return ok, f"fraction={value}"
        if kind == "ratio":
            num, den = (float(x) for x in spec["inputs"])
            value = round(num / den, spec["expected_value_round"])
            ok = value == round(target_value, spec["expected_value_round"])
            detail = f"ratio={value}"
            if spec.get("tolerance_kind") == "halfwidth_of_range":
                lo, hi = (float(x) for x in spec["tolerance_inputs"])
                tol = round((hi - lo) / 2, spec["expected_tolerance_round"])
                ok = ok and tol == round(target_tolerance,
                                         spec["expected_tolerance_round"])
                detail += f", tolerance_halfwidth={tol}"
            return ok, detail
    except (KeyError, TypeError, ValueError, ZeroDivisionError,
            statistics.StatisticsError) as exc:
        return False, f"derivation spec error: {exc}"
    return False, f"unknown derivation kind {kind!r} (fail closed)"


# --------------------------------------------------------------------------
# per-target verification
# --------------------------------------------------------------------------

def required_level(spec: dict) -> str:
    """Every target requires its statistic quotes; derived values must also
    reproduce their derivation."""
    return ("derivation_reproduced" if spec.get("derivation")
            else "statistic_quote_matched")


def verify_target(name: str, spec: dict, data: bytes | None,
                  final_url: str | None, content_type: str | None,
                  retrieval_error: str | None = None) -> dict:
    art = spec.get("source_artifact") or {}
    levels: list[str] = []
    failures: list[str] = []
    warnings: list[str] = []
    hash_ok = False

    if not art:
        return {"target": name, "levels": [], "final_url": None,
                "failures": [f"{name}: no source_artifact block"],
                "warnings": [], "required": "statistic_quote_matched",
                "met_required": False}

    if retrieval_error is not None or data is None:
        failures.append(f"{name}: retrieval failed: {retrieval_error}")
    else:
        levels.append("artifact_retrieved")
        kind = art.get("content_kind", "pdf")
        allowed = _CONTENT_TYPES.get(kind, ())
        if content_type and allowed and content_type not in allowed:
            warnings.append(f"{name}: unexpected content-type "
                            f"{content_type!r} for {kind} artifact")
        actual = hashlib.sha256(data).hexdigest()
        if actual == art.get("sha256"):
            hash_ok = True
            levels.append("artifact_hash_matched")
        elif art.get("stability") in IMMUTABLE_STABILITIES:
            failures.append(
                f"{name}: sha256 mismatch on IMMUTABLE artifact "
                f"(recorded {str(art.get('sha256'))[:12]}..., retrieved "
                f"{actual[:12]}...)")
        else:
            warnings.append(
                f"{name}: sha256 mismatch (recorded "
                f"{str(art.get('sha256'))[:12]}..., retrieved {actual[:12]}...) "
                f"-- stability={art.get('stability')}; acceptable ONLY while "
                "every statistic quote still matches, and the target is NOT "
                "fully_verified")
        try:
            text = extract_text(data, kind)
            levels.append("text_extracted")
        except RetrievalError as exc:
            failures.append(f"{name}: {exc}")
            text = None
        if text is not None:
            quotes = art.get("verified_quotes", [])
            if not quotes:
                failures.append(f"{name}: no verified_quotes recorded -- "
                                "statistic cannot be re-located (fail closed)")
            else:
                missing = [q for q in quotes if not re.search(q, text)]
                if missing:
                    for q in missing:
                        failures.append(
                            f"{name}: quoted statistic pattern {q!r} NOT "
                            "found -- statistic_location no longer "
                            "reproducible")
                else:
                    levels.append("statistic_quote_matched")

    deriv = spec.get("derivation")
    if deriv:
        ok, detail = reproduce_derivation(
            deriv, float(spec["value"]), float(spec["tolerance"]))
        if ok:
            levels.append("derivation_reproduced")
        else:
            failures.append(f"{name}: derivation NOT reproduced ({detail})")

    req = required_level(spec)
    met = req in levels
    # fully_verified = every applicable check passed INCLUDING the hash;
    # a mutable-mismatch pass (rule 5) is deliberately not full verification.
    fully = (met and hash_ok and "text_extracted" in levels
             and "statistic_quote_matched" in levels
             and (not deriv or "derivation_reproduced" in levels)
             and not failures)
    if fully:
        levels.append("fully_verified")
    return {"target": name, "levels": levels, "final_url": final_url,
            "failures": failures, "warnings": warnings,
            "required": req, "met_required": met and not failures}


def verify_targets(targets: dict, fetcher=fetch,
                   archive: dict[str, bytes] | None = None) -> dict:
    """Verify every target. `archive` (sha256 -> bytes) enables offline
    mode; otherwise `fetcher` retrieves each distinct URL exactly once."""
    fetched: dict[str, tuple] = {}
    reports = []
    for name, spec in targets.items():
        art = spec.get("source_artifact") or {}
        url = art.get("artifact_url")
        data = final_url = ctype = None
        err = None
        if archive is not None:
            data = archive.get(art.get("sha256", ""))
            if data is None:
                err = "artifact not present in the offline archive"
            final_url = f"offline:{art.get('sha256', '')[:12]}"
        elif url:
            if url not in fetched:
                try:
                    fetched[url] = (*fetcher(url), None)
                except RetrievalError as exc:
                    fetched[url] = (None, None, None, str(exc))
            data, final_url, ctype, err = fetched[url]
        else:
            err = "no artifact_url recorded"
        reports.append(verify_target(name, spec, data, final_url, ctype,
                                     retrieval_error=err))
    counts = {lv: sum(1 for r in reports if lv in r["levels"]) for lv in LEVELS}
    return {
        "targets": reports,
        "counts_by_level": counts,
        "n_targets": len(reports),
        "ok": all(r["met_required"] for r in reports),
    }


def verify_derivations_only(targets: dict) -> dict:
    """Deterministic offline check (CI-safe): every recorded derivation must
    reproduce its target's value (and derived tolerance) from the quoted
    inputs. No network, no artifacts."""
    failures = []
    n = 0
    for name, spec in targets.items():
        deriv = spec.get("derivation")
        if not deriv:
            continue
        n += 1
        ok, detail = reproduce_derivation(
            deriv, float(spec["value"]), float(spec["tolerance"]))
        if not ok:
            failures.append(f"{name}: derivation NOT reproduced ({detail})")
    return {"n_derivations": n, "failures": failures, "ok": not failures}


def _print_report(report: dict) -> None:
    for r in report["targets"]:
        for w in r["warnings"]:
            print(f"WARN  {w}")
        for f in r["failures"]:
            print(f"FAIL  {f}")
    print("verification levels reached "
          f"({report['n_targets']} targets):")
    for lv in LEVELS:
        print(f"  {lv:<24} {report['counts_by_level'][lv]}/{report['n_targets']}")
    for r in report["targets"]:
        if r["final_url"]:
            print(f"  final URL {r['target']}: {r['final_url']}")
    if report["ok"]:
        print("every target reached its required verification level")
    else:
        bad = [r["target"] for r in report["targets"] if not r["met_required"]]
        print(f"NOT VERIFIED: {', '.join(bad)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", metavar="DIR",
                    help="verify archived artifacts from DIR (matched by "
                         "SHA-256); no network")
    ap.add_argument("--derivations-only", action="store_true",
                    help="deterministic offline derivation check (CI-safe)")
    args = ap.parse_args(argv)
    targets = json.loads(TARGETS_PATH.read_text(encoding="utf-8"))["targets"]

    if args.derivations_only:
        rep = verify_derivations_only(targets)
        for f in rep["failures"]:
            print(f"FAIL  {f}")
        print(f"derivations reproduced: "
              f"{rep['n_derivations'] - len(rep['failures'])}/{rep['n_derivations']}")
        return 0 if rep["ok"] else 1

    archive = None
    if args.offline:
        archive = {}
        for p in Path(args.offline).iterdir():
            if p.is_file():
                archive[hashlib.sha256(p.read_bytes()).hexdigest()] = p.read_bytes()
        print(f"offline archive: {len(archive)} artifact(s) indexed")

    report = verify_targets(targets, archive=archive)
    _print_report(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
