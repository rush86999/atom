/**
 * FreshdeskIntegration Component Tests
 *
 * Tests verify the real Freshdesk integration component
 * (components/FreshdeskIntegration.tsx):
 * - Connection status (GET /api/v1/freshdesk/health)
 * - API-key connect flow (POST /api/v1/freshdesk/auth)
 * - Tickets, contacts, companies, agents, groups, stats data loading
 * - Ticket/contact detail dialogs, search, and empty-data resilience
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts.
 */

import React from 'react';
import { renderWithProviders, screen, waitFor, within } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import FreshdeskIntegration from '../FreshdeskIntegration';

const stats = {
  total_tickets: 42,
  open_tickets: 7,
  pending_tickets: 3,
  resolved_tickets: 28,
  closed_tickets: 4,
  total_contacts: 120,
  total_companies: 6,
  total_agents: 5,
  total_groups: 2,
  avg_first_response_time: 4.5,
  avg_resolution_time: 12.2,
  satisfaction_rating: 4.8,
};

const tickets = [
  {
    id: 1001,
    subject: 'Cannot log into dashboard',
    description: 'User reports 401 when logging in',
    email: 'user@example.com',
    priority: 4,
    status: 2,
    source: 2,
    type: 'Incident',
    created_at: '2026-01-10T10:00:00Z',
    updated_at: '2026-01-10T11:00:00Z',
    is_escalated: true,
    tags: ['login', 'urgent'],
  },
  {
    id: 1002,
    subject: 'Billing question',
    description: 'Invoice mismatch on plan renewal',
    email: 'billing@example.com',
    priority: 2,
    status: 5,
    source: 2,
    created_at: '2026-01-11T10:00:00Z',
    updated_at: '2026-01-11T11:00:00Z',
    is_escalated: false,
    tags: [],
  },
];

const contacts = [
  {
    id: 1,
    name: 'Jane Cooper',
    email: 'jane@example.com',
    phone: '+1 555 0100',
    mobile: '+1 555 0101',
    company_id: 3,
    job_title: 'CTO',
    time_zone: 'America/New_York',
    language: 'en',
    created_at: '2025-06-01T10:00:00Z',
    updated_at: '2025-06-01T10:00:00Z',
    last_login_at: '2026-01-05T09:00:00Z',
    active: true,
  },
];

const companies = [
  {
    id: 3,
    name: 'Acme Corp',
    description: 'Enterprise software vendor',
    domains: ['acme.com'],
    industry: 'Software',
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2025-01-01T10:00:00Z',
  },
];

const agents = [
  {
    id: 11,
    email: 'support@example.com',
    name: 'Alice Agent',
    available: true,
    occasional: false,
    ticket_scope: 1,
    group_ids: [1, 2],
    role_ids: [1],
    created_at: '2025-03-01T10:00:00Z',
    updated_at: '2025-03-01T10:00:00Z',
  },
];

const groups = [
  {
    id: 1,
    name: 'Support Tier 1',
    description: 'First line support',
    escalated: true,
    agent_ids: [11],
    created_at: '2025-03-01T10:00:00Z',
    updated_at: '2025-03-01T10:00:00Z',
  },
];

const connectedHandlers = [
  rest.get('/api/v1/freshdesk/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, status: 'healthy' }));
  }),
  rest.get('/api/v1/freshdesk/contacts', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: contacts }));
  }),
  rest.get('/api/v1/freshdesk/tickets', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: tickets }));
  }),
  rest.get('/api/v1/freshdesk/companies', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: companies }));
  }),
  rest.get('/api/v1/freshdesk/agents', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: agents }));
  }),
  rest.get('/api/v1/freshdesk/groups', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: groups }));
  }),
  rest.get('/api/v1/freshdesk/stats', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: stats }));
  }),
];

const setDisconnected = (status = 503) => {
  server.use(
    rest.get('/api/v1/freshdesk/health', (req, res, ctx) => {
      return res(ctx.status(status), ctx.json({ error: 'not connected' }));
    })
  );
};

describe('FreshdeskIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
  });

  test('shows connect screen when not connected', async () => {
    setDisconnected();

    renderWithProviders(<FreshdeskIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /connect freshdesk/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: /connect freshdesk/i })
    ).toBeInTheDocument();
  });

  test('connect requires domain and API key before hitting the backend', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');

    setDisconnected();

    renderWithProviders(<FreshdeskIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect freshdesk/i,
    });
    await user.click(connectButton);

    // Dialog opens with empty credentials; clicking Connect must not fire
    // the auth request (component shows a missing-credentials toast instead)
    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await waitFor(() => {
      expect(within(dialogContent).getByText('Connect Freshdesk')).toBeInTheDocument();
    });
    await user.click(within(dialogContent).getByRole('button', { name: /^connect$/i }));

    await new Promise((r) => setTimeout(r, 50));
    expect(
      fetchSpy.mock.calls.some(([url]) => String(url).includes('/api/v1/freshdesk/auth'))
    ).toBe(false);
    // Dialog stays open (missing-credentials toast, no state change)
    expect(
      within(dialogContent).getByPlaceholderText('your-domain')
    ).toBeInTheDocument();
  });

  test('connects with API key and domain and loads the dashboard', async () => {
    const user = userEvent.setup();

    // Stateful health: disconnected at mount, healthy after the OAuth-style
    // connect reload (handleConnect -> loadFreshdeskData re-checks health)
    let healthOk = false;
    server.use(
      rest.get('/api/v1/freshdesk/health', (req, res, ctx) => {
        return res(ctx.status(healthOk ? 200 : 503), ctx.json({ success: true }));
      }),
      rest.get('/api/v1/freshdesk/contacts', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: contacts }));
      }),
      rest.get('/api/v1/freshdesk/tickets', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: tickets }));
      }),
      rest.get('/api/v1/freshdesk/companies', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: companies }));
      }),
      rest.get('/api/v1/freshdesk/agents', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: agents }));
      }),
      rest.get('/api/v1/freshdesk/groups', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: groups }));
      }),
      rest.get('/api/v1/freshdesk/stats', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: stats }));
      }),
      rest.post('/api/v1/freshdesk/auth', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    renderWithProviders(<FreshdeskIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect freshdesk/i,
    });
    await user.click(connectButton);

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(within(dialogContent).getByPlaceholderText('your-domain'), 'acme');
    await user.type(
      within(dialogContent).getByPlaceholderText(/enter your api key/i),
      'abc123'
    );
    // The connect reload now sees a healthy backend
    healthOk = true;
    await user.click(within(dialogContent).getByRole('button', { name: /^connect$/i }));

    // Connected main UI with dashboard stats
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Freshdesk' })
      ).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('Total Tickets')).toBeInTheDocument();
    });
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('4.5h')).toBeInTheDocument();
    expect(screen.getByText('4.8/5')).toBeInTheDocument();
  });

  test('reports connection failure and stays on the connect screen', async () => {
    const user = userEvent.setup();
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    server.use(
      rest.get('/api/v1/freshdesk/health', (req, res, ctx) => {
        return res(ctx.status(503), ctx.json({ error: 'not connected' }));
      }),
      rest.post('/api/v1/freshdesk/auth', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'bad credentials' }));
      })
    );

    renderWithProviders(<FreshdeskIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect freshdesk/i,
    });
    await user.click(connectButton);

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(within(dialogContent).getByPlaceholderText('your-domain'), 'acme');
    await user.type(
      within(dialogContent).getByPlaceholderText(/enter your api key/i),
      'bad-key'
    );
    await user.click(within(dialogContent).getByRole('button', { name: /^connect$/i }));

    // Auth 500 -> the component shows a toast and stays on the connect
    // screen with the dialog open (no crash, no state flip)
    await waitFor(() => {
      expect(
        within(dialogContent).getByPlaceholderText('your-domain')
      ).toBeInTheDocument();
    });
    expect(
      screen.getAllByRole('heading', { name: /connect freshdesk/i }).length
    ).toBeGreaterThan(0);
    expect(consoleErrorSpy).not.toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });

  test('renders tickets with status and priority badges', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<FreshdeskIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Freshdesk' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /tickets/i }));

    await waitFor(() => {
      expect(screen.getByText('Cannot log into dashboard')).toBeInTheDocument();
    });
    expect(screen.getByText('#1001')).toBeInTheDocument();
    expect(screen.getByText('#1002')).toBeInTheDocument();
    // status 2 -> "Open", priority 4 -> "Urgent"
    expect(screen.getByText('Open')).toBeInTheDocument();
    expect(screen.getByText('Urgent')).toBeInTheDocument();
    expect(screen.getByText('Closed')).toBeInTheDocument();
    // type column: missing type falls back to "General"
    expect(screen.getByText('General')).toBeInTheDocument();
  });

  test('opens ticket details with description and tags', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<FreshdeskIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Freshdesk' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /tickets/i }));
    await waitFor(() => {
      expect(screen.getByText('Cannot log into dashboard')).toBeInTheDocument();
    });

    // Eye button for the escalated ticket row
    const eyeButtons = screen.getAllByRole('button');
    const viewButton = eyeButtons.find((b) => b.querySelector('svg.lucide-eye')) as HTMLElement;
    await user.click(viewButton);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /ticket details/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText('User reports 401 when logging in')
    ).toBeInTheDocument();
    expect(screen.getByText('login')).toBeInTheDocument();
    expect(screen.getByText('urgent')).toBeInTheDocument();
    // Escalated alert
    expect(screen.getByText('This ticket has been escalated')).toBeInTheDocument();
  });

  test('renders contacts with status and opens the contact modal', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<FreshdeskIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Freshdesk' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /contacts/i }));

    await waitFor(() => {
      expect(screen.getByText('Jane Cooper')).toBeInTheDocument();
    });
    expect(screen.getByText('jane@example.com')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Company 3')).toBeInTheDocument();

    const viewButton = screen
      .getAllByRole('button')
      .find((b) => b.querySelector('svg.lucide-eye')) as HTMLElement;
    await user.click(viewButton);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /contact details/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByText('CTO')).toBeInTheDocument();
    expect(screen.getByText('America/New_York')).toBeInTheDocument();
  });

  test('renders companies with domains and industry', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<FreshdeskIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Freshdesk' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /companies/i }));

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });
    expect(screen.getByText(/acme\.com/)).toBeInTheDocument();
    expect(screen.getByText('Software')).toBeInTheDocument();
    expect(screen.getByText('Enterprise software vendor')).toBeInTheDocument();
  });

  test('renders agents and groups', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<FreshdeskIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Freshdesk' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /agents/i }));
    await waitFor(() => {
      expect(screen.getByText('Alice Agent')).toBeInTheDocument();
    });
    expect(screen.getByText('support@example.com')).toBeInTheDocument();
    expect(screen.getByText('Available')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /groups/i }));
    await waitFor(() => {
      expect(screen.getByText('Support Tier 1')).toBeInTheDocument();
    });
    expect(screen.getByText('Escalated')).toBeInTheDocument();
    expect(screen.getByText('First line support')).toBeInTheDocument();
  });

  test('search posts the query to the search endpoint', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');

    server.use(
      ...connectedHandlers,
      rest.post('/api/v1/freshdesk/search', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({ success: true, data: { total_count: 3 } })
        );
      })
    );

    renderWithProviders(<FreshdeskIntegration />);

    const searchInput = await screen.findByPlaceholderText(/search tickets, contacts/i);
    await user.type(searchInput, 'dashboard{enter}');

    await waitFor(() => {
      expect(
        fetchSpy.mock.calls.some(
          ([url, init]) =>
            String(url).includes('/api/v1/freshdesk/search') &&
            (init as RequestInit)?.method === 'POST' &&
            String((init as RequestInit)?.body).includes('dashboard')
        )
      ).toBe(true);
    });
  });

  test('survives empty data responses without crashing', async () => {
    server.use(
      rest.get('/api/v1/freshdesk/health', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true }));
      }),
      rest.get('/api/v1/freshdesk/contacts', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/freshdesk/tickets', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/freshdesk/companies', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/freshdesk/agents', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/freshdesk/groups', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      // Stats omitted entirely
      rest.get('/api/v1/freshdesk/stats', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'boom' }));
      })
    );

    renderWithProviders(<FreshdeskIntegration />);

    // Main UI renders with zero rows and no stats cards
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Freshdesk' })).toBeInTheDocument();
    });
    expect(screen.queryByText('Total Tickets')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /refresh data/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: error paths, status/priority variants, modal close,
// create-ticket modal
// ---------------------------------------------------------------------------
describe('FreshdeskIntegration (extended coverage)', () => {
  let consoleSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    server.resetHandlers();
    server.use(...connectedHandlers);
  });

  afterEach(() => {
    consoleSpy.mockRestore();
  });

  const connected = async () => {
    renderWithProviders(<FreshdeskIntegration />);
    await screen.findByRole('heading', { name: /freshdesk/i });
  };

  test('a failed data load disconnects the integration', async () => {
    server.use(
      rest.get('/api/v1/freshdesk/health', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, status: 'healthy' }))
      ),
      rest.get('/api/v1/freshdesk/tickets', (req, res) => res.networkError('down'))
    );

    renderWithProviders(<FreshdeskIntegration />);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to load Freshdesk data:',
        expect.anything()
      );
    });
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /connect freshdesk/i })
      ).toBeInTheDocument();
    });
  });

  test('search failures are logged without crashing', async () => {
    const user = userEvent.setup();
    server.use(
      rest.post('/api/v1/freshdesk/search', (req, res) => res.networkError('down'))
    );

    await connected();

    const searchInput = await screen.findByPlaceholderText(/search/i);
    await user.type(searchInput, 'boom{enter}');

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Search failed:', expect.anything());
    });
  });

  test('renders every ticket status and priority variant', async () => {
    const variantTickets = [
      { status: 2, priority: 1, id: 1, subject: 'S2 P1' },
      { status: 3, priority: 2, id: 2, subject: 'S3 P2' },
      { status: 4, priority: 3, id: 3, subject: 'S4 P3' },
      { status: 5, priority: 4, id: 4, subject: 'S5 P4' },
      { status: 9, priority: 9, id: 5, subject: 'S9 P9' },
    ].map((t) => ({ ...tickets[0], ...t, tags: [] }));

    server.use(
      rest.get('/api/v1/freshdesk/tickets', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, data: variantTickets }))
      )
    );

    await connected();
    const user0 = userEvent.setup();
    await user0.click(screen.getByRole('button', { name: /tickets/i }));
    await screen.findByText('S2 P1');

    for (const text of ['Open', 'Pending', 'Resolved', 'Closed', 'Unknown']) {
      expect(screen.getAllByText(text).length).toBeGreaterThan(0);
    }
    for (const text of ['Low', 'Medium', 'High', 'Urgent']) {
      expect(screen.getAllByText(text).length).toBeGreaterThan(0);
    }
    // status 9 and priority 9 both fall back to Unknown
    expect(screen.getAllByText('Unknown').length).toBeGreaterThan(1);
  });

  test('connect modal cancel closes the dialog', async () => {
    const user = userEvent.setup();
    server.use(
      rest.get('/api/v1/freshdesk/health', (req, res, ctx) =>
        res(ctx.status(503), ctx.json({ error: 'nope' }))
      )
    );

    renderWithProviders(<FreshdeskIntegration />);
    await user.click(
      await screen.findByRole('button', { name: /connect freshdesk/i })
    );
    await screen.findByText(/api key authentication/i);
    await user.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByText(/api key authentication/i)).not.toBeInTheDocument();
    });
  });

  test('opens the create ticket modal and cancels it', async () => {
    const user = userEvent.setup();

    await connected();
    await user.click(screen.getByRole('button', { name: /tickets/i }));
    await screen.findByText('Cannot log into dashboard');

    await user.click(screen.getByRole('button', { name: /create ticket/i }));
    await waitFor(() => {
      expect(screen.getAllByText('Create Ticket').length).toBeGreaterThan(1);
    });
    const cancel = screen
      .getAllByRole('button')
      .find((b) => b.textContent === 'Cancel');
    if (cancel) {
      await user.click(cancel);
    }
  });

  test('closes the ticket details modal via the Close button', async () => {
    const user = userEvent.setup();

    await connected();
    await user.click(screen.getByRole('button', { name: /tickets/i }));
    await screen.findByText('Cannot log into dashboard');

    const eyeButton = screen
      .getAllByRole('button')
      .find((b) => b.querySelector('svg.lucide-eye')) as HTMLElement;
    await user.click(eyeButton);
    await screen.findByRole('heading', { name: /ticket details/i });
    await user.click(screen.getByRole('button', { name: /close/i }));
    await waitFor(() => {
      expect(
        screen.queryByRole('heading', { name: /ticket details/i })
      ).not.toBeInTheDocument();
    });
  });
});
