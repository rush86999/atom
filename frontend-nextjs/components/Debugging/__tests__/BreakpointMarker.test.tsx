/**
 * BreakpointMarker Component Tests
 *
 * Tests verify the REAL BreakpointMarker component
 * (components/Debugging/BreakpointMarker.tsx, a NAMED export):
 * - Fetches active breakpoints on mount (GET .../debug/breakpoints?active_only=true)
 * - Renders breakpoint rows (condition, hit limit, hit count, log message)
 * - Add form validation (requires a node) and POST of a new breakpoint
 * - Remove (DELETE) and toggle (PUT .../toggle) round-trips
 * - onBreakpointsChange callback with the fetched list
 *
 * fetch is mocked directly (see components/Settings/__tests__/TwoFactorSettings.test.tsx).
 * The toast hook is globally stubbed in tests/setup.ts.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import BreakpointMarker from '../BreakpointMarker';

const nodes = [
  { id: 'node-a', name: 'Fetch Users', type: 'http' },
  { id: 'node-b', name: 'Send Email', type: 'email' },
];

const seedBreakpoint = (overrides: Record<string, any> = {}) => ({
  breakpoint_id: 'bp-1',
  node_id: 'node-a',
  edge_id: null,
  breakpoint_type: 'node',
  condition: null,
  hit_count: 0,
  hit_limit: null,
  is_active: true,
  is_disabled: false,
  log_message: null,
  created_at: '2026-08-01T10:00:00Z',
  ...overrides,
});

describe('BreakpointMarker', () => {
  let storedBreakpoints: any[];
  let postBody: any = null;

  beforeEach(() => {
    storedBreakpoints = [];
    postBody = null;
    // The mocked responses are plain objects, not real Response instances.
    global.fetch = jest.fn((url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      if (u.includes('/toggle')) {
        storedBreakpoints = storedBreakpoints.map((b) => ({
          ...b,
          is_disabled: !b.is_disabled,
        }));
        return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
      }
      if (init?.method === 'DELETE') {
        const id = u.split('/debug/breakpoints/')[1].split('?')[0];
        storedBreakpoints = storedBreakpoints.filter((b) => b.breakpoint_id !== id);
        return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
      }
      if (init?.method === 'POST') {
        postBody = JSON.parse(String(init.body));
        storedBreakpoints = [
          ...storedBreakpoints,
          seedBreakpoint({ ...postBody, breakpoint_id: 'bp-new' }),
        ];
        return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
      }
      if (u.includes('/debug/breakpoints')) {
        return Promise.resolve({ ok: true, json: async () => storedBreakpoints });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    }) as unknown as typeof fetch;
  });

  // Test 1: empty state with the add hint
  test('renders the empty state when no breakpoints exist', async () => {
    render(
      <BreakpointMarker workflowId="wf-1" currentUserId="user-1" nodes={nodes} />
    );

    await waitFor(() => {
      expect(screen.getByText('No breakpoints set')).toBeInTheDocument();
    });
    expect(screen.getByText('Click + to add a breakpoint')).toBeInTheDocument();
    expect(screen.getByText('0 breakpoints')).toBeInTheDocument();
  });

  // Test 2: fetches and renders breakpoints with condition/limit/hits/log
  test('renders fetched breakpoints and notifies onBreakpointsChange', async () => {
    storedBreakpoints = [
      seedBreakpoint({
        condition: "user_id == '123'",
        hit_limit: 5,
        hit_count: 2,
        log_message: 'first user step',
      }),
      seedBreakpoint({ breakpoint_id: 'bp-2', node_id: 'node-b', is_disabled: true }),
    ];
    const onBreakpointsChange = jest.fn();

    render(
      <BreakpointMarker
        workflowId="wf-1"
        currentUserId="user-1"
        nodes={nodes}
        onBreakpointsChange={onBreakpointsChange}
      />
    );

    expect(await screen.findByText('node-a')).toBeInTheDocument();
    expect(screen.getByText("Cond: user_id == '123'")).toBeInTheDocument();
    expect(screen.getByText('Limit: 5')).toBeInTheDocument();
    expect(screen.getByText('Hits: 2')).toBeInTheDocument();
    expect(screen.getByText('Log: first user step')).toBeInTheDocument();
    expect(screen.getByText('2 breakpoints')).toBeInTheDocument();
    expect(onBreakpointsChange).toHaveBeenCalledWith(storedBreakpoints);
  });

  // Test 3: disabled breakpoints expose an Enable action
  test('disabled breakpoints show Enable instead of Disable', async () => {
    storedBreakpoints = [
      seedBreakpoint({ breakpoint_id: 'bp-2', node_id: 'node-b', is_disabled: true }),
    ];

    render(
      <BreakpointMarker workflowId="wf-1" currentUserId="user-1" nodes={nodes} />
    );

    expect(await screen.findByRole('button', { name: 'Enable' })).toBeInTheDocument();
  });

  // Test 4: adding a breakpoint requires a selected node (no POST without one)
  test('shows an error toast and skips the POST when no node is selected', async () => {
    render(<BreakpointMarker workflowId="wf-1" currentUserId="user-1" nodes={nodes} />);

    await waitFor(() => expect(screen.getByText('No breakpoints set')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '' })); // the + toggle
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    await waitFor(() => {
      expect(screen.getByText('No breakpoints set')).toBeInTheDocument();
    });
    // Only the initial GET happened — no POST with an empty node selection
    expect((global.fetch as jest.Mock).mock.calls.some(([, init]) => init?.method === 'POST')).toBe(
      false
    );
  });

  // Test 5: adds a breakpoint with node, condition, hit limit, and log message
  test('posts a new breakpoint with node, condition, hit limit, and log message', async () => {
    render(
      <BreakpointMarker
        workflowId="wf-1"
        currentUserId="user-1"
        debugSessionId="ses-1"
        nodes={nodes}
      />
    );

    await waitFor(() => expect(screen.getByText('No breakpoints set')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '' }));

    fireEvent.change(screen.getByLabelText('Node'), { target: { value: 'node-a' } });
    fireEvent.change(screen.getByLabelText('Condition (Optional)'), {
      target: { value: "user_id == '123'" },
    });
    fireEvent.change(screen.getByLabelText('Hit Limit (Optional)'), {
      target: { value: '3' },
    });
    fireEvent.change(screen.getByLabelText('Log Message (Optional)'), {
      target: { value: 'checking user' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    await waitFor(() => {
      expect(postBody).toEqual({
        workflow_id: 'wf-1',
        node_id: 'node-a',
        debug_session_id: 'ses-1',
        condition: "user_id == '123'",
        hit_limit: 3,
        log_message: 'checking user',
      });
    });
    // Refetched list renders the new breakpoint
    expect(await screen.findByText('Limit: 3')).toBeInTheDocument();
    expect(screen.getByText("Cond: user_id == '123'")).toBeInTheDocument();
  });

  // Test 6: removing a breakpoint DELETEs it and refreshes the list
  test('removes a breakpoint via DELETE and shows the empty state again', async () => {
    storedBreakpoints = [seedBreakpoint()];

    render(<BreakpointMarker workflowId="wf-1" currentUserId="user-1" nodes={nodes} />);

    const row = (await screen.findByText('node-a')).closest('div.border') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: '' })); // trash icon button

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/workflows/debug/breakpoints/bp-1?user_id=user-1',
        { method: 'DELETE' }
      );
    });
    expect(await screen.findByText('No breakpoints set')).toBeInTheDocument();
  });

  // Test 7: toggling a breakpoint PUTs the toggle endpoint and refreshes
  test('toggles a breakpoint and reflects the new state', async () => {
    storedBreakpoints = [seedBreakpoint()];

    render(<BreakpointMarker workflowId="wf-1" currentUserId="user-1" nodes={nodes} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Disable' }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/workflows/debug/breakpoints/bp-1/toggle?user_id=user-1',
        { method: 'PUT' }
      );
    });
    expect(await screen.findByRole('button', { name: 'Enable' })).toBeInTheDocument();
  });
});
