# Location subscription SDK and truthful stop consumers

Final product source 11b54c2ea; SDK repair da6cf71fb. Source-bound controlled Jest tests only, no device/OS permission or physical GPS stopping claim.

Service negative 45942a155: 87 passed / 2 failed. Installed expo-location returns LocationSubscription.remove(), not a numeric id or removeSubscriptionAsync. Native Flash proposal fixes handle/removal/preserved failed-stop state. Root also aligned all numeric and callback fixtures the proposal missed. Service final: 89/89. Initial partial candidate retained two failing obsolete fixture cases; no deletion or suppression.

Caller negative f1b8527c5: screen false OFF; agent bridge suite initially could not load because automocking camera imported native SDK. An explicit camera service double of the same three used capabilities restores the existing gate without mocking the location consumer. Restored negative at da6cf71fb: 65 passed / 2 failed. Final at 11b54c2ea: 67/67. Screen reads active/background state and reports failure; agent refuses success while still active.

Full strict compiler remains failed: 358 diagnostics, previously 366. No dependency/config/compiler changes. Pending start/stop race identified by model review remains open: late watch creation may resurrect tracking after stop. No physical-stop, permission, background OS or full-mobile-build qualification follows.
