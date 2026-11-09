# Mobile companion — development reference

Atom's React Native companion is under repair. The web application's accepted
workflows do not establish mobile build readiness or device support. This
reference describes the checked-in companion at source `d1f51887b`; later changes
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
project-wide type check currently fails. Keep its complete source/test scope;
do not hide errors with exclusions, ambient module shims or weaker settings.

One reproducible controlled camera selection is:

```bash
npm test -- src/__tests__/services/cameraService.test.ts \
  src/__tests__/services/cameraService.sdk.test.ts \
  src/__tests__/services/cameraService.video-sdk.test.ts \
  src/__tests__/screens/device/CameraScreen.test.tsx \
  --runInBand --watch=false --watchman=false
```

The frozen source's four-file selection passes 124 cases. These SDK-shaped
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
| Storage and offline work | Existing storage/queue implementations remain the consumer surfaces. | Installed MMKV contract, secure key/migration qualification, durable retry/prioritization and concurrent queue updates. |

Source-bound packets:

- [Camera/gallery SDK controls](../docs/acceptance/evidence/mobile_camera_sdk_8ef724ee0/README.md)
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
