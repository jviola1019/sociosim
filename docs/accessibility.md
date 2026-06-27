# Accessibility

Current status:

- Playwright E2E smoke test passes.
- Static UI includes semantic navigation, result tabs, focusable controls, and
  chart labels.

Remaining work:

- Add axe-core or equivalent automated accessibility checks.
- Provide data-table alternatives for charts, canvas/network views, and cascade
  graphics.
- Ensure graph details are keyboard accessible, not hover-only.
- Keep status communication color-independent.
- Verify reduced-motion, focus order, contrast, empty states, and responsive
  text wrapping before release.
