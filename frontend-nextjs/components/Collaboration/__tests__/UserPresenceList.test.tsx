/**
 * UserPresenceList Component Tests
 *
 * Tests verify the real UserPresenceList component
 * (components/Collaboration/UserPresenceList.tsx):
 * - loading skeleton while participants are fetched
 * - renders participants with initials avatars, role badges, "You" marker,
 *   "View only" label and selected-node indicator
 * - empty state ("No active collaborators")
 * - fail-soft error handling
 * - stays on the loading state when no sessionId is provided (no fetch)
 *
 * API: GET /api/collaboration/sessions/:sessionId
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import UserPresenceList from '../UserPresenceList';

const participants = [
  {
    user_id: 'user-1',
    user_name: 'Alice Adams',
    user_color: '#ff0000',
    role: 'owner',
    can_edit: true,
    last_heartbeat: '2024-01-01T10:00:00Z',
  },
  {
    user_id: 'user-2',
    user_name: 'Bob Brown',
    user_color: '#00ff00',
    role: 'viewer',
    can_edit: false,
    selected_node: 'node-42',
    last_heartbeat: '2024-01-01T10:05:00Z',
  },
  {
    user_id: 'user-3',
    user_name: 'Carol',
    user_color: '#0000ff',
    role: 'editor',
    can_edit: true,
    last_heartbeat: '2024-01-01T10:01:00Z',
  },
];

const sessionHandlers = [
  rest.get('/api/collaboration/sessions/:sessionId', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ participants }));
  }),
];

describe('UserPresenceList', () => {
  beforeEach(() => {
    server.resetHandlers();
    server.use(...sessionHandlers);
  });

  it('shows a loading skeleton before participants arrive', () => {
    render(<UserPresenceList workflowId="wf-1" sessionId="sess-1" />);
    expect(screen.getByText('Active Users')).toBeInTheDocument();
    expect(document.querySelector('.animate-pulse')).not.toBeNull();
  });

  it('renders participants with initials, role badges and colors', async () => {
    render(<UserPresenceList workflowId="wf-1" sessionId="sess-1" currentUserId="user-1" />);

    await screen.findByText('Active Users (3)');
    expect(screen.getByText('Alice Adams')).toBeInTheDocument();
    expect(screen.getByText('Bob Brown')).toBeInTheDocument();
    expect(screen.getByText('AA')).toBeInTheDocument();
    expect(screen.getByText('BB')).toBeInTheDocument();
    expect(screen.getByText('C')).toBeInTheDocument();
    expect(screen.getByText('owner')).toBeInTheDocument();
    expect(screen.getByText('viewer')).toBeInTheDocument();
    expect(screen.getByText('editor')).toBeInTheDocument();
  });

  it('marks the current user with a "You" badge', async () => {
    render(<UserPresenceList workflowId="wf-1" sessionId="sess-1" currentUserId="user-1" />);

    await screen.findByText('Alice Adams');
    expect(screen.getByText('You')).toBeInTheDocument();
  });

  it('labels read-only participants with "View only" and shows their selection', async () => {
    render(<UserPresenceList workflowId="wf-1" sessionId="sess-1" />);

    await screen.findByText('Bob Brown');
    expect(screen.getByText('View only')).toBeInTheDocument();
    expect(screen.getByText(/node-42/)).toBeInTheDocument();
    expect(screen.queryByText('You')).not.toBeInTheDocument();
  });

  it('shows "No active collaborators" when the session has no participants', async () => {
    server.use(
      rest.get('/api/collaboration/sessions/:sessionId', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ participants: [] }));
      })
    );

    render(<UserPresenceList workflowId="wf-1" sessionId="sess-1" />);

    await screen.findByText('No active collaborators');
    expect(screen.getByText('Active Users (0)')).toBeInTheDocument();
  });

  it('fails soft on fetch errors and shows the empty state', async () => {
    server.use(
      rest.get('/api/collaboration/sessions/:sessionId', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<UserPresenceList workflowId="wf-1" sessionId="sess-1" />);

    await screen.findByText('No active collaborators');
  });

  it('does not fetch or render participants without a sessionId', () => {
    render(<UserPresenceList workflowId="wf-1" />);

    expect(screen.getByText('Active Users')).toBeInTheDocument();
    expect(document.querySelector('.animate-pulse')).not.toBeNull();
    expect(screen.queryByText('Alice Adams')).not.toBeInTheDocument();
    expect(screen.queryByText('No active collaborators')).not.toBeInTheDocument();
  });
});
