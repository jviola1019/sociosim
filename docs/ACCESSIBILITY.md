# Accessibility — WCAG 2.2 AA self-audit

**Status: automated + scripted conformance checks pass. This is a
self-audit, not a certification.**

What that distinction means, precisely:

- **ADA certification: NOT CLAIMED.** No third party has audited this
  interface, and no legal conformance claim is made.
- **No assistive-technology user testing has been performed.** Automated
  tooling and scripted browser checks cannot substitute for a screen-reader
  user driving the app; roughly a third of WCAG success criteria are not
  machine-decidable at all.
- What *is* true: every machine-checkable WCAG 2.2 A/AA rule that axe-core
  implements reports **zero violations** on both themes, and the
  criteria below that require behavioural verification are covered by
  scripted Playwright assertions that run in CI on every push.

## Evidence

Gate: `tests/test_a11y_axe.py` (CI step "Accessibility gate"). It runs
axe-core with the rule tags `wcag2a wcag2aa wcag21a wcag21aa wcag22a
wcag22aa`, fails the build on any serious/critical violation, and scans:

- the initial configuration view,
- the rendered results view after a real simulation,
- the **dark** theme as well as the light one,
- under `prefers-reduced-motion` (which the CSS honours).

Measured 2026-07-13: **0 violations, light and dark.**

## Criterion-by-criterion

| Criterion | Status | Evidence |
|---|---|---|
| 1.1.1 Non-text content | pass | Every asset carries alt text from the registry (`accessibility_alt_template`, enforced by `evidence_gate.py`); charts expose `role="img"` + an `aria-label` **and** an `.sr-only` summary carrying the actual data (totals, peak hour, counts) — asserted to contain digits, not just the title. |
| 1.3.1 Info and relationships | pass (axe) | Landmarks (`header`/`main`/`aside`/`section`), `role="tablist"`, labelled form controls. |
| 1.4.3 Contrast (minimum) | pass | axe on both themes. Five real defects were found and fixed by this gate (version badge 1.43:1; white-on-`#0a84ff` 3.64:1; an `opacity`-created stacking context at 1.07:1; lens badge 4.35:1; and a dark-mode nav bar that was still using the light glass token, 1.6:1). |
| 1.4.4 Resize text / 1.4.10 Reflow | pass | Scripted: no horizontal document scroll at **320 CSS px**; focus ring still rendered at **200 % zoom**. |
| 1.4.11 Non-text contrast | pass (axe) | — |
| 1.4.12 Text spacing / 1.4.13 Hover-focus content | pass (axe) | — |
| 2.1.1 Keyboard / 2.1.2 No trap | pass | Scripted: Tab moves focus off `<body>`; the history drawer opens from the keyboard, traps focus, and returns it. |
| 2.4.1 Bypass blocks | pass | Skip link is the first tab stop, visible on focus, and moves focus into the focusable `#output` region (asserted). |
| 2.4.3 Focus order / 2.4.7 Focus visible | pass | Scripted: focus returns to the drawer's opener on Escape; the `:focus-visible` outline is asserted under **real** keyboard focus (an earlier version of this check queried `getComputedStyle(..., ':focus-visible')`, which silently returns `''` — it was vacuous and was fixed). |
| 2.4.11 Focus not obscured (min) — **2.2** | pass (axe) | — |
| 2.5.8 Target size (minimum) — **2.2** | pass | Scripted: every interactive control's **effective** pointer target ≥ 24×24 CSS px. Checkboxes render 13×13 but are wrapped in `<label>`, so the label is the activation target; the test measures the label, not the input. |
| 3.2.6 Consistent help / 3.3.7 Redundant entry — **2.2** | pass (axe) | — |
| 3.3.2 Labels or instructions | pass | Every control has a label; sliders expose units and `aria-valuetext`. |
| 4.1.2 Name, role, value / 4.1.3 Status messages | pass | Results region is `aria-live` + `role="status"`. |
| 2.3.3 Animation from interactions (AAA) | honoured | `prefers-reduced-motion` fallbacks in CSS; the gate scans under it. |

## Known gaps (not claimed as conformant)

- **Screen-reader user testing: not performed.** Names and roles are
  asserted programmatically; how the app actually *sounds* in JAWS/NVDA/
  VoiceOver is unverified.
- **Exported reports** are Markdown; they preserve heading structure and
  alt text but have not been audited as standalone accessible documents.
- **Cognitive-load and plain-language** criteria are unaudited.
- The canvas network view exposes an `aria-label` describing the graph, but
  it has no keyboard-navigable equivalent of the hover-to-inspect
  interaction. The same data is available in the audit-log and charts tabs.
