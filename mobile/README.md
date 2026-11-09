# Mobile companion — development reference

Atom's React Native companion is under repair. The web application's accepted
workflows do not establish mobile build readiness or device support. This
reference describes the checked-in companion at source `0d9449d76`; later changes
must be reviewed against their own source and evidence.

## Dependencies and local checks

The lockfile currently resolves Expo 50, React Native 0.73.6 and React 18.2.
Controlled repairs used Node 20.20.2 on macOS ARM64. The existing dependency
compatibility gaps, including the MMKV API/native combination, are still open;
this is not a supported-platform matrix or an SDK-upgrade claim.

From the repository root, the controlled JavaScript install used:

```bash
cd mobile
npm ci --ignore-scripts --no-audit --no-fund
npm run typecheck
```

Skipping install scripts was intentional for these controlled checks. It does
not prepare native modules or demonstrate an iOS/Android build. The strict
project-wide type check still fails with 211 diagnostics at this source (402 at
`2abf3c689`; 354 at `2a5345b5b`). Keep its complete source/test scope;
do not hide errors with exclusions, ambient module shims or weaker settings.

One reproducible controlled camera selection is:

```bash
npm test -- src/__tests__/services/cameraService.test.ts \
  src/__tests__/services/cameraService.sdk.test.ts \
  src/__tests__/services/cameraService.video-sdk.test.ts \
  src/__tests__/screens/device/CameraScreen.test.tsx \
  --runInBand --watch=false --watchman=false
```

The video packet's frozen four-file selection passes 124 cases. These SDK-shaped
doubles exercise consumer behavior, not a physical camera, permission prompt,
photo-library write or native preview. Exact source and capture limitations are
in the evidence linked below. A successful narrow Jest selection does not
cancel the failing project-wide compiler or qualify the entire companion.

## Current evidence and remaining behavior

| Area | Established controlled scope | Still open |
| --- | --- | --- |
| Camera and gallery | Installed SDK ownership, permission calls, single barcode callback plus existing batch-service compatibility, gallery-selection fields, permission and awaited gallery-write refusal/success paths; exact video completion joins and mounted-settings validation; 124 selected cases at `d1f51887b`. | Native capture/preview, actual gallery writes and recording guarantees; camera/result navigation and video UI controls; automatic document edge detection is a placeholder. |
| Notification acquisition | Current permission and exact optional user/device cache binding; 169 selected notification/context cases at `70030548e`. | Confirmed backend registration, delivery and actual OS/device behavior. Acquiring an SDK token is not a durable backend registration receipt. |
| Forms and chat | Focused controls for numeric/length validation, installed picker APIs and swipe actions are being retained during repair. | Complete compiler/build, integrated mobile journeys, native access and end-to-end task completion. |
| Storage and offline work | Installed MMKV4 wrapper; serialized existing queue writes, retained failed/unsent work, persisted UI retry/priority/delete and truthful incomplete outcomes; 743 selected controls at `11be7eb1c`. Fourteen-day retention is simulated time. | Native MMKV/encrypted migration, current-session binding, safe automatic startup, interrupted/uncertain effects and real elapsed soak. Controlled storage/UI tests do not establish those behaviors. |
| Session recovery | Request-owned generation, conditional login/refresh commits, server expiry, single-flight refresh, startup and mounted revocation controls; 808 combined controls at `ae102ca2d`. | Native restart/migration, full application bootstrap, live account/backend/device ownership and unknown-effect reconciliation. |
| Sync reporting | Queue-derived unresolved counts, observed pass IDs/results and entity counters, current-result validation and once-only completion callbacks; 965 combined controls at `2abf3c689`, including the real service/modal join with controlled transport and storage. | Native persistence/restart, current-account queue authority, full app bootstrap, actual API/business-result and unknown-effect recovery qualification. |
| Location ownership | Installed subscription removal, shared pending starts, stop-generation fencing, stale callback refusal and retryable failed removal; 96 service controls plus 67 screen/agent controls at `2a5345b5b`. | Actual OS permissions/background location, physical GPS stopping, device and complete mobile journeys. |
| Voice input | Mounted component supplies the installed Expo AV high-quality preset; 72 component controls at `9bb7c99a3`. | No production import caller found for this component; real microphone, native permissions, recording files and integrated chat wiring remain unqualified. |

The latest combined controlled selection at `0d9449d76` has 1,659 passes,
zero failures and two intentional platform-registration sentinels skipped across
43 files. The generic verification driver therefore remains false under its
zero-skips rule; this is not 1,661 executed passes or a qualified mobile build.

Source-bound packets:

- [Reviewed fixture and final photo material controls](../docs/acceptance/evidence/mobile_reviewed_fixture_batch_0d9449d76/README.md)
- [Partial remote-camera result repair and remaining work](../docs/acceptance/evidence/mobile_remote_camera_material_3f2713057/README.md)
- [Canvas NetInfo SDK controls](../docs/acceptance/evidence/mobile_canvas_netinfo_d03046af4/README.md)
- [Location start/stop ownership](../docs/acceptance/evidence/mobile_location_ownership_2a5345b5b/README.md)
- [Location subscription and truthful callers](../docs/acceptance/evidence/mobile_location_subscription_11b54c2ea/README.md)
- [Voice recording preset](../docs/acceptance/evidence/mobile_audio_preset_9bb7c99a3/README.md)
- [Platform helper contracts](../docs/acceptance/evidence/mobile_platform_helpers_92807406b/README.md)
- [Storage test helper contracts](../docs/acceptance/evidence/mobile_test_storage_helpers_8e47aab00/README.md)
- [Observed sync results](../docs/acceptance/evidence/mobile_sync_observed_results_2abf3c689/README.md)
- [Session recovery controls](../docs/acceptance/evidence/mobile_session_recovery_ae102ca2d/README.md)
- [Camera/gallery SDK controls](../docs/acceptance/evidence/mobile_camera_sdk_8ef724ee0/README.md)
- [Offline queue preservation controls](../docs/acceptance/evidence/mobile_offline_queue_11be7eb1c/README.md)
- [Storage SDK controls](../docs/acceptance/evidence/mobile_storage_sdk_7441ef81d/README.md)
- [Video completion controls](../docs/acceptance/evidence/mobile_video_completion_d1f51887b/README.md)
- [Notification cache subject controls](../docs/acceptance/evidence/mobile_notification_subject_70030548e/README.md)

## Configuration and credentials

Configuration is not yet unified. The generic [API service](src/services/api.ts)
uses a development/production URL selected by `__DEV__`, while
[AuthContext](src/contexts/AuthContext.tsx),
[DeviceContext](src/contexts/DeviceContext.tsx) and the
[notification service](src/services/notificationService.ts) read Expo
`extra.apiUrl` with a localhost fallback. Copying `.env.example` does not prove
those consumers use `API_BASE_URL` or `WEBSOCKET_URL` from that file. Verify the
actual request target before making a connection claim. A phone's localhost is
the phone, not the development computer.

Do not put a backend signing secret, provider secret or private credential in a
mobile bundle or commit it to configuration. Existing session storage goes
through [secureTokenStorage](src/storage/secureTokenStorage.ts); its native
Keychain/keystore and migration behavior still need device qualification.
Backend authentication and authorization remain authoritative.

## Native development and distribution

The checked-in `start`, `ios`, `android` and `web` scripts are development entry
points, not proof of a working native build. The existing `build:ios` and
`build:android` scripts still invoke the old `expo build:*` interface and are not
qualified release instructions. Expo's
[build setup](https://docs.expo.dev/build/setup/) and
[CLI reference](https://docs.expo.dev/eas/cli/) describe its current `eas`
interface; adopting a release path here still requires SDK compatibility,
configuration, credentials and an independently verified build.

No simulator/device launch, live account, OS permission operation, push delivery,
developer signing, store upload or deployment follows from the controlled repair
packets. Preserve existing native files and user data while qualifying those
steps. Use isolated test accounts and scratch backends, never the live developer
world, for destructive or persistence controls.
