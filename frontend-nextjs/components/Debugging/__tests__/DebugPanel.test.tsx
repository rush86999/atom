/**
 * DebugPanel Component Tests
 *
 * Tests verify the REAL DebugPanel component
 * (components/Debugging/DebugPanel.tsx, a NAMED export):
 * - Fetches the active debug session on mount (GET .../debug/sessions?user_id=)
 * - Starts a debug session (POST .../debug/sessions) with the configured
 *   stop-on-entry/exceptions/error switches, reporting via onSessionChange
 * - Stops an active session (POST .../debug/sessions/:id/complete) and clears
 *   state via onSessionChange(null)
 * - Debug Settings collapsible toggles the run-configuration switches
 *
 * fetch is mocked directly (see components/Settings/__tests__/TwoFactorSettings.test.tsx).
 * The toast hook is globally stubbed in tests/setup.ts.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DebugPanel } from '../DebugPanel';

const activeSession = {
  session_id: 'ses-abcdef1234567890',
  workflow_id: 'wf-1',
  status: 'running',
  current_step: 2,
  current_node_id: 'node-b',
  session_name: null,
  created_at: '2026-08-01T10:00:00Z',
};

const newSession = {
  session_id: 'ses-new1234567890',
  workflow_id: 'wf-1',
  status: 'paused',
  current_step: 0,
  current_node_id: null,
  session_name: null,
  created_at: '2026-08-06T10:00:00Z',
};

describe('DebugPanel', () => {
  let activeSessions: any[];
  let lastPostBody: any = null;
  let postCount = 0;

  beforeEach(() => {
    activeSessions = [];
    lastPostBody = null;
    postCount = 0;
    global.fetch = jest.fn((url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      if (init?.method === 'POST') {
        postCount += 1;
        if (u.includes('/complete')) {
          return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
        }
        lastPostBody = JSON.parse(String(init.body));
        return Promise.resolve({ ok: true, json: async () => newSession });
      }
      if (u.includes('/debug/sessions')) {
        return Promise.resolve({ ok: true, json: async () => activeSessions });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
      // fixture returns partial Response objects; cast the completed mock
    }) as unknown as typeof fetch;
  });

  // Test 1: shows the workflow name and a Start button when no session is active
  test('renders workflow name and Start Debugging when no session is active', async () => {
    render(
      <DebugPanel workflowId="wf-1" workflowName="Onboarding Flow" currentUserId="user-1" />
    );

    expect(await screen.findByRole('button', { name: /start debugging/i })).toBeInTheDocument();
    expect(screen.getByText('Onboarding Flow')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /debug panel/i })).toBeInTheDocument();
  });

  // Test 2: fetches and displays the active session on mount
  test('loads the active session and shows its status, step, and node', async () => {
    activeSessions = [activeSession];
    const onSessionChange = jest.fn();

    render(
      <DebugPanel
        workflowId="wf-1"
        workflowName="Onboarding Flow"
        currentUserId="user-1"
        onSessionChange={onSessionChange}
      />
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /stop/i })).toBeInTheDocument();
    });
    expect(screen.getByText('running')).toBeInTheDocument();
    expect(screen.getByText(/ses-abc/)).toBeInTheDocument();
    expect(screen.getByText('Step 2')).toBeInTheDocument();
    expect(screen.getByText('node-b')).toBeInTheDocument();
    expect(onSessionChange).toHaveBeenCalledWith(activeSession);
  });

  // Test 3: starting a session POSTs the workflow + current switch settings
  test('starts a debug session with stop-on settings and notifies parent', async () => {
    const onSessionChange = jest.fn();
    render(
      <DebugPanel
        workflowId="wf-1"
        workflowName="Onboarding Flow"
        currentUserId="user-1"
        onSessionChange={onSessionChange}
      />
    );

    fireEvent.click(await screen.findByRole('button', { name: /start debugging/i }));

    await waitFor(() => {
      expect(postCount).toBe(1);
    });
    // Defaults: stopOnEntry=false, stopOnExceptions=true, stopOnError=true
    expect(lastPostBody).toEqual({
      workflow_id: 'wf-1',
      stop_on_entry: false,
      stop_on_exceptions: true,
      stop_on_error: true,
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /stop/i })).toBeInTheDocument();
    });
    expect(onSessionChange).toHaveBeenCalledWith(newSession);
  });

  // Test 4: Debug Settings collapsible toggles the switches, which feed the POST body
  test('debug settings switches control the start-session payload', async () => {
    render(
      <DebugPanel workflowId="wf-1" workflowName="Onboarding Flow" currentUserId="user-1" />
    );

    // Settings are collapsed initially
    expect(screen.queryByRole('switch', { name: 'Stop on Entry' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /debug settings/i }));
    expect(screen.getByRole('switch', { name: 'Stop on Entry' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('switch', { name: 'Stop on Entry' }));
    fireEvent.click(screen.getByRole('switch', { name: 'Stop on Exceptions' }));

    fireEvent.click(screen.getByRole('button', { name: /start debugging/i }));

    await waitFor(() => {
      expect(lastPostBody).toEqual({
        workflow_id: 'wf-1',
        stop_on_entry: true,
        stop_on_exceptions: false,
        stop_on_error: true,
      });
    });
  });

  // Test 5: Stop completes the session and clears state
  test('stops the active session and notifies the parent with null', async () => {
    activeSessions = [activeSession];
    const onSessionChange = jest.fn();

    render(
      <DebugPanel
        workflowId="wf-1"
        workflowName="Onboarding Flow"
        currentUserId="user-1"
        onSessionChange={onSessionChange}
      />
    );

    const stopBtn = await screen.findByRole('button', { name: /stop/i });
    fireEvent.click(stopBtn);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /start debugging/i })).toBeInTheDocument();
    });
    const completeCall = (global.fetch as jest.Mock).mock.calls.find(([url, init]) =>
      String(url).includes('/complete')
    );
    expect(completeCall?.[1]?.method).toBe('POST');
    expect(onSessionChange).toHaveBeenCalledWith(null);
    expect(screen.queryByText('running')).not.toBeInTheDocument();
  });
});
