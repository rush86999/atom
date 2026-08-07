/**
 * IntercomIntegration Component Tests
 *
 * Tests verify the real Intercom integration component
 * (components/IntercomIntegration.tsx):
 * - Connection status (GET /api/v1/intercom/health)
 * - Connect flow (modal -> handleConnect)
 * - Contacts, conversations, teams, admins, stats data loading
 * - Contact/conversation detail dialogs and the send-message flow
 * - Search and empty-data resilience
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts.
 */

import React from 'react';
import { renderWithProviders, screen, waitFor, within } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import IntercomIntegration from '../IntercomIntegration';

const stats = {
  total_contacts: 250,
  total_conversations: 90,
  open_conversations: 12,
  unassigned_conversations: 3,
  team_count: 4,
  admin_count: 6,
  response_time_avg: 2.5,
  satisfaction_rating: 4.7,
};

const contacts = [
  {
    id: 'c1',
    type: 'contact',
    email: 'sara@example.com',
    name: 'Sara Chen',
    phone: '+1 555 0100',
    role: 'admin',
    created_at: '2025-05-01T10:00:00Z',
    updated_at: '2026-01-01T10:00:00Z',
    last_seen_at: '2026-01-06T09:00:00Z',
    tags: ['vip', 'trial', 'north-america'],
    companies: [{ id: 'comp1', name: 'Acme Corp' }],
  },
];

const conversations = [
  {
    id: 'conv_1234567890',
    type: 'conversation',
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-01-02T10:00:00Z',
    source: {},
    contacts: [{ id: 'c1', type: 'contact' }],
    conversation_parts: [
      {
        id: 'p1',
        type: 'part',
        part_type: 'note',
        body: 'Customer needs help with billing',
        author: { id: 'c1', type: 'contact' },
        created_at: '2026-01-01T10:00:00Z',
      },
      {
        id: 'p2',
        type: 'part',
        part_type: 'note',
        body: 'Refund issued',
        author: { id: 'a1', type: 'admin' },
        created_at: '2026-01-01T11:00:00Z',
      },
    ],
    tags: ['billing'],
    assignee: { id: 'a1', type: 'admin' },
    open: true,
    read: false,
    priority: 'priority',
  },
];

const teams = [
  {
    id: 't1',
    type: 'team',
    name: 'Support Squad',
    admin_ids: ['a1', 'a2'],
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2025-01-01T10:00:00Z',
  },
];

const admins = [
  {
    id: 'a1',
    type: 'admin',
    name: 'Priya Patel',
    email: 'priya@example.com',
    job_title: 'Support Lead',
    away_mode_enabled: false,
    away_mode_reassign: false,
    has_inbox_seat: true,
    team_ids: ['t1'],
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2025-01-01T10:00:00Z',
  },
  {
    id: 'a2',
    type: 'admin',
    name: 'Tom Lee',
    email: 'tom@example.com',
    away_mode_enabled: true,
    away_mode_reassign: true,
    has_inbox_seat: false,
    team_ids: ['t1'],
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2025-01-01T10:00:00Z',
  },
];

const connectedHandlers = [
  rest.get('/api/v1/intercom/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, status: 'healthy' }));
  }),
  rest.get('/api/v1/intercom/contacts', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: contacts }));
  }),
  rest.get('/api/v1/intercom/conversations', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: conversations }));
  }),
  rest.get('/api/v1/intercom/teams', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: teams }));
  }),
  rest.get('/api/v1/intercom/admins', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: admins }));
  }),
  rest.get('/api/v1/intercom/stats', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: stats }));
  }),
];

const setDisconnected = (status = 503) => {
  server.use(
    rest.get('/api/v1/intercom/health', (req, res, ctx) => {
      return res(ctx.status(status), ctx.json({ error: 'not connected' }));
    })
  );
};

describe('IntercomIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
  });

  test('shows connect screen when not connected', async () => {
    setDisconnected();

    renderWithProviders(<IntercomIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /connect intercom/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: /connect intercom/i })
    ).toBeInTheDocument();
  });

  test('connects from the modal and loads the main UI with stats', async () => {
    const user = userEvent.setup();

    // Stateful health: disconnected at mount, healthy after connect reload
    let healthOk = false;
    server.use(
      rest.get('/api/v1/intercom/health', (req, res, ctx) => {
        return res(ctx.status(healthOk ? 200 : 503), ctx.json({ success: true }));
      }),
      rest.get('/api/v1/intercom/contacts', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: contacts }));
      }),
      rest.get('/api/v1/intercom/conversations', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: conversations }));
      }),
      rest.get('/api/v1/intercom/teams', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: teams }));
      }),
      rest.get('/api/v1/intercom/admins', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: admins }));
      }),
      rest.get('/api/v1/intercom/stats', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: stats }));
      })
    );

    renderWithProviders(<IntercomIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect intercom/i,
    });
    await user.click(connectButton);

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await waitFor(() => {
      expect(within(dialogContent).getByText('OAuth 2.0 Required')).toBeInTheDocument();
    });

    healthOk = true;
    await user.click(within(dialogContent).getByRole('button', { name: /^connect$/i }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Intercom' })).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('Total Contacts')).toBeInTheDocument();
    });
    expect(screen.getByText('250')).toBeInTheDocument();
    expect(screen.getByText('2.5h')).toBeInTheDocument();
    expect(screen.getByText('4.7/5')).toBeInTheDocument();
  });

  test('renders contacts and opens the contact detail modal', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<IntercomIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Intercom' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /contacts/i }));

    await waitFor(() => {
      expect(screen.getByText('Sara Chen')).toBeInTheDocument();
    });
    expect(screen.getByText('sara@example.com')).toBeInTheDocument();
    expect(screen.getByText('+1 555 0100')).toBeInTheDocument();
    // Only two of the three tags render, the rest collapses to "+1"
    expect(screen.getByText('vip')).toBeInTheDocument();
    expect(screen.getByText('trial')).toBeInTheDocument();
    expect(screen.getByText('+1')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^view$/i }));

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /contact details/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
  });

  test('sends a message to a contact through the message modal', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');

    server.use(
      ...connectedHandlers,
      rest.post('/api/v1/intercom/messages', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, message: {} }));
      })
    );

    renderWithProviders(<IntercomIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Intercom' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /contacts/i }));
    await waitFor(() => {
      expect(screen.getByText('Sara Chen')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /^message$/i }));

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(
      within(dialogContent).getByPlaceholderText(/type your message here/i),
      'Thanks for reaching out!'
    );
    expect(within(dialogContent).getByText(/To: Sara Chen/)).toBeInTheDocument();

    await user.click(within(dialogContent).getByRole('button', { name: /send message/i }));

    await waitFor(() => {
      expect(
        fetchSpy.mock.calls.some(
          ([url, init]) =>
            String(url).includes('/api/v1/intercom/messages') &&
            (init as RequestInit)?.method === 'POST' &&
            String((init as RequestInit)?.body).includes('Thanks for reaching out!') &&
            String((init as RequestInit)?.body).includes('c1')
        )
      ).toBe(true);
    });

    // Success closes the message modal
    await waitFor(() => {
      expect(
        screen.queryByRole('heading', { name: /send message/i })
      ).not.toBeInTheDocument();
    });
  });

  test('renders conversations and opens the detail modal with message parts', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<IntercomIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Intercom' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /conversations/i }));

    // Conversation id is truncated to the first 8 chars
    await waitFor(() => {
      expect(screen.getByText('conv_123...')).toBeInTheDocument();
    });
    expect(screen.getByText('Open')).toBeInTheDocument();
    expect(screen.getByText('Assigned')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^view$/i }));

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /conversation details/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByText('Customer needs help with billing')).toBeInTheDocument();
    expect(screen.getByText('Refund issued')).toBeInTheDocument();
    expect(screen.getByText('Agent')).toBeInTheDocument();
    expect(screen.getByText('Customer')).toBeInTheDocument();
  });

  test('renders teams and admins with availability states', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<IntercomIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Intercom' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /teams/i }));
    await waitFor(() => {
      expect(screen.getByText('Support Squad')).toBeInTheDocument();
    });
    expect(screen.getByText('2 admins')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /admins/i }));
    await waitFor(() => {
      expect(screen.getByText('Priya Patel')).toBeInTheDocument();
    });
    expect(screen.getByText('priya@example.com')).toBeInTheDocument();
    expect(screen.getByText('Support Lead')).toBeInTheDocument();
    expect(screen.getByText('Available')).toBeInTheDocument();
    expect(screen.getByText('Away')).toBeInTheDocument();
    expect(screen.getByText('Tom Lee')).toBeInTheDocument();
    expect(screen.getByText('tom@example.com')).toBeInTheDocument();
  });

  test('search posts the query to the search endpoint', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');

    server.use(
      ...connectedHandlers,
      rest.post('/api/v1/intercom/search', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({ success: true, data: { total_count: 2 } })
        );
      })
    );

    renderWithProviders(<IntercomIntegration />);

    const searchInput = await screen.findByPlaceholderText(
      /search contacts, conversations/i
    );
    await user.type(searchInput, 'sara{enter}');

    await waitFor(() => {
      expect(
        fetchSpy.mock.calls.some(
          ([url, init]) =>
            String(url).includes('/api/v1/intercom/search') &&
            (init as RequestInit)?.method === 'POST' &&
            String((init as RequestInit)?.body).includes('sara')
        )
      ).toBe(true);
    });
  });

  test('survives empty data responses without crashing', async () => {
    server.use(
      rest.get('/api/v1/intercom/health', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true }));
      }),
      rest.get('/api/v1/intercom/contacts', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/intercom/conversations', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/intercom/teams', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/intercom/admins', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/intercom/stats', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'boom' }));
      })
    );

    renderWithProviders(<IntercomIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Intercom' })).toBeInTheDocument();
    });
    expect(screen.queryByText('Total Contacts')).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /refresh data/i })
    ).toBeInTheDocument();
  });
});
