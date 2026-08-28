/**
 * CollaborativeDebugging Component Tests
 *
 * Tests verify the REAL CollaborativeDebugging component
 * (components/Debugging/CollaborativeDebugging.tsx, a NAMED export):
 * - Fetches collaborators (GET .../sessions/:id/collaborators)
 * - Owner-only surfaces: Add Collaborator form, Invite Link, remove buttons
 * - Add collaborator (POST ?user_id=..&permission=..), remove (DELETE)
 * - Invite link copies /debug?session=<id> to the clipboard
 * - Permission badges (Viewer / Operator / Owner)
 *
 * fetch is mocked directly (see components/Settings/__tests__/TwoFactorSettings.test.tsx).
 * The toast hook is globally stubbed in tests/setup.ts; navigator.clipboard is
 * mocked in tests/setup.ts.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import CollaborativeDebugging from '../CollaborativeDebugging';

const collab = (overrides: Record<string, any> = {}) => ({
  user_id: 'user-2',
  permission: 'viewer',
  added_at: '2026-08-01T10:00:00Z',
  ...overrides,
});

describe('CollaborativeDebugging', () => {
  let storedCollabs: any[];
  let postUrl: string | null = null;

  beforeEach(() => {
    storedCollabs = [];
    postUrl = null;
    (navigator.clipboard.writeText as jest.Mock).mockClear();
    global.fetch = jest.fn((url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      if (init?.method === 'DELETE') {
        const id = u.split('/collaborators/')[1].split('?')[0];
        storedCollabs = storedCollabs.filter((c) => c.user_id !== id);
        return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
      }
      if (init?.method === 'POST') {
        postUrl = u;
        storedCollabs = [
          ...storedCollabs,
          collab({
            user_id: new URLSearchParams(u.split('?')[1]).get('user_id'),
            permission: new URLSearchParams(u.split('?')[1]).get('permission'),
          }),
        ];
        return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
      }
      if (u.includes('/collaborators')) {
        return Promise.resolve({ ok: true, json: async () => ({ collaborators: storedCollabs }) });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    }) as unknown as typeof fetch;
  });

  const renderOwner = (props: Record<string, any> = {}) =>
    render(
      <CollaborativeDebugging
        sessionId="ses-1"
        workflowId="wf-1"
        currentUserId="user-1"
        isOwner
        {...props}
      />
    );

  // Test 1: owner sees the add form, invite link, and fetched collaborators
  test('owner sees add form, invite link, and collaborator rows with badges', async () => {
    storedCollabs = [collab(), collab({ user_id: 'user-3', permission: 'op' })];
    renderOwner();

    expect(await screen.findByText('user-2')).toBeInTheDocument();
    expect(screen.getByText('user-3')).toBeInTheDocument();
    expect(screen.getByText('3 participants')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /invite link/i })).toBeInTheDocument();
    expect(screen.getByText('Add Collaborator')).toBeInTheDocument();
    expect(screen.getByText('Session Owner')).toBeInTheDocument();
    expect(screen.getByText('user-1')).toBeInTheDocument();
    expect(screen.getAllByText('Viewer').length).toBeGreaterThan(0);
    expect(screen.getByText('Operator')).toBeInTheDocument();
    expect(screen.getByText('Owner')).toBeInTheDocument();
  });

  // Test 2: non-owner sees none of the management surfaces
  test('non-owner view hides add form, invite link, and remove buttons', async () => {
    storedCollabs = [collab()];
    render(
      <CollaborativeDebugging
        sessionId="ses-1"
        workflowId="wf-1"
        currentUserId="user-1"
        isOwner={false}
      />
    );

    await screen.findByText('user-2');
    expect(screen.queryByText('Add Collaborator')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /invite link/i })).not.toBeInTheDocument();
    expect(screen.getByText('Viewer')).toBeInTheDocument();
  });

  // Test 3: without a session nothing is fetched and no add UI is shown for owners
  test('does not fetch collaborators when sessionId is null', () => {
    render(
      <CollaborativeDebugging
        sessionId={null}
        workflowId="wf-1"
        currentUserId="user-1"
        isOwner
      />
    );

    expect(screen.getByText('No collaborators yet. Add someone to debug together!')).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  // Test 4: invite link copies the session deep link to the clipboard
  test('copies the invite link for the active session', async () => {
    renderOwner();

    fireEvent.click(await screen.findByRole('button', { name: /invite link/i }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        `${window.location.origin}/debug?session=ses-1`
      );
    });
  });

  // Test 5: adding a collaborator POSTs user_id + permission and refreshes
  test('adds a collaborator as viewer by default', async () => {
    renderOwner();

    fireEvent.change(
      await screen.findByPlaceholderText('User ID or email'),
      { target: { value: 'user-9' } }
    );
    const addBtn = within(
      screen.getByText('Add Collaborator').closest('div.p-3') as HTMLElement
    ).getByRole('button', { name: '' });
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(postUrl).toContain('user_id=user-9');
      expect(postUrl).toContain('permission=viewer');
    });
    expect(await screen.findByText('user-9')).toBeInTheDocument();
  });

  // Test 6: removing a collaborator DELETEs them and refreshes
  test('removes a collaborator via DELETE', async () => {
    storedCollabs = [collab(), collab({ user_id: 'user-3', permission: 'op' })];
    renderOwner();

    await screen.findByText('user-2');
    const row = screen.getByText('user-2').closest('div.border') as HTMLElement;
    fireEvent.click(within(row).getByRole('button', { name: '' }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/workflows/debug/sessions/ses-1/collaborators/user-2',
        { method: 'DELETE' }
      );
    });
    expect(screen.queryByText('user-2')).not.toBeInTheDocument();
    expect(screen.getByText('user-3')).toBeInTheDocument();
  });
});
