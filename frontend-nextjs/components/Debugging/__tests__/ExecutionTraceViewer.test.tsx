/**
 * ExecutionTraceViewer Component Tests
 *
 * Tests verify the REAL ExecutionTraceViewer component
 * (components/Debugging/ExecutionTraceViewer.tsx, a NAMED export):
 * - Fetches traces on mount (GET .../executions/:id/traces?debug_session_id=..)
 * - Renders step rows with status badges, node types, durations ("Running...")
 * - Expand/collapse reveals timestamps, input/output data, errors, variable changes
 * - Search + status filter narrow the list; refresh refetches
 *
 * fetch is mocked directly (see components/Settings/__tests__/TwoFactorSettings.test.tsx).
 * The toast hook is globally stubbed in tests/setup.ts.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import ExecutionTraceViewer from '../ExecutionTraceViewer';

const trace = (overrides: Record<string, any> = {}) => ({
  trace_id: 't1',
  workflow_id: 'wf-1',
  execution_id: 'ex-1',
  debug_session_id: 'ses-1',
  step_number: 1,
  node_id: 'fetch-users',
  node_type: 'http',
  status: 'completed',
  input_data: { url: 'https://api.example.com/users' },
  output_data: { count: 2 },
  error_message: '',
  variable_changes: [
    { variable: 'users', type: 'updated', old_value: [], new_value: [1, 2] },
  ],
  started_at: '2026-08-01T10:00:00Z',
  completed_at: '2026-08-01T10:00:01Z',
  duration_ms: 250,
  ...overrides,
});

describe('ExecutionTraceViewer', () => {
  beforeEach(() => {
    global.fetch = jest.fn(
      () => Promise.resolve({ ok: true, json: async () => [] })
    ) as unknown as typeof fetch;
  });

  const renderViewer = (props: Record<string, any> = {}) =>
    render(
      <ExecutionTraceViewer
        executionId="ex-1"
        workflowId="wf-1"
        currentUserId="user-1"
        debugSessionId="ses-1"
        {...props}
      />
    );

  // Test 1: fetches traces with the debug session id and renders step rows
  test('loads traces and renders step rows with status and duration', async () => {
    (global.fetch as jest.Mock).mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        json: async () => [
          trace(),
          trace({
            trace_id: 't2',
            step_number: 2,
            node_id: 'send-email',
            node_type: 'action',
            status: 'failed',
            error_message: 'SMTP connection refused',
            duration_ms: 0,
            output_data: {},
            variable_changes: [],
          }),
        ],
      })
    );
    renderViewer();

    expect(await screen.findByText('Step 1')).toBeInTheDocument();
    expect(screen.getByText('Step 2')).toBeInTheDocument();
    expect(screen.getByText('fetch-users')).toBeInTheDocument();
    expect(screen.getByText('send-email')).toBeInTheDocument();
    expect(screen.getByText('250ms')).toBeInTheDocument();
    expect(screen.getByText('Running...')).toBeInTheDocument();
    expect(screen.getByText('2 steps')).toBeInTheDocument();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/workflows/executions/ex-1/traces?debug_session_id=ses-1'
      );
    });
  });

  // Test 2: empty state
  test('shows the empty state when no traces exist', async () => {
    renderViewer();

    await waitFor(() => {
      expect(screen.getByText('No execution traces found')).toBeInTheDocument();
    });
    expect(screen.getByText('0 steps')).toBeInTheDocument();
  });

  // Test 3: expanding a trace reveals input/output data and variable changes
  test('expanding a completed trace shows timestamps, I/O, and variable changes', async () => {
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({ ok: true, json: async () => [trace()] })
    );
    renderViewer();

    fireEvent.click(await screen.findByText('Step 1'));

    expect(screen.getByText('Input Data')).toBeInTheDocument();
    expect(screen.getByText(/https:\/\/api\.example\.com\/users/)).toBeInTheDocument();
    expect(screen.getByText('Output Data')).toBeInTheDocument();
    expect(screen.getByText('Variable Changes')).toBeInTheDocument();
    expect(screen.getByText(/\[UPDATED\]/)).toBeInTheDocument();
    expect(screen.getByText('users')).toBeInTheDocument();
    expect(screen.getByText('Started')).toBeInTheDocument();
    expect(screen.getByText('Completed')).toBeInTheDocument();
  });

  // Test 4: failed traces surface their error message
  test('expanding a failed trace shows the error message', async () => {
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => [
          trace({
            trace_id: 't2',
            step_number: 2,
            node_id: 'send-email',
            node_type: 'action',
            status: 'failed',
            error_message: 'SMTP connection refused',
            variable_changes: [],
          }),
        ],
      })
    );
    renderViewer();

    fireEvent.click(await screen.findByText('Step 2'));

    expect(screen.getByText('Error')).toBeInTheDocument();
    expect(screen.getByText('SMTP connection refused')).toBeInTheDocument();
  });

  // Test 5: search narrows the visible traces
  test('search filters traces by node id', async () => {
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => [
          trace(),
          trace({
            trace_id: 't2',
            step_number: 2,
            node_id: 'send-email',
            node_type: 'action',
            status: 'started',
          }),
        ],
      })
    );
    renderViewer();

    await screen.findByText('Step 1');
    fireEvent.change(screen.getByPlaceholderText('Search traces...'), {
      target: { value: 'email' },
    });

    expect(screen.queryByText('Step 1')).not.toBeInTheDocument();
    expect(screen.getByText('Step 2')).toBeInTheDocument();
  });

  // Test 6: status filter narrows the visible traces
  test('status filter shows only failed traces', async () => {
    const user = userEvent.setup();
    (global.fetch as jest.Mock).mockImplementation(() =>
      Promise.resolve({
        ok: true,
        json: async () => [
          trace(),
          trace({
            trace_id: 't2',
            step_number: 2,
            node_id: 'send-email',
            node_type: 'action',
            status: 'failed',
          }),
        ],
      })
    );
    renderViewer();

    await screen.findByText('Step 1');
    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByText('Failed'));

    expect(screen.queryByText('Step 1')).not.toBeInTheDocument();
    expect(screen.getByText('Step 2')).toBeInTheDocument();
  });

  // Test 7: refresh button refetches traces
  test('refresh button refetches the trace list', async () => {
    renderViewer();

    await waitFor(() => expect(screen.getByText('No execution traces found')).toBeInTheDocument());
    const callsBefore = (global.fetch as jest.Mock).mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => {
      expect((global.fetch as jest.Mock).mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });
});
