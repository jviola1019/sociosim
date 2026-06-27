"""One-time data-insertion script (provenance record for docs/DATA_MANIFEST.md).

Fetches BALANCED, PII-scrubbed samples of two license-clean public moderation
benchmarks via the HuggingFace Dataset Viewer API (sanctioned official API, not
scraping) and writes them under socio_sim/data/benchmarks/moderation/:

  - civil_comments  (Google/Jigsaw, CC0-1.0)        -> toxicity (>=0.5) vs clean
  - spam_detection  (Deysi/spam-detection, Apache-2.0) -> spam vs not_spam

Re-run to regenerate. Output is gzipped JSONL of {"text", "label"} with text
truncated to 400 chars and emails/URLs/phones/@handles redacted (defense-in-depth;
both sources are already de-identified). Deterministic order (sorted by text).
"""

from __future__ import annotations

import gzip
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "socio_sim" / "data" / "benchmarks" / "moderation"
API = "https://datasets-server.huggingface.co/filter"
PER_CLASS = 1500
PAGE = 100
MAXLEN = 400

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_PHONE = re.compile(r"\+?\d[\d\-\s().]{7,}\d")
_HANDLE = re.compile(r"(?<!\w)@\w+")


def scrub(text: str) -> str:
    t = _URL.sub("[URL]", str(text))
    t = _EMAIL.sub("[EMAIL]", t)
    t = _PHONE.sub("[PHONE]", t)
    t = _HANDLE.sub("[USER]", t)
    return t[:MAXLEN].strip()


def fetch(dataset: str, where: str, n: int) -> list:
    rows, offset = [], 0
    while len(rows) < n:
        url = (f"{API}?dataset={urllib.parse.quote(dataset)}&config=default&split=train"
               f"&where={urllib.parse.quote(where)}&offset={offset}&length={PAGE}")
        batch = None
        for attempt in range(5):                         # retry transient 5xx
            try:
                with urllib.request.urlopen(url, timeout=45) as r:
                    batch = json.load(r).get("rows", [])
                break
            except Exception as exc:                     # noqa: BLE001 (one-off script)
                if attempt == 4:
                    print(f"  warn: offset {offset} failed ({exc}); "
                          f"stopping with {len(rows)} rows")
                time.sleep(1.5 + attempt)
        if not batch:
            break
        rows.extend(x["row"] for x in batch)
        offset += PAGE
        time.sleep(0.2)
    return rows[:n]


def write(path: Path, records: list):
    records = sorted(records, key=lambda r: r["text"])      # deterministic order
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Civil Comments (CC0): toxic vs clean
    tox = [{"text": scrub(r["text"]), "label": 1}
           for r in fetch("google/civil_comments", '"toxicity">=0.5', PER_CLASS)]
    clean = [{"text": scrub(r["text"]), "label": 0}
             for r in fetch("google/civil_comments", '"toxicity"<0.1', PER_CLASS)]
    cc = [r for r in (tox + clean) if r["text"]]
    write(OUT / "civil_comments.jsonl.gz", cc)
    print(f"civil_comments: {sum(r['label'] for r in cc)} toxic / {len(cc)} total")

    # Deysi spam-detection (Apache-2.0): spam vs not_spam
    spam = [{"text": scrub(r["text"]), "label": 1}
            for r in fetch("Deysi/spam-detection-dataset", '"label"=\'spam\'', PER_CLASS)]
    ham = [{"text": scrub(r["text"]), "label": 0}
           for r in fetch("Deysi/spam-detection-dataset", '"label"=\'not_spam\'', PER_CLASS)]
    sp = [r for r in (spam + ham) if r["text"]]
    write(OUT / "spam_detection.jsonl.gz", sp)
    print(f"spam_detection: {sum(r['label'] for r in sp)} spam / {len(sp)} total")


if __name__ == "__main__":
    main()
