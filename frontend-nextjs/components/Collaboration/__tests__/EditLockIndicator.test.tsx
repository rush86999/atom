/**
 * EditLockIndicator Component Tests
 *
 * Tests verify the real EditLockIndicator component
 * (components/Collaboration/EditLockIndicator.tsx):
 * - loading skeleton while locks are being fetched
 * - renders active locks with per-resource icons, "You"/other-user badges,
 *   lock reasons, expiry text and "Locked" status
 * - empty state ("No active locks") and the user-facing info line based on
 *   whether the current user holds any lock
 * - fail-soft error handling (fetch failure -> empty state, no crash)
 * - 10s polling keeps refetching lock state
 *
 * API: GET /api/collaboration/locks/:workflowId
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import EditLockIndicator from '../EditLockIndicator';

interface LockFixture {
  lock_id: string;
  resource_type: string;
  resource_id: string;
  locked_by: string;
  locked_by_name?: string;
  locked_at: string;
  expires_at: string | null;
  lock_reason?: string;
}

const workflowLock: LockFixture = {
  lock_id: 'lock-1',
  resource_type: 'workflow',
  resource_id: 'wf-1',
  locked_by: 'user-2',
  locked_by_name: 'Alice',
  locked_at: '2024-01-01T10:00:00Z',
  expires_at: null,
  lock_reason: 'Refactoring the trigger nodes',
};

const nodeLock: LockFixture = {
  lock_id: 'lock-2',
  resource_type: 'node',
  resource_id: 'node-42',
  locked_by: 'user-1',
  locked_at: '2024-01-01T11:00:00Z',
  expires_at: '2024-01-01T12:30:00Z',
};

const edgeLock: LockFixture = {
  lock_id: 'lock-3',
  resource_type: 'edge',
  resource_id: 'edge-7',
  locked_by: 'user-3',
  locked_by_name: 'Bob',
  locked_at: '2024-01-01T09:00:00Z',
  expires_at: null,
};

const lockHandlers = [
  rest.get('/api/collaboration/locks/:workflowId', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ locks: [workflowLock, nodeLock, edgeLock] })
    );
  }),
];

describe('EditLockIndicator', () => {
  beforeEach(() => {
    server.resetHandlers();
    server.use(...lockHandlers);
  });

  it('shows a loading skeleton before locks arrive', () => {
    render(<EditLockIndicator workflowId="wf-1" currentUserId="user-1" />);
    expect(screen.getByText('Active Locks')).toBeInTheDocument();
    expect(document.querySelector('.animate-pulse')).not.toBeNull();
  });

  it('renders active locks with count, icon, owner badge and lock status', async () => {
    render(<EditLockIndicator workflowId="wf-1" currentUserId="user-1" />);

    await screen.findByText('Active Locks (3)');
    expect(screen.getByText('Entire workflow')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Refactoring the trigger nodes')).toBeInTheDocument();
    expect(screen.getAllByText('No expiry')).toHaveLength(2);
    expect(screen.getAllByText('Locked')).toHaveLength(3);
  });

  it('marks locks held by the current user with a "You" badge', async () => {
    render(<EditLockIndicator workflowId="wf-1" currentUserId="user-1" />);

    await screen.findByText('Active Locks (3)');
    expect(screen.getByText('You')).toBeInTheDocument();
    expect(screen.getByText('node: node-42')).toBeInTheDocument();
    expect(screen.getByText(/You have active locks\./)).toBeInTheDocument();
  });

  it('renders per-resource icons (workflow/node/edge) and expiry time', async () => {
    render(<EditLockIndicator workflowId="wf-1" currentUserId="user-1" />);

    await screen.findByText('Active Locks (3)');
    expect(screen.getByText('📄')).toBeInTheDocument();
    expect(screen.getByText('🔷')).toBeInTheDocument();
    expect(screen.getByText('🔗')).toBeInTheDocument();
    expect(screen.getByText('edge: edge-7')).toBeInTheDocument();
    expect(screen.getByText(`Expires ${new Date(nodeLock.expires_at!).toLocaleTimeString()}`)).toBeInTheDocument();
  });

  it('shows "No active locks" and the other-users info line when empty', async () => {
    server.use(
      rest.get('/api/collaboration/locks/:workflowId', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ locks: [] }));
      })
    );

    render(<EditLockIndicator workflowId="wf-1" currentUserId="user-1" />);

    await screen.findByText('No active locks');
    expect(screen.getByText(/Other users have locked resources\./)).toBeInTheDocument();
    expect(screen.getByText('Active Locks (0)')).toBeInTheDocument();
  });

  it('fails soft on fetch errors and renders the empty state', async () => {
    server.use(
      rest.get('/api/collaboration/locks/:workflowId', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<EditLockIndicator workflowId="wf-1" currentUserId="user-1" />);

    await screen.findByText('No active locks');
    expect(screen.queryByText('Alice')).not.toBeInTheDocument();
  });

  it('refetches locks on the 10-second polling interval', async () => {
    let requestCount = 0;
    server.use(
      rest.get('/api/collaboration/locks/:workflowId', (req, res, ctx) => {
        requestCount += 1;
        return res(ctx.status(200), ctx.json({ locks: [] }));
      })
    );

    render(<EditLockIndicator workflowId="wf-1" currentUserId="user-1" />);

    await screen.findByText('No active locks');
    expect(requestCount).toBeGreaterThanOrEqual(1);

    await waitFor(() => expect(requestCount).toBeGreaterThanOrEqual(2), { timeout: 15000 });
  });
});
