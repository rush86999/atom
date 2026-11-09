# Canvas NetInfo SDK contract

Product source d03046af4. Existing service/screen tests now model the installed NetInfo module: default object plus named functions, no invented NetInfo alias; addEventListener returns a callable unsubscribe, not {remove}. Negative 51db82f9d: 69 passed / 6 failed. Corrected runtime:75/75, zero skips. Cache/offline behavior retained.

The prior permissive test doubles hid a real service import failure and a mounted screen listener leak. Final strict compiler still fails with351 diagnostics(previous354), not a full build pass. All captured mobile source bytes match declared Git freeze; original dirty capture metadata retained, no clean served-app identity implied. No actual OS network/device/application journey was run. Prior34file location regression remains attributed to2a5345b5b, not silently rerun or reattributed.
