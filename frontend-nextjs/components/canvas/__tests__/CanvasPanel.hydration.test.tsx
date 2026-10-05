/**
 * The canvas must render its content on LOAD and after a RELOAD, even when the
 * parent also hands it a live socket listener.
 *
 * THE DEFECT (2026-09-28)
 * `CanvasPanel` applied its `lastMessage` prop only when the parent passed no
 * socket listener:
 *
 *     useEffect(() => {
 *         if (!lastMessage) return;
 *         applyCanvasMessage(lastMessage);
 *     }, [lastMessage, ...]);
 *
 * `/canvas/[id]` passes BOTH: `lastMessage={canvasLastMessage}` (a synthetic
 * `canvas:update`/`present` frame the page builds from the canvas it fetched
 * via `GET /api/canvas/{id}`) AND `onSocketMessage={onMessage}`. So on a
 * dedicated socket path the prop effect was skipped entirely and the panel
 * stayed null (`if (!state || !state.visible) return null`) until the agent
 * happened to broadcast a canvas frame. A user who opened a canvas by URL, or
 * reloaded one, saw an empty canvas area — the page header showed the title
 * and type while the canvas body rendered nothing at all.
 *
 * WHAT THE FIX MUST PRESERVE
 * The socket listener exists for a real reason: `lastMessage` is ONE state slot,
 * so a burst of frames inside a single render commit collapses to one commit
 * and an effect keyed on the prop sees only the newest frame. That is why the
 * listener was added. Dropping the prop path to make room for it traded a
 * burst-loss bug for a blank-canvas bug. Both paths are needed:
 *
 *   * the PROP carries the parent's authoritative current state — on the detail
 *     page that is the canvas fetched on mount, and it changes when the user
 *     reloads or the page refreshes;
 *   * the LISTENER carries every live frame in arrival order.
 *
 * The two are not alternatives, so the guard is removed rather than inverted.
 * Re-applying a payload the panel already has is a no-op anyway: both call
 * sites run through the same `applyCanvasMessage`, whose `payloadKey` /
 * `lastSavedSigRef` guards make identical payloads idempotent.
 */
import React from 'react';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

jest.mock('@monaco-editor/react', () => ({
  __esModule: true,
  default: ({ value, onChange }: any) => (
    <textarea
      data-testid="canvas-editor"
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
    />
  ),
}));

import { CanvasPanel } from '../CanvasPanel';

/** A `canvas:update`/present frame shaped like the one /canvas/[id] builds. */
const presentFrame = (body: string) => ({
  type: 'canvas:update',
  data: {
    action: 'present',
    component: 'email',
    canvas_id: 'cv-load-1',
    title: 'Quote for Steve',
    version: 3,
    data: { to: 'steve@example.com', cc: '', subject: 'Quote', body },
  },
});

const BODY_OLD = 'All quotes are valid for 15 days only.';

/** The email body surface is a contentEditable `.rte-surface`, not a textarea. */
const bodyText = () =>
  (document.querySelector('.rte-surface') as HTMLElement | null)?.textContent ?? null;

/** Collects the handler the panel registers, the way a live socket would. */
function socketHarness() {
  const handlers: Array<(msg: any) => void> = [];
  const onSocketMessage = (handler: (msg: any) => void) => {
    handlers.push(handler);
    return () => {
      const i = handlers.indexOf(handler);
      if (i >= 0) handlers.splice(i, 1);
    };
  };
  return {
    onSocketMessage,
    emit: (msg: any) => act(() => handlers.forEach((h) => h(msg))),
    handlerCount: () => handlers.length,
  };
}

beforeEach(() => {
  server.resetHandlers();
  server.use(
    rest.get('*/api/canvas/email/signature', async (_req, res, ctx) =>
      res(ctx.status(200), ctx.json({ success: true, signature: null, source: null }))),
  );
  delete (window as any).atom;
});

describe('CanvasPanel hydration when the parent also passes a socket listener', () => {
  it('renders the canvas on MOUNT, before any socket frame has arrived', () => {
    // Exactly what /canvas/[id] does: both props, and the socket is silent
    // until the agent broadcasts something.
    const sock = socketHarness();
    render(
      <CanvasPanel
        lastMessage={presentFrame(BODY_OLD)}
        onSocketMessage={sock.onSocketMessage}
      />
    );

    expect(sock.handlerCount()).toBe(1);
    // The panel registered its live listener...
    // ...and still rendered the canvas it was handed. Before the fix this
    // returned null and the whole canvas area was blank.
    expect(screen.getByTestId('canvas-container')).toBeInTheDocument();
    expect(screen.getByText('Quote for Steve')).toBeInTheDocument();
    expect(bodyText()).toContain(BODY_OLD);
  });

  it('renders the canvas after a RELOAD (a fresh mount with the same props)', () => {
    const first = socketHarness();
    const { unmount } = render(
      <CanvasPanel
        lastMessage={presentFrame(BODY_OLD)}
        onSocketMessage={first.onSocketMessage}
      />
    );
    expect(bodyText()).toContain(BODY_OLD);
    unmount();

    // Reload: the browser throws the tree away and rebuilds it from the same
    // server fetch. Nothing about the second mount differs from the first.
    const second = socketHarness();
    render(
      <CanvasPanel
        lastMessage={presentFrame(BODY_OLD)}
        onSocketMessage={second.onSocketMessage}
      />
    );
    expect(screen.getByTestId('canvas-container')).toBeInTheDocument();
    expect(bodyText()).toContain(BODY_OLD);
  });

  it('still renders with NO socket listener at all (the prop-only callers)', () => {
    render(<CanvasPanel lastMessage={presentFrame(BODY_OLD)} />);
    expect(screen.getByTestId('canvas-container')).toBeInTheDocument();
    expect(bodyText()).toContain(BODY_OLD);
  });

  it('applies a LIVE socket frame, not just the prop', () => {
    // The other half of the contract: the listener is not a fallback that the
    // prop path replaces. Without this, a fix for the blank canvas would
    // silently reintroduce the burst-loss bug the listener was added for.
    const sock = socketHarness();
    render(
      <CanvasPanel
        lastMessage={presentFrame(BODY_OLD)}
        onSocketMessage={sock.onSocketMessage}
      />
    );
    expect(bodyText()).toContain(BODY_OLD);

    sock.emit(
      presentFrame('All quotes are valid for 30 days only.')
    );
    expect(bodyText()).toContain('All quotes are valid for 30 days only.');
  });

  it('applies EVERY frame of a socket burst, not only the last one', () => {
    // `lastMessage` is one state slot: N frames inside one render commit
    // collapse to one, so a prop-keyed effect can only ever see the newest.
    // The listener is what makes the sequence lossless, and the intermediate
    // frame below is one a user would watch land and then be overwritten by
    // the next.
    const sock = socketHarness();
    render(
      <CanvasPanel
        lastMessage={presentFrame(BODY_OLD)}
        onSocketMessage={sock.onSocketMessage}
      />
    );

    const seen: Array<string | null> = [];
    for (const v of [1, 2, 3]) {
      sock.emit(presentFrame(`All quotes are valid for ${v}0 days only.`));
      seen.push(bodyText());
    }
    // Each frame was applied as it arrived: no frame is silently skipped.
    expect(seen).toEqual([
      'All quotes are valid for 10 days only.',
      'All quotes are valid for 20 days only.',
      'All quotes are valid for 30 days only.',
    ]);
  });

  it('unsubscribes its socket handler on unmount (no leak across reloads)', () => {
    const sock = socketHarness();
    const { unmount } = render(
      <CanvasPanel
        lastMessage={presentFrame(BODY_OLD)}
        onSocketMessage={sock.onSocketMessage}
      />
    );
    expect(sock.handlerCount()).toBe(1);
    unmount();
    expect(sock.handlerCount()).toBe(0);
  });
});
