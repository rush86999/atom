# Mobile test-storage helper contracts

Runtime bytes match `8e47aab00`. Captures retain their actual recorded base and
working-tree status; all five input sets match the declared Git freezes,
250/251 files each, with no reconstruction or relabeling of historical runs.

## Repairs

The existing helper baseline had 37 failures: 36 called removed MMKV `removeAll`,
and one expected `null` from the installed SDK's missing-string getter. Helpers
now call `clearAll`; the reset assertion checks the real `undefined` contract.
The in-house optional test globals are typed from the installed MMKV interface,
not an invented SDK module or a new production store. Actual indexed SecureStore
and AsyncStorage tuple types are declared without compiler suppression.

The configured Flash CLI proposed the patch. Root rejected removal of the
explicit fallback fixture: existing tests demonstrate that owner even though the
default setup does not create it. Three additional negatives exposed discarded
orphan seeds and readback losing zero/false. Orphan seeding now refuses; typed
number/boolean accessors preserve the actual values. The original fallback map
case remains supported. No test case was removed or newly skipped.

## Results and exact skip boundary

Helper suite: 100 passing assertions, zero failures, two unchanged intentional
platform-registration skips. Combined selection: 1,065 passing assertions across
28 actual files, zero failures and the same two registrations. Their names and
the original/final Jest reports are retained in `verification.json` and artifacts.
They test the registration utility's deliberate skip behavior; this is not proof
that the skipped callback bodies ran on another platform.

The generic driver's `verification_pass` remains **false** because it requires
zero pending tests. Its successful raw process exits and pending records were
not rewritten, and no blanket green-gate override was added. Strict full-project
compilation still exits 2 with 374 diagnostics (previously 402). This packet does
not qualify the mobile build, native storage, app startup or business effects.

The proposal, exact public input and root adjudication are preserved. Only the
root-reviewed helper changes were applied; no production implementation,
provider, credential, SDK version, compiler option, new module shim or test
suppression was used. No live model call in the app, real account, OS permission,
remote business effect or deployment was exercised.
