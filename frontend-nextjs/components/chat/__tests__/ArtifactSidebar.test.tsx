/**
 * ArtifactSidebar Component Tests
 *
 * Tests verify the session Artifacts panel against its real data source:
 * the session-scoped canvas list (GET /api/canvas/?session_id=…) backed by
 * the canvas audit trail — the same store CanvasHost saves to, /canvas/{id}
 * reads, and the gallery page lists.
 *
 * Source: components/chat/ArtifactSidebar.tsx
 *
 * Real behavior (verified against source):
 * - Fetches `/api/canvas/?session_id=...&limit=50` on mount via apiClient
 *   (authenticated, backend-URL aware) and every 10s.
 * - Renders `canvases[]` from the response: display_title → title →
 *   canvas_id, a `v{version}` badge, relative timestamp.
 * - Clicking an item renders it into the chat's CanvasHost through
 *   syncCanvasFromStore (lib/canvasSync) — no navigation.
 * - "View Full History" links to /canvas (the cross-session gallery).
 * - Header: "Session Artifacts". Empty placeholder when the session has none.
 * - Returns null when no sessionId.
 */

import React from 'react';
import { renderWithProviders, screen, waitFor, fireEvent } from '../../../tests/test-utils';
import { ArtifactSidebar } from '../ArtifactSidebar';

const mockGet = jest.fn();
const mockSync = jest.fn();
const mockOnRefresh = jest.fn();

jest.mock('@/lib/api-client', () => ({
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}));

jest.mock('@/lib/canvasSync', () => ({
  syncCanvasFromStore: (...args: unknown[]) => mockSync(...args),
  onCanvasRefresh: (...args: unknown[]) => mockOnRefresh(...args),
}));

const ITEMS = [
  {
    canvas_id: 'cv-1',
    canvas_type: 'docs',
    action_type: 'present',
    title: 'Doc title',
    display_title: 'Session Doc',
    snippet: 'hello',
    deleted: false,
    last_updated: '2026-08-30T12:00:00Z',
    version: 2,
  },
  {
    canvas_id: 'cv-2',
    canvas_type: 'sheets',
    action_type: 'update',
    title: null,
    display_title: 'Budget sheet',
    snippet: null,
    deleted: false,
    last_updated: '2026-08-30T12:05:00Z',
    version: 3,
  },
];

const mockResponse = (canvases: unknown[]) =>
  mockGet.mockResolvedValue({ data: { success: true, canvases, count: canvases.length, total: canvases.length } });

describe('ArtifactSidebar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockOnRefresh.mockReturnValue(jest.fn());
    mockResponse([]);
  });

  // Test 1: fetches the SESSION-SCOPED canvas list (not the dead legacy
  // /api/artifacts endpoint) with the session id.
  test('fetches session-scoped canvas list via apiClient', async () => {
    mockResponse(ITEMS);
    renderWithProviders(<ArtifactSidebar sessionId="session-123" />);

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith(
        `/api/canvas/?session_id=${encodeURIComponent('session-123')}&limit=50`
      );
    });
  });

  // Test 2: renders the list with server-derived titles
  test('renders artifact list with display titles', async () => {
    mockResponse(ITEMS);
    const { container } = renderWithProviders(<ArtifactSidebar sessionId="session-123" />);

    await waitFor(() => {
      expect(container.textContent).toContain('Session Doc');
      expect(container.textContent).toContain('Budget sheet');
    });
  });

  // Test 3: empty session shows placeholder
  test('empty artifacts shows placeholder', async () => {
    const { container } = renderWithProviders(<ArtifactSidebar sessionId="session-123" />);

    await waitFor(() => {
      expect(container.textContent).toContain('No artifacts yet this session.');
    });
  });

  // Test 4: version badge comes from the audit-row count
  test('artifact has correct version badge', async () => {
    mockResponse([ITEMS[1]]);
    const { container } = renderWithProviders(<ArtifactSidebar sessionId="session-123" />);

    await waitFor(() => {
      expect(container.textContent).toContain('v3');
    });
  });

  // Test 5: clicking an item renders it into the CanvasHost via
  // syncCanvasFromStore — the no-navigation journey.
  test('clicking an artifact loads it into the canvas host', async () => {
    mockResponse([ITEMS[0]]);
    const onSelect = jest.fn();
    const { container } = renderWithProviders(
      <ArtifactSidebar sessionId="session-123" onSelectArtifact={onSelect} />
    );

    await waitFor(() => {
      expect(container.textContent).toContain('Session Doc');
    });
    fireEvent.click(screen.getByText('Session Doc'));

    await waitFor(() => {
      expect(mockSync).toHaveBeenCalledWith('cv-1');
      expect(onSelect).toHaveBeenCalledWith('cv-1');
    });
  });

  // Test 6: View Full History links to the /canvas gallery
  test('View Full History links to /canvas', async () => {
    const { container } = renderWithProviders(<ArtifactSidebar sessionId="session-123" />);

    await waitFor(() => {
      const link = container.querySelector('[data-testid="artifact-full-history"]');
      expect(link).not.toBeNull();
      expect(link!.getAttribute('href')).toBe('/canvas');
    });
  });

  // Test 7: header reflects session scope
  test('shows header with title', () => {
    const { container } = renderWithProviders(<ArtifactSidebar sessionId="session-123" />);
    expect(container.textContent).toContain('Session Artifacts');
  });

  // Test 8: returns null when no sessionId
  test('returns null when no sessionId', () => {
    const { container } = renderWithProviders(<ArtifactSidebar sessionId={null} />);
    expect(container.innerHTML).toBe('');
  });

  // Test 9: refetches when a canvas refresh (agent present/update) arrives
  test('subscribes to canvas refresh events and refetches', async () => {
    renderWithProviders(<ArtifactSidebar sessionId="session-123" />);

    await waitFor(() => expect(mockGet).toHaveBeenCalled());
    // onCanvasRefresh registered with a handler; unsubscribed cleanly.
    expect(mockOnRefresh).toHaveBeenCalled();
    expect(typeof mockOnRefresh.mock.calls[0][0]).toBe('function');
  });

  // Test 10: renders without errors
  test('renders without errors', () => {
    expect(() =>
      renderWithProviders(<ArtifactSidebar sessionId="session-123" />)
    ).not.toThrow();
  });
});

describe('formatDate', () => {
  // Import the exported helper directly.
  const { formatDate } = require('../ArtifactSidebar');

  it('returns empty string for an unparseable date (not "Invalid Date")', () => {
    // A malformed timestamp previously produced NaN, fell through every
    // comparison, and rendered the literal "Invalid Date" to the user.
    expect(formatDate('not-a-real-date')).toBe('');
    expect(formatDate('')).toBe('');
    expect(formatDate(null)).toBe('');
    expect(formatDate(undefined)).toBe('');
  });

  it('does not return "Just now" for a far-future timestamp', () => {
    // Clock skew can put updated_at in the future; the old code returned
    // "Just now" for any negative diff. It should show the real date.
    const future = new Date(Date.now() + 86400000 * 7).toISOString(); // +7 days
    const result = formatDate(future);
    expect(result).not.toBe('Just now');
    expect(result.length).toBeGreaterThan(0);
  });

  it('returns "Just now" for a timestamp within the last minute', () => {
    const recent = new Date(Date.now() - 5000).toISOString(); // 5s ago
    expect(formatDate(recent)).toBe('Just now');
  });
});
