/**
 * NotificationsBell Component Tests
 *
 * Verifies the real notification center bell (components/layout/NotificationsBell.tsx):
 * - fetches /api/notifications on mount and shows unread-count badge
 * - dropdown open/close (button toggle + outside click)
 * - empty state ("You're all caught up.")
 * - mark-all-read flow (POST /read-all + refetch)
 * - per-item read flow (POST /:id/read, optimistic unread decrement)
 * - bearer token attached from localStorage
 * - graceful degradation on fetch failure / non-ok responses
 *
 * Uses the shared MSW server; the bell talks to
 * ${NEXT_PUBLIC_API_URL||http://localhost:8000}/api/notifications.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import { NotificationsBell } from '../NotificationsBell';

jest.mock('next/link', () => {
  const Link = ({ href, children, onClick }: any) => (
    <a href={href} onClick={onClick}>
      {children}
    </a>
  );
  return { __esModule: true, default: Link };
});

const notifications = [
  {
    id: 'n1',
    type: 'message',
    title: 'New message from Alice',
    message: 'Can you review the PR?',
    read: false,
    action_url: '/agents/agent-1',
    action_label: 'View agent',
    created_at: '2026-08-09T10:00:00Z',
  },
  {
    id: 'n2',
    type: 'alert',
    title: 'Workflow completed',
    message: 'The nightly backup finished.',
    read: true,
  },
];

let getCount = 0;

const notifyHandlers = [
  rest.get('*api/notifications', (req, res, ctx) => {
    getCount += 1;
    console.log('DBG_OLD_FIRED', req.url.href);
    return res(
      ctx.status(200),
      ctx.json({ data: { notifications, unread_count: 1 } })
    );
  }),
  rest.post('*api/notifications/read-all', (req, res, ctx) =>
    res(ctx.status(200), ctx.json({ success: true }))
  ),
  rest.post('*api/notifications/:id/read', (req, res, ctx) =>
    res(ctx.status(200), ctx.json({ success: true }))
  ),
];

const setNotifications = (notifs: any[], unreadCount: number) => {
  server.use(
    rest.get('*api/notifications', (req, res, ctx) => {
      getCount += 1;
      return res(
        ctx.status(200),
        ctx.json({ data: { notifications: notifs, unread_count: unreadCount } })
      );
    })
  );
};

const mockLocalStorage = () => {
  const store: Record<string, string> = {};
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: jest.fn((key: string) => store[key] ?? null),
      setItem: jest.fn((key: string, value: string) => {
        store[key] = value;
      }),
      removeItem: jest.fn((key: string) => {
        delete store[key];
      }),
      clear: jest.fn(() => {
        Object.keys(store).forEach((k) => delete store[k]);
      }),
      key: jest.fn(),
      length: 0,
    },
  });
  return store;
};

describe('NotificationsBell', () => {
  beforeEach(() => {
    getCount = 0;
    mockLocalStorage();
    server.resetHandlers();
    server.use(...notifyHandlers);
  });

  test('renders bell button without unread badge when nothing unread', async () => {
    setNotifications([], 0);

    render(<NotificationsBell />);

    const bell = await screen.findByRole('button', { name: 'Notifications' });
    expect(bell).toBeInTheDocument();
    expect(screen.queryByText('9+')).not.toBeInTheDocument();
  });

  test('shows unread count badge after fetch', async () => {
    render(<NotificationsBell />);

    const bell = await screen.findByRole('button', {
      name: 'Notifications (1 unread)',
    });
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  test('caps the badge at 9+', async () => {
    setNotifications([], 42);

    render(<NotificationsBell />);

    await screen.findByRole('button', { name: 'Notifications (42 unread)' });
    expect(screen.getByText('9+')).toBeInTheDocument();
  });

  test('opens dropdown with notification items and action labels', async () => {
    render(<NotificationsBell />);

    const bell = await screen.findByRole('button', { name: /unread/ });
    fireEvent.click(bell);

    expect(await screen.findByText('New message from Alice')).toBeInTheDocument();
    expect(screen.getByText('Can you review the PR?')).toBeInTheDocument();
    expect(screen.getByText('Workflow completed')).toBeInTheDocument();
    // action_label is rendered for items that carry an action_url
    expect(screen.getByText('View agent')).toBeInTheDocument();
    // the actionable item is a link
    expect(screen.getByRole('link', { name: /new message from alice/i })).toHaveAttribute(
      'href',
      '/agents/agent-1'
    );
  });

  test('shows empty state when there are no notifications', async () => {
    setNotifications([], 0);

    render(<NotificationsBell />);

    fireEvent.click(await screen.findByRole('button', { name: 'Notifications' }));
    expect(await screen.findByText(/all caught up/)).toBeInTheDocument();
  });

  test('mark all read posts and refetches notifications', async () => {
    render(<NotificationsBell />);

    const bell = await screen.findByRole('button', { name: /unread/ });
    fireEvent.click(bell);

    const markAllButton = await screen.findByRole('button', {
      name: /mark all read/i,
    });
    fireEvent.click(markAllButton);

    await waitFor(() => expect(getCount).toBeGreaterThanOrEqual(2));
  });

  test('clicking an unread notification marks it read optimistically and closes the dropdown', async () => {
    render(<NotificationsBell />);

    const bell = await screen.findByRole('button', { name: /unread/ });
    fireEvent.click(bell);

    fireEvent.click(
      await screen.findByRole('link', { name: /new message from alice/i })
    );

    await waitFor(() => {
      expect(bell).toHaveAttribute('aria-label', 'Notifications');
    });
    // dropdown closed after handling the item
    expect(screen.queryByText('New message from Alice')).not.toBeInTheDocument();
  });

  test('clicking an already-read notification does not change unread count', async () => {
    render(<NotificationsBell />);

    const bell = await screen.findByRole('button', { name: /unread/ });
    fireEvent.click(bell);

    fireEvent.click(await screen.findByText('Workflow completed'));

    await waitFor(() => {
      expect(bell).toHaveAttribute('aria-label', 'Notifications (1 unread)');
    });
  });

  test('closes the dropdown on outside click', async () => {
    render(<NotificationsBell />);

    const bell = await screen.findByRole('button', { name: /unread/ });
    fireEvent.click(bell);
    expect(await screen.findByText('New message from Alice')).toBeInTheDocument();

    fireEvent.mouseDown(document.body);

    await waitFor(() => {
      expect(screen.queryByText('New message from Alice')).not.toBeInTheDocument();
    });
  });

  test('sends the bearer token from localStorage', async () => {
    (window.localStorage.getItem as jest.Mock).mockReturnValue('tok123');
    let authHeader: string | null = null;
    server.use(
      rest.get('*api/notifications', (req, res, ctx) => {
        authHeader = req.headers.get('Authorization');
        return res(ctx.status(200), ctx.json({ data: { notifications: [], unread_count: 0 } }));
      })
    );

    render(<NotificationsBell />);

    await screen.findByRole('button', { name: 'Notifications' });
    await waitFor(() => expect(authHeader).toBe('Bearer tok123'));
  });

  test('tolerates network failure on fetch', async () => {
    server.use(
      rest.get(/\/api\/notifications/, (req, res, ctx) => res.networkError('boom'))
    );

    render(<NotificationsBell />);

    const bell = await screen.findByRole('button', { name: 'Notifications' });
    fireEvent.click(bell);
    expect(await screen.findByText(/all caught up/)).toBeInTheDocument();
  });

  test('tolerates non-ok responses', async () => {
    server.use(
      rest.get(/\/api\/notifications/, (req, res, ctx) => res(ctx.status(500)))
    );

    render(<NotificationsBell />);

    const bell = await screen.findByRole('button', { name: 'Notifications' });
    expect(bell).toBeInTheDocument();
  });
});
