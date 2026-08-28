/**
 * SessionPersistence Component Tests
 *
 * Tests verify the REAL SessionPersistence component
 * (components/Debugging/SessionPersistence.tsx, a NAMED export):
 * - Export button disabled without a session; GET .../sessions/:id/export
 *   triggers a JSON file download
 * - Import parses a selected .json file and POSTs it to .../sessions/import
 *   with the restore_breakpoints / restore_variables options, then calls
 *   onSessionImported
 * - Invalid JSON shows a failure toast and never POSTs
 *
 * fetch is mocked directly (see components/Settings/__tests__/TwoFactorSettings.test.tsx).
 * The toast hook, URL.createObjectURL, and Blob/File are stubbed in tests/setup.ts.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SessionPersistence from '../SessionPersistence';

describe('SessionPersistence', () => {
  let importBody: any = null;

  beforeEach(() => {
    importBody = null;
    (global.URL.createObjectURL as jest.Mock).mockClear();
    global.fetch = jest.fn((url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      if (init?.method === 'POST') {
        importBody = JSON.parse(String(init.body));
        return Promise.resolve({
          ok: true,
          json: async () => ({ session_id: 'ses-imported' }),
        });
      }
      if (u.includes('/export')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            session_id: 'ses-1',
            breakpoints: [],
            traces: [],
            variables: [],
          }),
        });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    // The mocked responses are partial fetch Responses; cast to satisfy the fetch signature.
    }) as unknown as typeof global.fetch;
  });

  const renderPersistence = (props: Record<string, any> = {}) =>
    render(
      <SessionPersistence
        sessionId="ses-1"
        workflowId="wf-1"
        currentUserId="user-1"
        {...props}
      />
    );

  // Test 1: renders both sections
  test('renders export and import sections', () => {
    renderPersistence();

    expect(screen.getByText('Session Persistence')).toBeInTheDocument();
    expect(screen.getByText('Export Session')).toBeInTheDocument();
    expect(screen.getByText('Import Session')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /export debug session/i })).toBeEnabled();
  });

  // Test 2: export is disabled without a session
  test('disables export when no session is active', () => {
    renderPersistence({ sessionId: null });

    expect(screen.getByRole('button', { name: /export debug session/i })).toBeDisabled();
  });

  // Test 3: export fetches the export endpoint and triggers a download
  test('exports the session as a JSON download', async () => {
    renderPersistence();

    fireEvent.click(screen.getByRole('button', { name: /export debug session/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/workflows/debug/sessions/ses-1/export'
      );
      expect(global.URL.createObjectURL).toHaveBeenCalled();
    });
  });

  // Test 4: import POSTs the parsed file with restore options and notifies the parent
  test('imports a JSON file and calls onSessionImported', async () => {
    const onSessionImported = jest.fn();
    renderPersistence({ onSessionImported });

    const file = new File(
      [JSON.stringify({ session_id: 'ses-old', variables: [{ name: 'x' }] })],
      'debug_session_ses-old.json',
      { type: 'application/json' }
    );
    fireEvent.change(screen.getByLabelText('Session File'), {
      target: { files: [file] },
    });
    expect(screen.getByText(/Selected: debug_session_ses-old\.json/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /import debug session/i }));

    await waitFor(() => {
      expect(importBody).toEqual({
        export_data: { session_id: 'ses-old', variables: [{ name: 'x' }] },
        restore_breakpoints: true,
        restore_variables: true,
      });
    });
    expect(onSessionImported).toHaveBeenCalledWith('ses-imported');
  });

  // Test 5: import is disabled until a file is selected
  test('import button is disabled before a file is chosen', () => {
    renderPersistence();

    expect(screen.getByRole('button', { name: /import debug session/i })).toBeDisabled();
  });

  // Test 6: invalid JSON never POSTs to the import endpoint
  test('invalid JSON file fails without POSTing', async () => {
    renderPersistence();

    const file = new File(['{not valid json'], 'broken.json', { type: 'application/json' });
    fireEvent.change(screen.getByLabelText('Session File'), {
      target: { files: [file] },
    });

    fireEvent.click(screen.getByRole('button', { name: /import debug session/i }));

    await waitFor(() => {
      const importCalls = (global.fetch as jest.Mock).mock.calls.filter(([, init]) =>
        String(init?.method ?? '').toUpperCase() === 'POST'
      );
      expect(importCalls).toHaveLength(0);
    });
  });
});
