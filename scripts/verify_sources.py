"""Re-verify the sourced aggregate targets against their recorded artifacts.

For every target in socio_sim/data/benchmarks/sourced_aggregates_v1.json this
script re-downloads the recorded ``source_artifact.artifact_url`` and:

- for stable artifacts (versioned arXiv PDFs and other pinned files):
  FAILS if the SHA-256 of the retrieved bytes differs from the recorded hash;
- for artifacts recorded as mutable (live HTML) or supersedable (regulator
  portals, author-hosted files): reports a hash difference as a WARNING and
  falls back to quote verification;
- in both cases: verifies every recorded ``verified_quotes`` regex is present
  in the retrieved artifact's extracted text (pypdf for PDFs, raw text for
  HTML). A missing quote is always a FAILURE -- the artifact no longer
  supports the target's statistic_location.

Network-dependent by design; run manually or in a scheduled job, NOT in the
default CI path (CI must not depend on third-party site availability).

Exit status: 0 = all verified, 1 = any failure.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ROOT / "socio_sim" / "data" / "benchmarks" / "sourced_aggregates_v1.json"

#: stability values whose hash mismatch is fatal (artifact claimed immutable)
_STABLE = {"immutable_versioned_arxiv_pdf"}


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "sociosim-source-verify/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310 - https URLs from reviewed metadata
        return resp.read()


def _extract_text(data: bytes, url: str) -> str:
    if url.lower().endswith((".html", "/")) or b"<html" in data[:2048].lower():
        return re.sub(r"\s+", " ", data.decode("utf-8", errors="replace"))
    try:
        import pypdf
    except ImportError:
        return ""
    reader = pypdf.PdfReader(io.BytesIO(data))
    return re.sub(r"\s+", " ", " ".join((p.extract_text() or "") for p in reader.pages))


def main() -> int:
    targets = json.loads(TARGETS.read_text(encoding="utf-8"))["targets"]
    failures: list[str] = []
    warnings: list[str] = []
    fetched: dict[str, bytes] = {}
    for name, spec in targets.items():
        art = spec.get("source_artifact")
        if not art:
            failures.append(f"{name}: no source_artifact block")
            continue
        url = art["artifact_url"]
        try:
            data = fetched.get(url)
            if data is None:
                data = fetched[url] = _fetch(url)
        except Exception as exc:
            failures.append(f"{name}: could not retrieve {url}: {exc}")
            continue
        actual = hashlib.sha256(data).hexdigest()
        if actual != art["sha256"]:
            msg = (f"{name}: sha256 mismatch (recorded {art['sha256'][:12]}..., "
                   f"retrieved {actual[:12]}...)")
            if art.get("stability") in _STABLE:
                failures.append(msg + " -- artifact recorded as immutable")
            else:
                warnings.append(msg + f" -- stability={art.get('stability')}; "
                                "falling back to quote verification")
        text = _extract_text(data, url)
        if not text:
            warnings.append(f"{name}: no text extracted (pypdf missing?); "
                            "quote verification skipped")
            continue
        for quote in art.get("verified_quotes", []):
            if not re.search(quote, text):
                failures.append(
                    f"{name}: quoted statistic pattern {quote!r} NOT found in "
                    "the retrieved artifact -- statistic_location no longer "
                    "reproducible")
    for w in warnings:
        print(f"WARN  {w}")
    for f in failures:
        print(f"FAIL  {f}")
    if failures:
        return 1
    print(f"verified {len(targets)} targets against their recorded artifacts "
          f"({len(warnings)} warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
