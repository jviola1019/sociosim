"""Scan decision-facing surfaces for unsupported claim language and legacy
assets.

Two layers:

1. Exact stale-phrase blacklist -- repo-wide, every tracked text file. These
   phrases have no legitimate context (retired filenames, retired/forbidden
   marketing-style claims), so a bare substring match is appropriate.

2. Context-aware risky-term scan -- restricted to the surfaces the brief
   actually names as claim-facing: docs (*.md), the web UI (*.html, *.js),
   and the CLI (run.py). Python *source* (imports, identifiers, module
   docstrings) is intentionally excluded from this layer: `socio_sim.
   validation`, `RunConfig.calibrated`, and similar are internal API names,
   not claims made to a user, and naively flagging every occurrence of
   "validation"/"calibration" there produces ~90% noise from import
   statements and module-path references (verified empirically while
   building this scanner -- see AUDIT_LOG.md R8-CLAIMSCAN). A term is only
   flagged if no hedge/negation marker appears nearby (e.g. "not a
   validation claim") and the surrounding phrase doesn't match a known-fine
   exemption (e.g. "Validation Ladder" is this project's named honesty-
   grading framework, not an empirical claim).

A file is skipped by the context-aware layer entirely if it carries a
"HISTORICAL RECORD" banner in its first ~2000 characters, or is in
CONTEXT_LAYER_FILE_EXEMPT (living retrospective documents -- changelogs and
completed sprint plans -- whose grammatical voice describes past shipped
work, not present-tense claims about the simulator's validity; the exact
stale-phrase layer above still applies to them in full).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Phrases with no legitimate context -- the correct way to comply with the
#: brief is to never write them at all (unlike e.g. "safety classifier",
#: which a correct disclaimer must legitimately say in negated form: "this is
#: not a safety classifier"). Kept deliberately short and proven: each entry
#: here was either an actual found violation or has zero current hits and is
#: not the kind of phrase a correct disclaimer would naturally negate-quote.
STALE_PHRASES = [
    "feed-atlas-v3",
    "ad-atlas-v3",
    "feed-cover-v3",
    "ad-creative-v3",
    "real trained",
    "real model",
    "decision-grade campaign winner",
    "CUPED lift",
    "visually verified",
    "evidence-based",
]

#: Files fully exempt from both layers: meta/process documentation that
#: discusses claim language, renames, and scanner design itself in service
#: of explaining what was fixed -- not a claim surface.
ALLOW = (
    "scripts/claim_scan.py",
    "scripts/asset_qa.py",
    "AUDIT_REMEDIATION_REPORT.md",
    "BASELINE_AUDIT_SNAPSHOT.md",
    "AUDIT_LOG.md",
    "HANDOFF.md",
    "SOURCE_LEDGER.md",
)

# Context-aware layer: file extensions in scope, plus run.py for CLI help text.
CONTEXT_LAYER_EXTENSIONS = {".md", ".html", ".js"}
CONTEXT_LAYER_EXTRA_FILES = {"run.py"}

# Living retrospective documents / explanatory rename notes. Their voice is
# "we built X" or "this used to be called Y", true statements about shipped
# code or past naming, not a present claim about empirical validity. The
# stale-phrase layer still scans them.
CONTEXT_LAYER_FILE_EXEMPT = {
    "CHANGELOG.md",
    "PLAN_P2.md",
    "CALIBRATION_REPORT.md",
}

HISTORICAL_MARKER = "HISTORICAL RECORD"

RISKY_TERMS = [
    r"\bvalidat(?:ed|es|ion|ions)\b",
    r"\bcalibrat(?:ed|es|ion|ions)\b",
    r"\bconfiden(?:ce|t)\b",
    r"\bcausal(?:ly)?\b",
    r"\bdecision[- ]ready\b",
    r"\bproduction[- ](?:ready|grade|classifier|model|guard|safe)\b",
    r"\bvisual(?:ly)? verif(?:y|ied|ication)\b",
    r"\bpredictive\b",
    r"\bverified\b",
]

# Phrases naming this project's own honesty-grading vocabulary or describing
# software-level (schema/structural) checking rather than an empirical claim
# about the real world. Matched case-insensitively as substrings of the
# scanned window; presence anywhere in the window clears the flag.
EXEMPT_PHRASES = (
    "validation ladder",
    "validation-ladder",
    "validates dimensions",
    "validates registry",
    "deterministic replay verified",
    "replay-verified",
    "browser-verified",
)

NEGATION_RE = re.compile(
    r"\b(not|no|never|isn'?t|doesn'?t|without|lacks?|cannot|can'?t|"
    r"non-|unsupported|incomplete|nor|does not|do not|did not|"
    r"not a |not an |not yet|not be |not used|not claim|not state|not imply|"
    r"not derived|not measured|pending|not performed|invalid uses?|"
    r"not claimed|skipped|disabled|absent)\b",
    re.IGNORECASE,
)

WINDOW = 60   # characters of context before a match to scan for a hedge/exemption
TRAILING = 40  # characters after a match to scan for an exempt phrase


def tracked_files() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return [ROOT / line for line in out.splitlines()]


def _stale_phrase_errors(rel: str, text: str) -> list[str]:
    lower = text.lower()
    return [f"{rel}: unsupported/stale phrase {pat!r}"
            for pat in STALE_PHRASES if pat.lower() in lower]


#: Markdown inline-code spans (`like.this`) are almost always Python module
#: paths or identifiers in this repo's docs, not prose claims -- blank them
#: out before scanning so e.g. `validation/benchmark_eval.py` doesn't trip
#: the bare word "validation".
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

_IMPORT_LINE_RE = re.compile(r"^\s*(from\s+\S+\s+import\b|import\s+\S+)")


def _context_aware_errors(rel: str, text: str) -> list[str]:
    scan_text = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group(0)), text)
    errors = []
    for term in RISKY_TERMS:
        for m in re.finditer(term, scan_text, re.IGNORECASE):
            line_no = scan_text.count("\n", 0, m.start()) + 1
            line = text.splitlines()[line_no - 1].strip()
            if _IMPORT_LINE_RE.match(line):
                continue
            # Dict/attribute access on a code identifier (e.g. study['calibration']),
            # not prose -- the identifier's own naming is tracked separately
            # (see AUDIT_LOG.md R9-OVERCLAIM deferred backend-rename note).
            if scan_text[max(0, m.start() - 2):m.start()] in ("['", '["'):
                continue
            start = max(0, m.start() - WINDOW)
            window = scan_text[start:m.end() + TRAILING]
            if NEGATION_RE.search(window):
                continue
            if any(phrase in window.lower() for phrase in EXEMPT_PHRASES):
                continue
            errors.append(
                f"{rel}:{line_no}: unhedged {m.group(0)!r} -> {line[:140]}")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOW or path.suffix.lower() in {".png", ".gz", ".coverage"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        errors.extend(_stale_phrase_errors(rel, text))

        in_scope = (path.suffix.lower() in CONTEXT_LAYER_EXTENSIONS
                    or path.name in CONTEXT_LAYER_EXTRA_FILES)
        if (in_scope and rel not in CONTEXT_LAYER_FILE_EXEMPT
                and HISTORICAL_MARKER not in text[:2000]):
            errors.extend(_context_aware_errors(rel, text))

    if errors:
        print("\n".join(errors[:80]))
        return 1
    print("claim scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
