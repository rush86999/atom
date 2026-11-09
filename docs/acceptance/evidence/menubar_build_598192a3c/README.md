# Menu bar build repair — controlled scope

Frozen source: `598192a3c`. This is build qualification, not a native user journey.

## Actual observations

- Initial strict frontend build failed on two malformed JSX expressions.
- Fixing those exposed 146 TypeScript diagnostics: production consumer/type
  mismatches plus missing test infrastructure and stale fixtures.
- Reviewed native OpenCode Go DeepSeek Flash proposals supplied bounded patches;
  root traced consumers and applied them. No model was installed or substituted.
- The first meaningful Jest run passed 16/17: the remaining fixture expected
  mutually exclusive panels together. The corrected test clicks real tabs,
  preserves prior assertions and verifies inactive panels disappear and agent
  data survives switching. All 17 original cases now pass, none skipped.
- Strict TypeScript and the real Vite build pass. No compiler settings were
  relaxed and no source or test was excluded.
- Native check initially refused absent frontend assets. With the actual built
  assets, `cargo check --locked` and `cargo build --locked` both passed.
- Node 25.2.1/npm 11.6.2; native ARM64 Rust/Cargo 1.98.1; Xcode developer tools.
  This is not a claim that older toolchains or all macOS versions are supported.

## Attribution and limits

Raw runs preceded the frozen commit; exact recorded source digests were compared
with that commit. Native input proof retains captured specs and confirms their
listed source inputs. Negative logs are preserved: initial syntax failure,
146-diagnostic intermediate, missing-asset native refusal and the 16/17 test run.
An earlier Watchman attempt returned zero without a test report and is explicitly
not counted. Jest now uses its local crawler, leaving global Watchman untouched.

The README and three appended CI steps were added after local compilation;
hosted Node 20 qualification is separate. Generated Rust schema files were restored
to their original bytes; no generated binary, dist tree or build cache is committed.
The frozen npm/Cargo lockfiles are committed for reproducibility.

No app launch, Keychain or account access, OS permission, working global shortcut,
notification, signing/notarization, installer/updater or distribution was tested.
The source still has placeholder shortcut registration and split native/frontend
server URL configuration; the companion README now states both accurately.
Those functionality goals and wider compatibility remain open.
