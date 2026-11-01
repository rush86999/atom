# Unforced teaching interaction — blocked (2026-10-31)

**Result: did not pass.** This check deliberately avoids `fill(force=True)` and
DOM mutation, so it can show whether an ordinary user can operate the Teaching
form. On the current candidate the canvas page becomes CPU-bound as soon as the
Training panel is opened, before any form interaction.

## What was done (ordinary actions only)

1. Normal login through `/login`.
2. Onboarding dismissed by pressing **Escape** on the visible dialog
   (`sessionStorage atom.onboarding.dismissed = 1`, verified).
3. Navigated Agents → Teach → canvas; waited for the Training panel.
4. Sampled the main thread with `setTimeout(…, 0)` **before touching the form**.

## Observed

| Step | Result |
|---|---|
| Onboarding via Escape | pass (session key set, dialog hidden) |
| Training panel attached | pass |
| Main-thread sample after open | **timeout — blocked** |
| `<summary>` click on optional fields | timeout ("performing click action") |
| Full-page screenshot after the stall | timeout ("waiting for fonts to load") |

`training-stall-trace.zip` is the Playwright trace (screenshots + snapshots)
captured around the stall; `training-panel-before.png` is the last rendering
before the main thread stopped responding.

## Interpretation and limits

- This is not the onboarding overlay (dismissed first) and not a locator
  mistake (the element is attached and visible).
- It reproduces on an isolated run at source `5664c46c5` with a copied
  production build retargeted to port 8077. The product code is identical to
  `233fa587f` (only docs/tests changed between them), but the build was
  retargeted by string replacement, so a build-specific cause is not excluded.
- The successful long journey used `fill(..., force=True)` and direct DOM
  opening. That proves submitted values reach the backend; it does not prove an
  ordinary user can operate the form.

## Next executable action

Reproduce on a stock production build at the default ports and, if it holds,
profile the Training panel's render (trace flame graph; look for a
render/effect loop or an unbounded list). Until then, no usability claim is
made for the teaching surface.
