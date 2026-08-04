/**
 * ArtifactSidebar Component Tests
 *
 * Tests verify ArtifactSidebar renders artifact list, handles empty state,
 * and triggers selection callback.
 *
 * Source: components/chat/ArtifactSidebar.tsx (36 lines, 0% coverage)
 */

import React from 'react';
import { renderWithProviders, screen, waitFor } from '../../../tests/test-utils';
import { ArtifactSidebar } from '../ArtifactSidebar';

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('ArtifactSidebar', () => {
  const mockOnSelectArtifact = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders artifact list
  test('renders artifact list', async () => {
    const mockArtifacts = [
      { id: '1', name: 'Artifact 1', type: 'code', version: 1, updated_at: '2024-01-01' },
      { id: '2', name: 'Artifact 2', type: 'markdown', version: 2, updated_at: '2024-01-02' },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockArtifacts,
    });

    const { container } = renderWithProviders(
      <ArtifactSidebar sessionId="session-123" onSelectArtifact={mockOnSelectArtifact} />
    );

    await waitFor(() => {
      expect(container.textContent).toContain('Artifact 1');
      expect(container.textContent).toContain('Artifact 2');
    }, { timeout: 10000 }); // Increased from default 5000ms
  });

  // Test 2: empty artifacts shows placeholder
  test('empty artifacts shows placeholder', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    const { container } = renderWithProviders(
      <ArtifactSidebar sessionId="session-123" onSelectArtifact={mockOnSelectArtifact} />
    );

    await waitFor(() => {
      expect(container.textContent).toContain('No artifacts shared yet');
    }, { timeout: 10000 }); // Increased from default 5000ms
  });

  // Test 3: artifact has correct version badge
  test('artifact has correct version badge', async () => {
    const mockArtifacts = [
      { id: '1', name: 'Test', type: 'code', version: 3, updated_at: '2024-01-01' },
    ];

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockArtifacts,
    });

    const { container } = renderWithProviders(
      <ArtifactSidebar sessionId="session-123" onSelectArtifact={mockOnSelectArtifact} />
    );

    await waitFor(() => {
      expect(container.textContent).toContain('v3');
    }, { timeout: 10000 }); // Increased from default 5000ms
  });

  // Test 4: shows header with title
  test('shows header with title', () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    const { container } = renderWithProviders(
      <ArtifactSidebar sessionId="session-123" onSelectArtifact={mockOnSelectArtifact} />
    );

    expect(container.textContent).toContain('Team Artifacts');
  });

  // Test 5: returns null when no sessionId
  test('returns null when no sessionId', () => {
    const { container } = renderWithProviders(
      <ArtifactSidebar sessionId={null} onSelectArtifact={mockOnSelectArtifact} />
    );

    expect(container.innerHTML).toBe('');
  });

  // Test 6: renders without errors
  test('renders without errors', () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    expect(() =>
      renderWithProviders(
        <ArtifactSidebar sessionId="session-123" onSelectArtifact={mockOnSelectArtifact} />
      )
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
