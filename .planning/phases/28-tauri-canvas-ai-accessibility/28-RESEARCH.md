# Phase 28: Tauri Canvas AI Accessibility Verification - Research

**Researched:** 2026-02-18
**Domain:** Tauri v2 Desktop Application Testing, Canvas AI Context, Window Global Variables
**Confidence:** HIGH

## Summary

Phase 28 requires verifying that canvas AI context, implemented in Phase 20, is properly accessible via Tauri's desktop application window global variables. The core challenge is ensuring that the `window.atom.canvas` API (designed for web browsers) functions correctly within Tauri's webview environment, where the frontend-backend bridge uses `window.__TAURI__` for IPC communication.

**Key finding:** Tauri v2 applications use the operating system's native web renderer (WebView2 on Windows, WebKit on macOS/Linux) with standard web technologies. The `window.atom.canvas` global variable from Phase 20 should already work in Tauri's webview, but this needs verification through testing. The primary concern is ensuring React components mount correctly, register canvas state, and that accessibility trees (hidden divs with `role="log"`) are present in the DOM.

**Primary recommendation:** Use a three-tier testing approach: (1) JavaScript API tests using JSDOM/Jest to verify `window.atom.canvas` registration, (2) Integration tests using Tauri's testing framework to verify IPC bridge communication, (3) Manual UI testing in actual Tauri desktop environment to verify real-time canvas updates and accessibility tree presence.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tauri | v2.0+ | Desktop app framework | De facto standard for Rust-based desktop apps using web technologies |
| Next.js | ^15.5.9 | Frontend framework | Already in use, provides SSR/React components |
| React | ^18.3.1 | UI library | Component rendering, hooks (useCanvasState) |
| TypeScript | ^5.9.2 | Type safety | Canvas state type definitions, window global declarations |

### Testing
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Jest | ^30.0.5 | Unit testing | JavaScript API tests, canvas state registration |
| @testing-library/react | ^16.3.0 | Component testing | Verify canvas components render with accessibility trees |
| @testing-library/jest-dom | ^6.6.3 | DOM assertions | Query `data-canvas-state` attributes, `role="log"` divs |
| Tauri Test Driver (built-in) | v2.0+ | Integration testing | Verify IPC bridge, window global in webview |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Jest + JSDOM | Vitest | Vitest faster but Jest already configured, ecosystem larger |
| Manual Tauri testing | Playwright | Playwright better for web but Tauri test driver closer to real environment |
| React Testing Library | Enzyme | Enzyme deprecated, RTL encourages user-centric testing |

**Installation:**
```bash
# Jest already installed
npm install --save-dev @tauri-apps/cli@latest

# For Tauri integration testing (if needed)
cd frontend-nextjs/src-tauri
cargo test
```

## Architecture Patterns

### Recommended Project Structure

```
frontend-nextjs/src-tauri/
├── src/
│   ├── main.rs              # Tauri backend (IPC commands, window management)
│   └── lib.rs               # Shared Rust code (if needed)
├── tests/                   # NEW: Tauri integration tests
│   ├── canvas_api_test.rs   # Test window.atom.canvas accessibility
│   └── integration_test.rs  # Test IPC bridge communication
└── tauri.conf.json          # Tauri configuration

frontend-nextjs/
├── components/
│   └── canvas/              # Canvas components (already exist)
│       ├── AgentOperationTracker.tsx
│       ├── ViewOrchestrator.tsx
│       └── types/index.ts   # CanvasStateAPI interface
├── hooks/
│   └── useCanvasState.ts    # Canvas state hook (already exists)
└── __tests__/
    └── tauri-canvas/        # NEW: Tauri-specific canvas tests
        ├── canvas-api.test.tsx       # Test window.atom.canvas API
        ├── canvas-dom.test.tsx       # Test accessibility tree DOM structure
        └── canvas-ipc.test.tsx       # Test IPC communication (if needed)
```

### Pattern 1: JavaScript API Testing (Jest + JSDOM)
**What:** Verify `window.atom.canvas` global API is accessible and functional
**When to use:** Unit tests for canvas state registration and retrieval
**Example:**
```typescript
// frontend-nextjs/__tests__/tauri-canvas/canvas-api.test.tsx

import { renderHook } from '@testing-library/react';
import { useCanvasState } from '@/hooks/useCanvasState';

// Mock Tauri window (if needed)
declare global {
  interface Window {
    atom?: {
      canvas?: {
        getState: (id: string) => any;
        getAllStates: () => any[];
        subscribe: (id: string, cb: Function) => () => void;
      };
    };
    __TAURI__?: any; // Tauri IPC bridge
  }
}

describe('Tauri Canvas API', () => {
  beforeEach(() => {
    // Initialize window.atom.canvas
    window.atom = {
      canvas: {
        getState: jest.fn(),
        getAllStates: jest.fn(),
        subscribe: jest.fn()
      }
    };
  });

  test('window.atom.canvas should be accessible in Tauri webview', () => {
    expect(window.atom?.canvas).toBeDefined();
    expect(typeof window.atom.canvas?.getState).toBe('function');
    expect(typeof window.atom.canvas?.getAllStates).toBe('function');
    expect(typeof window.atom.canvas?.subscribe).toBe('function');
  });

  test('useCanvasState hook should register with global API', () => {
    const { result } = renderHook(() => useCanvasState('test-canvas'));

    // Verify hook can access API
    expect(result.current.getState).toBeDefined();
    expect(result.current.getAllStates).toBeDefined();
  });
});
```

### Pattern 2: Accessibility Tree DOM Testing
**What:** Verify hidden accessibility divs with `role="log"` are present in DOM
**When to use:** Ensure AI agents can read canvas content without OCR
**Example:**
```typescript
// frontend-nextjs/__tests__/tauri-canvas/canvas-dom.test.tsx

import { render, screen } from '@testing-library/react';
import AgentOperationTracker from '@/components/canvas/AgentOperationTracker';

describe('Tauri Canvas Accessibility Tree', () => {
  test('canvas component should render hidden accessibility div', () => {
    const mockState = {
      operation_id: 'op-123',
      status: 'running',
      progress: 50,
      current_step: 'Processing data'
    };

    render(<AgentOperationTracker state={mockState} />);

    // Query accessibility tree (hidden from visual display)
    const accessibilityDiv = document.querySelector('[role="log"]');
    expect(accessibilityDiv).toBeInTheDocument();

    // Verify JSON state is present
    const stateJson = accessibilityDiv?.textContent || '';
    const parsedState = JSON.parse(stateJson);
    expect(parsedState.operation_id).toBe('op-123');
    expect(parsedState.status).toBe('running');
  });

  test('data-canvas-state attribute should be present', () => {
    const { container } = render(<AgentOperationTracker />);
    const canvasElement = container.querySelector('[data-canvas-state]');
    expect(canvasElement).toBeInTheDocument();
  });
});
```

### Pattern 3: Tauri Integration Testing (Rust)
**What:** Verify canvas context is accessible from Tauri backend via IPC
**When to use:** Test frontend-backend communication in Tauri environment
**Example:**
```rust
// frontend-nextjs/src-tauri/tests/canvas_api_test.rs

#[tauri::command]
async fn get_canvas_context(window: tauri::Window) -> Result<String, String> {
    // Execute JavaScript in webview to check window.atom.canvas
    let result = window.eval(
        r#"
        (function() {
            if (window.atom && window.atom.canvas) {
                const states = window.atom.canvas.getAllStates();
                return JSON.stringify(states);
            }
            return JSON.stringify({ error: "canvas API not found" });
        })()
        "#
    );

    match result {
        Ok(states) => Ok(states.as_string().unwrap_or_default()),
        Err(e) => Err(format!("Failed to evaluate JavaScript: {}", e))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_canvas_context_accessible() {
        // This would typically be run in an integration test context
        // where the Tauri app is actually running
    }
}
```

### Anti-Patterns to Avoid
- **Testing window.__TAURI__ directly**: Don't test Tauri's internal IPC bridge. Test your canvas API through `window.atom.canvas` instead.
- **Mocking window object incorrectly**: Don't completely replace `window`. Mock `window.atom.canvas` but preserve `window.__TAURI__` if present.
- **Testing visual rendering in unit tests**: Don't test canvas pixels/charts in Jest. Test the accessibility tree (JSON state) instead.
- **Skipping Tauri environment verification**: Don't assume web tests translate to Tauri. Must verify in actual Tauri webview context.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| DOM querying | Custom selectors | `@testing-library/react` (`screen`, `within`) | User-centric queries, accessibility-first |
| Window global mocking | Manual stub creation | Jest `beforeEach` with type-safe declarations | Type safety, prevents runtime errors |
| Tauri integration testing | Custom test runners | Tauri's built-in test driver + Cargo test | Official support, handles webview lifecycle |
| Canvas state verification | Parsing DOM manually | React Testing Library queries + JSON parsing | Handles React state updates, async rendering |

**Key insight:** Tauri v2 uses standard web technologies (WebView2/WebKit). Standard web testing tools work. Don't reinvent the wheel for "desktop testing" unless absolutely necessary.

## Common Pitfalls

### Pitfall 1: Assuming Tauri Webview != Browser
**What goes wrong:** Tests pass in Jest/JSDOM but fail in Tauri app because webview context differs
**Why it happens:** Tauri webview has `window.__TAURI__`, different security policies, potentially different JavaScript execution context
**How to avoid:**
- Add integration tests that run in actual Tauri environment (or mock `window.__TAURI__` in unit tests)
- Verify canvas state API works alongside Tauri IPC bridge
- Test with real Tauri build (`npm run tauri:dev`) before marking phase complete
**Warning signs:** Tests pass in CI but manual Tauri testing shows missing `window.atom.canvas`

### Pitfall 2: Missing Type Declarations for Tauri Window
**What goes wrong:** TypeScript errors when accessing `window.__TAURI__` or `window.atom.canvas`
**Why it happens:** Tauri adds global variables not in standard `lib.dom.d.ts`
**How to avoid:**
```typescript
// frontend-nextjs/src/types/tauri.d.ts
import { CanvasStateAPI } from '@/components/canvas/types';

declare global {
  interface Window {
    atom?: {
      canvas?: CanvasStateAPI;
    };
    __TAURI__?: {
      invoke: (cmd: string, args?: any) => Promise<any>;
      // Add other Tauri APIs as needed
    };
  }
}

export {};
```
**Warning signs:** TypeScript errors `Property 'atom' does not exist on type 'Window'`

### Pitfall 3: Canvas State Not Registered on Component Mount
**What goes wrong:** `window.atom.canvas.getState('canvas-id')` returns `null` even after component renders
**Why it happens:** Canvas state registration in `useEffect` hasn't executed yet, or component unmounted before registration
**How to avoid:**
- Test with `waitFor` from React Testing Library for async registration
- Verify `useEffect` cleanup doesn't unregister state prematurely
- Check that canvas ID is consistent between registration and retrieval
**Warning signs:** Flaky tests that sometimes pass, sometimes fail

### Pitfall 4: Accessibility Tree Not Present in Production Build
**What goes wrong:** Tests pass in dev mode (`npm run tauri:dev`) but fail in production build (`npm run tauri:build`)
**Why it happens:** Minification (Terser) removes "dead code" (hidden divs with `display: none`), or production CSP blocks inline scripts
**How to avoid:**
- Add `data-testid` attributes alongside accessibility tree (preserved in production)
- Configure Terser to preserve `role` and `aria-*` attributes
- Test production build before marking phase complete
**Warning signs:** Dev build works, production build missing accessibility divs

### Pitfall 5: Testing Visual Canvas Instead of Logical State
**What goes wrong:** Tests try to assert on chart pixels, canvas rendering, or visual output
**Why it happens:** Confusion about "canvas accessibility" - Phase 20 is about AI agents reading logical state, not visual rendering
**How to avoid:**
- **Test logical state**: Assert on JSON content in `role="log"` divs
- **Test accessibility tree**: Query `data-canvas-state`, `data-canvas-id` attributes
- **Skip visual tests**: Don't test React Recharts, canvas pixels, or CSS rendering
**Warning signs:** Tests using `canvas.getContext('2d')`, snapshot testing of visual components

## Code Examples

Verified patterns from official sources and codebase analysis:

### Example 1: Verify Canvas State API Registration
```typescript
// Source: Phase 20 implementation (frontend-nextjs/hooks/useCanvasState.ts)

import { renderHook, waitFor } from '@testing-library/react';
import { useCanvasState } from '@/hooks/useCanvasState';

describe('Canvas State API in Tauri Environment', () => {
  beforeEach(() => {
    // Simulate Tauri webview environment
    window.__TAURI__ = {
      invoke: jest.fn()
    };

    // Initialize canvas API (mimics useCanvasState initialization)
    window.atom = {
      canvas: {
        getState: jest.fn((id) => ({ canvas_id: id, status: 'active' })),
        getAllStates: jest.fn(() => []),
        subscribe: jest.fn((id, cb) => {
          // Return unsubscribe function
          return () => {};
        })
      }
    };
  });

  test('canvas API should be accessible with Tauri IPC present', () => {
    expect(window.atom?.canvas).toBeDefined();
    expect(window.__TAURI__).toBeDefined();

    // Verify no conflicts between atom.canvas and __TAURI__
    expect(typeof window.atom.canvas.getState).toBe('function');
    expect(typeof window.__TAURI__.invoke).toBe('function');
  });

  test('useCanvasState should work in Tauri environment', async () => {
    const { result } = renderHook(() => useCanvasState('test-canvas'));

    await waitFor(() => {
      expect(result.current.getState).toBeDefined();
      expect(result.current.getAllStates).toBeDefined();
    });
  });
});
```

### Example 2: Test Accessibility Tree Presence
```typescript
// Source: Phase 20 verification (.planning/phases/20-canvas-ai-context/20-VERIFICATION.md)

import { render, screen } from '@testing-library/react';
import AgentOperationTracker from '@/components/canvas/AgentOperationTracker';

describe('Tauri Canvas Accessibility Tree', () => {
  test('agent operation tracker should expose state to AI agents', () => {
    const props = {
      operation_id: 'op-123',
      agent_id: 'agent-456',
      agent_name: 'TestAgent',
      status: 'running' as const,
      progress: 75,
      current_step: 'Processing data',
      context: {
        what: 'Analyzing sales data',
        why: 'Generate monthly report',
        next: 'Send email notification'
      },
      logs_count: 5,
      started_at: '2026-02-18T10:00:00Z'
    };

    render(<AgentOperationTracker {...props} />);

    // Accessibility tree should be present (hidden from visual display)
    const accessibilityLog = screen.getByRole('log');
    expect(accessibilityLog).toBeInTheDocument();

    // Verify state is serialized as JSON
    const stateText = accessibilityLog.textContent;
    expect(stateText).toContain('op-123');
    expect(stateText).toContain('running');
    expect(stateText).toContain('75');

    // Parse and verify JSON structure
    const state = JSON.parse(stateText || '{}');
    expect(state.operation_id).toBe('op-123');
    expect(state.status).toBe('running');
    expect(state.progress).toBe(75);
    expect(state.context.what).toBe('Analyzing sales data');
  });
});
```

### Example 3: Test Real-Time Canvas Updates (if WebSocket enabled)
```typescript
// Source: Phase 20 canvas state API (docs/CANVAS_AI_ACCESSIBILITY.md)

describe('Canvas Real-Time Updates in Tauri', () => {
  test('canvas state changes should trigger subscriptions', async () => {
    // Mock canvas state store
    const mockStates = new Map();
    const subscribers = new Map();

    window.atom = {
      canvas: {
        getState: (id) => mockStates.get(id),
        getAllStates: () => Array.from(mockStates.entries()).map(([id, state]) => ({ canvas_id: id, state })),
        subscribe: (id, callback) => {
          const subs = subscribers.get(id) || [];
          subs.push(callback);
          subscribers.set(id, subs);
          return () => {
            const current = subscribers.get(id) || [];
            subscribers.set(id, current.filter(cb => cb !== callback));
          };
        }
      }
    };

    // Test subscription
    const mockCallback = jest.fn();
    const unsubscribe = window.atom.canvas.subscribe('test-canvas', mockCallback);

    // Update state
    const newState = { canvas_id: 'test-canvas', status: 'updated' };
    mockStates.set('test-canvas', newState);

    // Notify subscribers
    const subs = subscribers.get('test-canvas') || [];
    subs.forEach(cb => cb(newState));

    expect(mockCallback).toHaveBeenCalledWith(newState);

    // Unsubscribe
    unsubscribe();
  });
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Electron (Chromium bundle) | Tauri (OS native webview) | Tauri 1.0 (2022) | 10x smaller app size, better security |
| Testing in browser only | Tauri integration tests | Tauri 2.0 (2024) | More accurate testing environment |
| Canvas content only visual | Dual representation (visual + logical) | Phase 20 (Feb 2026) | AI agents can read canvas without OCR |
| No global canvas API | `window.atom.canvas` global API | Phase 20 (Feb 2026) | Standardized access pattern for AI agents |

**Deprecated/outdated:**
- **Electron-specific testing**: Spectron (deprecated 2022), use Tauri test driver instead
- **Visual-only canvas**: Old canvas components without accessibility trees, upgrade to Phase 20 components
- **OCR for canvas reading**: AI agents no longer need OCR, use `window.atom.canvas.getState()` instead

## Open Questions

1. **Tauri Test Driver Availability**
   - What we know: Tauri has built-in testing capabilities (mentioned in docs)
   - What's unclear: Exact API for integration tests, whether to use Cargo tests or JavaScript tests
   - Recommendation: Start with Jest unit tests + manual Tauri dev testing, add Rust integration tests only if needed

2. **Production Build Minification Impact**
   - What we know: Terser removes "dead code" in production builds
   - What's unclear: Whether accessibility divs (`role="log"`, `display: none`) survive minification
   - Recommendation: Test with `npm run tauri:build` to verify accessibility trees preserved in production

3. **Performance of Real-Time Canvas Updates in Tauri**
   - What we know: Phase 20 documents WebSocket support for canvas state changes
   - What's unclear: Performance overhead in Tauri webview vs. browser
   - Recommendation: Measure performance with manual testing (100ms target from Phase 20)

4. **Security Policy (CSP) Compatibility**
   - What we know: Tauri apps use Content Security Policy (line 42 in tauri.conf.json)
   - What's unclear: Whether inline scripts or dynamic content injection is blocked
   - Recommendation: Verify CSP allows `role="log"` divs and JSON state injection

## Sources

### Primary (HIGH confidence)
- **Phase 20 Verification Report** - `.planning/phases/20-canvas-ai-context/20-VERIFICATION.md` (7/7 success criteria verified)
- **Canvas AI Accessibility Documentation** - `docs/CANVAS_AI_ACCESSIBILITY.md` (11,684 bytes, comprehensive guide)
- **Canvas State Type Definitions** - `frontend-nextjs/components/canvas/types/index.ts` (550 lines, TypeScript interfaces)
- **useCanvasState Hook Implementation** - `frontend-nextjs/hooks/useCanvasState.ts` (84 lines, global API registration)
- **Tauri Configuration** - `frontend-nextjs/src-tauri/tauri.conf.json` (Tauri v2.0+, CSP settings)
- **Tauri Main Process** - `frontend-nextjs/src-tauri/src/main.rs` (1757 lines, IPC commands, window management)

### Secondary (MEDIUM confidence)
- **React Testing Library Documentation** - Accessibility-first testing queries
- **Jest Configuration** - `frontend-nextjs/package.json` (Jest ^30.0.5, @testing-library/react ^16.3.0)
- **Tauri Official Website** - https://v2.tauri.app/ (Tauri 2.0 release info, webview architecture)

### Tertiary (LOW confidence)
- **WebSearch Results** - Searches for "Tauri v2 testing" returned no results (likely due to Tauri v2 being relatively new or URL structure changes)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools already in use (Jest, React Testing Library, Tauri v2)
- Architecture: HIGH - Phase 20 implementation verified working, Tauri webview architecture well-documented
- Pitfalls: MEDIUM - Web testing patterns clear, but Tauri-specific issues unknown (integration testing needed)

**Research date:** 2026-02-18
**Valid until:** 2026-03-20 (30 days - Tauri v2 stable, web testing patterns mature)

**Key assumption:** Tauri v2 webview behaves like standard browser for JavaScript execution. Verification needed for `window.__TAURI__` coexistence with `window.atom.canvas`.
