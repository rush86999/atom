# Tauri Canvas AI Context Verification Guide

**Purpose:** Verify Phase 20's canvas AI context (`window.atom.canvas`) works correctly in Tauri desktop application environment.

**Last Updated:** 2026-02-18

---

## Overview

This guide provides comprehensive manual testing steps for verifying that the canvas AI context, implemented in Phase 20, is accessible and functional in Tauri's desktop application. The canvas AI context enables AI agents to read canvas state without OCR by accessing structured JSON data via the `window.atom.canvas` global API.

**What's Being Tested:**
- `window.atom.canvas` API accessibility in Tauri webview
- Canvas state registration and retrieval
- Real-time canvas updates via subscriptions
- Accessibility trees (hidden divs with `role="log"`) presence in DOM
- Tauri IPC bridge (`window.__TAURI__`) coexistence with canvas API

**Why Manual Testing is Needed:**
- **Production Build Minification:** Terser may remove accessibility divs as "dead code" in production builds
- **Real Webview Context:** JSDOM tests (Plan 01) simulate browser but don't catch Tauri-specific issues
- **IPC Bridge Interaction:** Verify `window.__TAURI__` and `window.atom.canvas` don't conflict
- **Platform Differences:** WebView2 (Windows) vs. WebKit (macOS/Linux) behavior may differ

---

## Prerequisites

### Required Software

**1. Rust Toolchain**
```bash
# Verify Rust installation
rustc --version  # Should be 1.70+ or later
cargo --version
```

If not installed:
```bash
# macOS
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Windows
# Download from: https://rustup.rs/
```

**2. Node.js and npm**
```bash
node --version  # Should be 18+ or later
npm --version   # Should be 9+ or later
```

**3. Tauri CLI**
```bash
# Install Tauri CLI (if not already installed)
cargo install tauri-cli --version "^2.0.0"

# Verify installation
cargo tauri --version
```

### Platform-Specific Requirements

**macOS:**
- Xcode Command Line Tools: `xcode-select --install`
- Minimum OS version: macOS 10.15+

**Windows:**
- WebView2 Runtime (usually pre-installed on Windows 10/11)
- Visual Studio C++ Build Tools
- Verify WebView2: Check "Microsoft Edge WebView2" in Apps & Features

**Linux:**
- WebKit2GTK development libraries
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install libwebkit2gtk-4.0-dev \
    build-essential \
    curl \
    wget \
    file \
    libxdo-dev \
    libssl-dev \
    libayatana-appindicator3-dev
```

### Verify Setup

```bash
cd frontend-nextjs
npm run tauri:info
```

Expected output: System information showing Rust, Node.js, and platform dependencies are correctly installed.

---

## Development Build Verification

This section tests canvas AI context accessibility in Tauri development environment with hot-reload and DevTools enabled.

### Step 1: Start Development Server

```bash
cd frontend-nextjs
npm run tauri:dev
```

**Expected Behavior:**
- Terminal shows "Running beforeDevCommand" (npm run dev)
- Next.js dev server starts on http://localhost:3000
- Tauri window opens automatically after ~10-30 seconds
- Application loads in desktop window (not browser)

**Troubleshooting:**
- If window doesn't open, check for port conflicts (3000 already in use)
- If build fails, run `npm install` to ensure dependencies are current
- If Tauri shows error, verify Rust toolchain: `rustc --version`

### Step 2: Open DevTools

Once Tauri window opens:

**macOS:** Press `Cmd+Option+I`
**Windows/Linux:** Press `Ctrl+Shift+I`

DevTools panel should open, similar to Chrome DevTools.

### Step 3: Verify Canvas API Accessibility

**Test 1: Verify window.atom.canvas exists**

In DevTools Console tab, run:

```javascript
typeof window.atom?.canvas
```

**Expected Output:** `"object"`

**If undefined:**
- Navigate to a page with canvas components (e.g., AgentOperationTracker)
- Wait for component to mount
- Re-run the check

---

**Test 2: Verify API methods exist**

```javascript
['getState', 'getAllStates', 'subscribe', 'subscribeAll'].every(method =>
  typeof window.atom.canvas[method] === 'function'
)
```

**Expected Output:** `true`

**If false:**
- Canvas API not fully initialized
- Check console for initialization errors
- Verify `useCanvasState` hook is being used in components

---

**Test 3: Verify Tauri IPC coexistence**

```javascript
// Both should be defined:
console.log('Tauri IPC:', typeof window.__TAURI__)
console.log('Canvas API:', typeof window.atom.canvas)
```

**Expected Output:**
```
Tauri IPC: object
Canvas API: object
```

**If __TAURI__ is undefined:**
- Dev server may be running without Tauri wrapper
- Ensure you're using `npm run tauri:dev`, not `npm run dev`

**If both are undefined:**
- No canvas components mounted on current page
- Navigate to a page with AgentOperationTracker or other canvas components

---

**Test 4: Verify accessibility tree in DOM**

1. In DevTools, switch to **Elements** tab
2. Press `Cmd+F` (macOS) or `Ctrl+F` (Windows/Linux) to open search
3. Search for: `[role="log"]`

**Expected Result:**
- One or more `<div>` elements found
- Element has `role="log"` attribute
- Element has `data-canvas-state` attribute
- Element has `style="display: none"` (hidden from visual display)

**Example DOM structure:**
```html
<div
  role="log"
  data-canvas-state="agent-operation"
  data-canvas-id="operation-tracker-123"
  style="display: none;">
  {"operation_id":"op-123","status":"running","progress":50,...}
</div>
```

**If no elements found:**
- Canvas component may not be mounted
- Try navigating to a page with AgentOperationTracker
- Check Console tab for React errors

**Test 5: Retrieve canvas state via API**

```javascript
// Get all canvas states
const states = window.atom.canvas.getAllStates()
console.log('Canvas states:', states)

// Get specific canvas state (if you know the ID)
const state = window.atom.canvas.getState('operation-tracker-123')
console.log('Specific state:', state)
```

**Expected Output:**
- Array of objects with `canvas_id` and `state` properties
- State object should contain operation data (id, status, progress, etc.)

---

## Production Build Verification

This section tests canvas AI context in production build, which uses minified code and different build configuration.

### Step 1: Build Production Application

```bash
cd frontend-nextjs
npm run tauri:build
```

**Expected Behavior:**
- Build process takes 2-5 minutes
- Next.js builds optimized production bundle
- Tauri bundles app into platform-specific executable
- Final build location shown in terminal output

**Build Output Locations:**
- **macOS:** `frontend-nextjs/src-tauri/target/release/bundle/dmg/` (.dmg file) and `/bundle/macos/` (.app file)
- **Windows:** `frontend-nextjs/src-tauri/target/release/bundle/msi/` (.msi installer) and `/bundle/nsis/` (.exe setup)
- **Linux:** `frontend-nextjs/src-tauri/target/release/bundle/deb/` (.deb package) and `/bundle/appimage/` (.AppImage)

### Step 2: Launch Production Build

**macOS:**
```bash
open frontend-nextjs/src-tauri/target/release/bundle/macos/ATOM.app
# Or double-click .app file in Finder
```

**Windows:**
```bash
# Run the installer or executable
frontend-nextjs\src-tauri\target\release\bundle\msi\ATOM_0.1.0_x64_en-US.msi
```

**Linux:**
```bash
# Install .deb package
sudo dpkg -i frontend-nextjs/src-tauri/target/release/bundle/deb/atom_0.1.0_amd64.deb
# Or run AppImage directly
./frontend-nextjs/src-tauri/target/release/bundle/appimage/atom_0.1.0_amd64.AppImage
```

### Step 3: Open DevTools in Production

**Option A: Keyboard Shortcut**
- **macOS:** `Cmd+Option+I`
- **Windows/Linux:** `Ctrl+Shift+I`

**Option B: If Shortcut Doesn't Work**
Production builds may disable DevTools by default. Enable via Tauri configuration:

1. Edit `frontend-nextjs/src-tauri/tauri.conf.json`
2. Add to `app.windows[0]`:
```json
{
  "title": "ATOM",
  "debug": true  // Enables DevTools in production
}
```

3. Rebuild: `npm run tauri:build`

### Step 4: Production-Specific Tests

**Repeat Tests 1-5 from Development Build section above.**

**Critical Additional Check:**

**Test 6: Verify accessibility trees survived minification**

In DevTools Elements tab, search for `[role="log"]`.

**Expected Result:**
- Accessibility divs still present (not removed by Terser minification)
- `data-canvas-state` attributes present
- JSON content preserved inside hidden div

**If accessibility divs are missing:**

This means Terser removed the "dead code" (hidden divs). Fix by adding `data-testid` attributes (always preserved):

```tsx
// In canvas components (AgentOperationTracker, ViewOrchestrator, etc.)
<div
  role="log"
  data-testid="canvas-state-log"  // Add this
  data-canvas-state={canvasType}
  data-canvas-id={canvasId}
  style={{ display: 'none' }}>
  {JSON.stringify(state)}
</div>
```

Alternatively, configure Terser in `next.config.js`:

```javascript
module.exports = {
  compiler: {
    removeConsole: false,  // Preserve console for debugging
    terserOptions: {
      compress: {
        drop_console: false,  // Don't remove console logs
        dead_code: false,     // Don't remove "dead" code (accessibility divs)
        pure_funcs: [],       // Don't remove function calls
      },
    },
  },
};
```

After adding fixes, rebuild and retest: `npm run tauri:build`

---

## Real-Time Canvas Updates Test

This section verifies that canvas state changes are properly propagated to subscribers, simulating how AI agents would monitor canvas updates.

### Step 1: Navigate to Page with Live Canvas Updates

Open a page with real-time canvas updates, such as:
- Agent operation tracker (running agent operation)
- Live data dashboard
- Any page with canvas state that changes over time

### Step 2: Subscribe to Canvas Changes

In DevTools Console, run:

```javascript
// Subscribe to all canvas state changes
const unsubscribe = window.atom.canvas.subscribeAll((event) => {
  console.log('Canvas state changed:', event);
  console.log('  Canvas ID:', event.canvas_id);
  console.log('  New State:', event.state);
});

console.log('Subscribed to canvas updates. Trigger a canvas state change...');
```

### Step 3: Trigger Canvas State Change

Depending on the page:
- Start an agent operation
- Update data in a dashboard
- Interact with canvas component (click button, change filter, etc.)

### Step 4: Verify Callback Fires

**Expected Output in Console:**
```
Canvas state changed: {canvas_id: "operation-tracker-123", state: {...}}
  Canvas ID: operation-tracker-123
  New State: {operation_id: "op-123", status: "running", progress: 55, ...}
```

**If callback doesn't fire:**
- Verify `useCanvasState` hook is correctly implemented in component
- Check for console errors during state updates
- Ensure component is re-rendering on state change

### Step 5: Cleanup Subscription

```javascript
// Stop receiving updates
unsubscribe();
console.log('Unsubscribed from canvas updates');
```

Trigger another state change — callback should NOT fire.

---

## Troubleshooting

### Issue: `window.atom.canvas is undefined`

**Cause:**
- Canvas component not mounted yet
- `useCanvasState` hook not called on current page
- Page hasn't fully loaded

**Fix:**
1. Navigate to a page with canvas components (AgentOperationTracker, ViewOrchestrator)
2. Wait for React component to mount (check React DevTools if needed)
3. Re-run `typeof window.atom?.canvas` check
4. Verify component uses `useCanvasState` hook

**Verification:**
```javascript
// Check if any canvas components are mounted
document.querySelectorAll('[data-canvas-state]').length
// Should be > 0
```

---

### Issue: Accessibility divs missing in production build

**Cause:**
- Terser minification removed hidden divs as "dead code"
- CSS-in-JS not applied during static build
- Next.js optimization removed unused DOM elements

**Fix:**
1. Add `data-testid` attributes (always preserved):
```tsx
<div
  role="log"
  data-testid="canvas-accessibility-tree"  // Add this
  data-canvas-state={canvasType}
  style={{ display: 'none' }}>
  {JSON.stringify(state)}
</div>
```

2. Configure Terser to preserve accessibility divs (see Production Build Verification section)

3. Rebuild and test: `npm run tauri:build`

---

### Issue: `window.__TAURI__ undefined` in dev build

**Cause:**
- Using `npm run dev` instead of `npm run tauri:dev`
- Tauri IPC bridge not initialized in standard web dev server

**Fix:**
- Always use `npm run tauri:dev` for Tauri desktop testing
- Standard `npm run dev` only tests web browser environment

**Verification:**
```javascript
// Should return "object" in Tauri build
typeof window.__TAURI__
```

---

### Issue: Canvas state not updating in real-time

**Cause:**
- Subscription not properly set up
- Component not re-rendering on state change
- WebSocket connection not established (if using remote updates)

**Fix:**
1. Verify component uses `useCanvasState` hook:
```tsx
import { useCanvasState } from '@/hooks/useCanvasState';

function MyComponent() {
  const { state, getState } = useCanvasState('my-canvas');
  // ...
}
```

2. Check for React state update errors in Console
3. Test subscription manually (see Real-Time Canvas Updates Test)

---

### Issue: TypeScript errors when accessing window.atom.canvas

**Cause:**
- Missing type declaration for `window.atom` global

**Fix:**
Create or edit `frontend-nextjs/src/types/global.d.ts`:
```typescript
import { CanvasStateAPI } from '@/components/canvas/types';

declare global {
  interface Window {
    atom?: {
      canvas?: CanvasStateAPI;
    };
    __TAURI__?: {
      invoke: (cmd: string, args?: any) => Promise<any>;
    };
  }
}

export {};
```

---

## Success Criteria Checklist

Complete all checks below to verify canvas AI context works in Tauri:

### Development Build
- [ ] `window.atom.canvas` is accessible (returns `"object"`)
- [ ] All API methods exist: `getState`, `getAllStates`, `subscribe`, `subscribeAll`
- [ ] `window.__TAURI__` coexists without conflicts
- [ ] Accessibility trees present in DOM (`[role="log"]` elements)
- [ ] Canvas state retrievable via API calls
- [ ] Real-time updates work via subscriptions

### Production Build
- [ ] `window.atom.canvas` accessible in production build
- [ ] Accessibility trees survived minification (not removed as dead code)
- [ ] All API methods functional in production
- [ ] Real-time updates work in production

### Cross-Platform Verification
- [ ] Tests pass on macOS (WebKit webview)
- [ ] Tests pass on Windows (WebView2) - if applicable
- [ ] Tests pass on Linux (WebKitGTK) - if applicable

---

## Notes

**What This Guide Covers:**
- Canvas AI context accessibility in Tauri webview
- API registration and functionality
- Accessibility tree presence in DOM
- Real-time canvas state updates
- Development vs. production build differences

**What This Guide Does NOT Cover:**
- Backend API testing (out of scope for canvas context)
- Visual canvas rendering (charts, tables, etc.)
- Tauri IPC command implementation
- Canvas component functionality testing (see Phase 20 verification)

**Related Documentation:**
- Phase 20 Canvas AI Context: `.planning/phases/20-canvas-ai-context/20-VERIFICATION.md`
- Canvas AI Accessibility: `docs/CANVAS_AI_ACCESSIBILITY.md`
- Tauri Configuration: `frontend-nextjs/src-tauri/tauri.conf.json`
- Canvas State Types: `frontend-nextjs/components/canvas/types/index.ts`

**For Issues:**
- Check Tauri docs: https://v2.tauri.app/
- Check React Testing Library docs: https://testing-library.com/docs/react-testing-library/intro/
- Review Phase 28 Research: `.planning/phases/28-tauri-canvas-ai-accessibility/28-RESEARCH.md`

---

**Last Updated:** 2026-02-18
**Phase:** 28 - Tauri Canvas AI Accessibility Verification
**Plan:** 03 - Manual Testing Documentation & Integration Tests
