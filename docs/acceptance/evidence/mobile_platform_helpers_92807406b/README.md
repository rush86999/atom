# Mobile platform helper repair

Product source: 92807406b. Controlled Jest and strict TypeScript checks only; no native device, simulator, application or provider run.

The independent SDK contract was 4 passed / 6 failed before repair and is now 10 passed / 0 failed. Existing storage/helper selection is 104 passed / 0 failed / 2 intentional platform-registration sentinels skipped. The raw strict driver therefore retains verification_pass=false for that selection; no blanket pass is claimed. Full strict TypeScript still fails with 368 diagnostics (previously 374).

The existing Flash CLI supplied a patch proposal. Its claimed scratch test results are unverified model statements; only the separately retained local runner captures establish results here. Selected/native/default key presence follows installed React Native semantics, including explicit undefined. Jest factories retain argument tuples and return types without claiming arbitrary function properties. No compiler setting, dependency or production code changed.

Combined 28-file regression: 1069 passed, zero failed, the same two intentional registration skips. The independent platform contract is a separate 10-case selection.
