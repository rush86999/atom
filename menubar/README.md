# Atom Menu Bar Companion

A development macOS companion for Atom, built with React, TypeScript and Tauri 2.
It provides interfaces for chat, agents, canvases, approvals and workflows.
Build verification does not establish that every interface works against a live backend.

## Verified build scope

The November 2026 build repair checks the strict TypeScript/Vite build, all 17
controlled WindowManager frontend tests, and a locked native Rust check and binary
build over the real frontend assets on Apple Silicon macOS. The local build used
Node 25.2.1, npm 11.6.2 and Rust/Cargo 1.98.1. These are observed versions, not a
minimum-version or cross-platform compatibility matrix.

No application launch, real account login, Keychain operation, global shortcut,
notification, installer, updater, signing/notarization or distribution was qualified
by that build checkpoint. See the source and test files for implementation details;
controlled frontend mocks do not certify the corresponding OS or backend operation.

## Prerequisites

- macOS with Xcode or its command-line tools and a working native Rust toolchain.
- Node.js and npm; use the checked-in npm lockfile.
- The configured Tauri bundle minimum is macOS 10.15. That setting is not evidence
  that this locked dependency set runs on every macOS version from 10.15 onward.
- An Atom backend is needed for actual account and task operations, not compilation.

See the [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/) and
[Vite integration guide](https://v2.tauri.app/start/frontend/vite/).

## Install and check

Run from this directory:

```bash
npm ci --ignore-scripts
npm run build
npm test -- --runInBand --watch=false
cd src-tauri
cargo check --locked
cargo build --locked
```

Build the frontend first: the native context embeds the real `../dist` assets.
Do not substitute an empty directory to make the native build pass. Jest uses its
local crawler (`watchman: false`), without modifying a global Watchman installation.

## Development and packaging

`npm run dev` starts Vite. `npm run tauri:dev` starts the native application and
can access OS facilities; that is a separate runtime exercise. Development and
packaging must use an explicitly configured test account/backend.

`npm run tauri:build` invokes the packaging path. It is not covered by the binary
build above. The checked-in bundle configuration still contains placeholder
signing identity and updater public-key values. Configure and independently verify
signing, notarization, updater trust and release artifacts before distribution.
No developer certificate or updater key is supplied by this repository checkpoint.

## Configuration and implementation boundaries

- Default endpoints are unchanged: HTTP `http://localhost:8000` and WebSocket
  `ws://localhost:8000/ws/menubar`.
- Native HTTP commands resolve the base through `src-tauri/src/config.rs`.
  `ATOM_MENUBAR_BACKEND_URL` (preferred) or the repository-wide
  `ATOM_BACKEND_URL` convention overrides it. `ATOM_MENUBAR_WS_URL` overrides the
  WebSocket endpoint; when absent it is derived from the HTTP base.
- The frontend consumes the native `get_backend_config` result. An environment
  override wins over a stale stored value, so an isolated loopback verification
  launch cannot silently reach the default backend. Without an override,
  `localStorage.atom_server_url` (Settings > Server URL) applies.
- Isolated verification example, using a scratch backend on a separate loopback
  port: `ATOM_BACKEND_URL=http://127.0.0.1:8123 npm run tauri:dev`. This changes
  only the endpoint the companion targets; it does not start a backend, create
  data, or authorize a live account. Point it at a scratch backend, never the
  live development database.
- The Tauri content-security policy is a separate network boundary. It allows
  loopback HTTP/WebSocket origins on any port so an isolated scratch backend can
  be verified; the remote API origin is unchanged. Check it when changing
  destinations; do not remove it to make a connection succeed.
- Focused endpoint checks (no backend launch, no live data):
  `npm test -- --runInBand --watch=false src/__tests__/config.test.ts src/__tests__/backendPaths.test.tsx`
  and, from `src-tauri`, `cargo test --locked --bin atom-menubar config::`.
- Native code includes Keychain-backed session handling. Persistence and account
  behavior need a real, authorized runtime test; compilation is insufficient.
- `src-tauri/src/hotkeys.rs::register_hotkeys` is currently a placeholder.
  Keyboard labels, configured shortcuts and a `quick-chat-hotkey` event listener
  do not establish a working OS-wide shortcut or durable shortcut preferences.

## Architecture reference

- `src/MenuBar.tsx`: current-tab UI and command/event consumers.
- `src/config.ts`: frontend endpoint resolution (native override, stored
  Settings value, default).
- `src/types.ts` and `src/hooks`: shared frontend types and hooks.
- `src/__tests__/config.test.ts`: focused endpoint-resolution tests; no network.
- `src/components/__tests__/WindowManager.test.tsx`: controlled tab, event and
  command tests; no real OS integration.
- `src-tauri/src/main.rs`: application, tray and command registration.
- `src-tauri/src/config.rs`: native HTTP/WebSocket endpoint resolution and
  validation.
- `src-tauri/src/commands.rs`: native HTTP and session operations.
- `src-tauri/src/hotkeys.rs`: shortcut configuration and unfinished registration.
- `src-tauri/src/websocket.rs`: native WebSocket client.

Keep these boundaries explicit when adding functionality or extending the
qualification matrix. A successful build must not be presented as a working
installer, secure updater, live integration or universally compatible companion.

## License

See the repository [LICENSE](../LICENSE).
