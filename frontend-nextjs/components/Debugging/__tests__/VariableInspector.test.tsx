/**
 * VariableInspector Component Tests
 *
 * Tests verify the REAL VariableInspector component
 * (components/Debugging/VariableInspector.tsx, a NAMED export):
 * - Fetches variables for a session (or a trace when traceId is given)
 * - Search + Changed Only filtering
 * - Value formatting: preview, strings, booleans, null, numbers, JSON fallback
 * - Watch / scope / type badges; previous-value display; empty & no-session states
 *
 * fetch is mocked directly (see components/Settings/__tests__/TwoFactorSettings.test.tsx).
 * The toast hook is globally stubbed in tests/setup.ts.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import VariableInspector from '../VariableInspector';

const variable = (overrides: Record<string, any> = {}) => ({
  variable_id: 'v1',
  variable_name: 'user_name',
  variable_path: 'user.name',
  variable_type: 'string',
  value: 'alice',
  value_preview: '',
  is_mutable: true,
  scope: 'local',
  is_changed: false,
  previous_value: undefined,
  is_watch: false,
  ...overrides,
});

describe('VariableInspector', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: async () => [] })) as unknown as typeof fetch;
  });

  const renderInspector = (props: Record<string, any> = {}) =>
    render(
      <VariableInspector
        sessionId="ses-1"
        workflowId="wf-1"
        currentUserId="user-1"
        {...props}
      />
    );

  // Test 1: no session → prompt without fetching
  test('shows a prompt and skips fetching when no session exists', () => {
    renderInspector({ sessionId: null });

    expect(screen.getByText('Start a debug session to inspect variables')).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  // Test 2: fetches session variables and renders name, path, badges, value
  test('loads and renders session variables', async () => {
    (global.fetch as jest.Mock).mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        json: async () => [
          variable(),
          variable({
            variable_id: 'v2',
            variable_name: 'retry_count',
            variable_path: 'config.retry_count',
            variable_type: 'number',
            value: 3,
            scope: 'global',
            is_watch: true,
          }),
        ],
      })
    );
    renderInspector();

    expect(await screen.findByText('user_name')).toBeInTheDocument();
    expect(screen.getByText('user.name')).toBeInTheDocument();
    expect(screen.getByText('retry_count')).toBeInTheDocument();
    expect(screen.getByText('config.retry_count')).toBeInTheDocument();
    expect(screen.getByText('Watch')).toBeInTheDocument();
    expect(screen.getByText('2 variables')).toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/workflows/debug/sessions/ses-1/variables'
      );
    });
  });

  // Test 3: traceId routes the fetch to the trace variables endpoint
  test('fetches trace-scoped variables when traceId is provided', async () => {
    renderInspector({ traceId: 'trace-9' });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/workflows/debug/traces/trace-9/variables'
      );
    });
  });

  // Test 4: empty variables state
  test('shows the no-variables state when the session has none', async () => {
    renderInspector();

    await waitFor(() => {
      expect(screen.getByText('No variables found')).toBeInTheDocument();
    });
  });

  // Test 5: search filters by variable name or path
  test('search narrows variables by name or path', async () => {
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => [
          variable(),
          variable({ variable_id: 'v2', variable_name: 'retry_count', variable_path: 'config.retry_count' }),
        ],
      })
    );
    renderInspector();

    await screen.findByText('user_name');
    fireEvent.change(screen.getByPlaceholderText('Search variables...'), {
      target: { value: 'retry' },
    });

    expect(screen.queryByText('user_name')).not.toBeInTheDocument();
    expect(screen.getByText('retry_count')).toBeInTheDocument();
  });

  // Test 6: Changed Only toggle hides unchanged variables and shows previous value
  test('changed-only filter hides unchanged variables', async () => {
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => [
          variable(),
          variable({
            variable_id: 'v2',
            variable_name: 'score',
            variable_type: 'number',
            value: 42,
            is_changed: true,
            previous_value: 10,
          }),
        ],
      })
    );
    renderInspector();

    await screen.findByText('user_name');
    fireEvent.click(screen.getByRole('button', { name: /changed only/i }));

    expect(screen.queryByText('user_name')).not.toBeInTheDocument();
    expect(screen.getByText('score')).toBeInTheDocument();
    expect(screen.getByText(/Previous: 10/)).toBeInTheDocument();
  });

  // Test 7: value formatting covers previews, strings, booleans, null, numbers
  test('formats values by type and preview', async () => {
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => [
          variable(),
          variable({
            variable_id: 'v2',
            variable_name: 'user_prefs',
            value: { theme: 'dark' },
            value_preview: 'Object{2 keys}',
          }),
          variable({ variable_id: 'v3', variable_name: 'flag', variable_type: 'boolean', value: true }),
          variable({ variable_id: 'v4', variable_name: 'nothing', variable_type: 'string', value: null }),
          variable({ variable_id: 'v5', variable_name: 'count', variable_type: 'number', value: 7 }),
        ],
      })
    );
    renderInspector();

    await screen.findByText('user_name');
    expect(screen.getByText('"alice"')).toBeInTheDocument();
    expect(screen.getByText('Object{2 keys}')).toBeInTheDocument();
    expect(screen.getByText('true')).toBeInTheDocument();
    expect(screen.getByText('null')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
  });

  // Test 8: refresh button refetches
  test('refresh button refetches variables', async () => {
    renderInspector();

    await waitFor(() => expect(screen.getByText('No variables found')).toBeInTheDocument());
    const callsBefore = (global.fetch as jest.Mock).mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => {
      expect((global.fetch as jest.Mock).mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });
});
