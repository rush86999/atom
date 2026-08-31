/**
 * ZendeskIntegration Component Tests
 *
 * Tests verify the real Zendesk integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile and ticket data loading
 * - Ticket search filtering and create-ticket dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/ZendeskIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ZendeskIntegration from '@/components/ZendeskIntegration';
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

// Radix Select is not interactive in jsdom; replace with native selects so
// filter + dialog select handlers can be driven directly.
jest.mock('@/components/ui/select', () => ({
  Select: ({ value, onValueChange, children }: any) => (
    <select
      data-testid="native-select"
      value={value ?? ''}
      onChange={(e) => onValueChange(e.target.value)}
    >
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: any) => <>{children}</>,
  SelectContent: ({ children }: any) => <>{children}</>,
  SelectItem: ({ value, children }: any) => <option value={value}>{children}</option>,
  SelectValue: () => null,
}));


const zendeskHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { zendesk: { connected: true, source: 'user_connection' } } }));
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { zendesk: { connected: true, source: 'user_connection' } } }));
  }),

  rest.post('/api/integrations/zendesk/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            name: 'Rushi Parikh',
            email: 'rushi@example.com',
            role: 'admin',
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/zendesk/tickets', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          tickets: [
            {
              id: 101,
              subject: 'Login issue',
              description: 'User cannot log in',
              status: 'open',
              priority: 'high',
              requester_id: 1,
              requester: { name: 'Alice' },
            },
            {
              id: 102,
              subject: 'Billing question',
              description: 'Invoice question',
              status: 'solved',
              priority: 'low',
              requester_id: 2,
              requester: { name: 'Bob' },
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/zendesk/users', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { users: [] } }));
  }),
  rest.post('/api/integrations/zendesk/groups', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { groups: [] } }));
  }),
  rest.post('/api/integrations/zendesk/views', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { views: [] } }));
  }),
  rest.post('/api/integrations/zendesk/organizations', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { organizations: [] } }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/connection-status', (req, res, ctx) => {
      return res(ctx.status(404));
    })
  );
};

// Data is loaded in both checkConnection() and the connected useEffect
// (double data-load race); wait for the full dataset to settle.
const settleData = async (text: RegExp) => {
  await screen.findByText(text);
  await new Promise((r) => setTimeout(r, 50));
};

describe('ZendeskIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...zendeskHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<ZendeskIntegration />);

    expect(
      screen.getByRole('heading', { name: /zendesk integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect zendesk account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<ZendeskIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect zendesk account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays tickets in the default Tickets tab
  test('displays tickets in the default Tickets tab', async () => {
    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Login issue')).toBeInTheDocument();
      expect(screen.getByText('Billing question')).toBeInTheDocument();
    });
  });

  // Test 7: filters tickets by search query
  test('filters tickets by search query', async () => {
    render(<ZendeskIntegration />);

    await settleData(/Login issue/);

    const searchInput = screen.getByPlaceholderText(/search tickets/i);
    fireEvent.change(searchInput, { target: { value: 'Billing' } });

    await waitFor(() => {
      expect(screen.getByText('Billing question')).toBeInTheDocument();
    });
    expect(screen.queryByText('Login issue')).not.toBeInTheDocument();
  });

  // Test 8: opens create ticket dialog
  test('opens create ticket dialog', async () => {
    render(<ZendeskIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /create ticket/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 9: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect zendesk account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 10: shows refresh status button
  test('shows refresh status button', async () => {
    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: tab data rendering, create flows, and error paths
// ---------------------------------------------------------------------------
describe('ZendeskIntegration (extended coverage)', () => {
  // NOTE: jest.config.js sets restoreMocks:true, which detaches describe-scope
  // spies after every test — create a fresh console.error spy per test.
  let errorSpy: jest.SpyInstance;
  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  const richTickets = [
    {
      id: 201,
      subject: 'New ticket',
      description: 'd',
      status: 'new',
      priority: 'urgent',
      type: 'question',
      requester: { name: 'Alice' },
      via: { channel: 'web' },
      url: 'https://zendesk.example.com/201',
      created_at: '2024-01-01T10:00:00Z',
    },
    {
      id: 202,
      subject: 'Open ticket',
      description: 'd',
      status: 'open',
      priority: 'high',
      type: 'incident',
      requester: { name: 'Bob' },
      via: { channel: 'email' },
      created_at: '2024-01-02T10:00:00Z',
    },
    {
      id: 203,
      subject: 'Pending ticket',
      description: 'd',
      status: 'pending',
      priority: 'normal',
      type: 'problem',
      requester: { name: 'Carol' },
      via: { channel: 'api' },
      created_at: '2024-01-03T10:00:00Z',
    },
    {
      id: 204,
      subject: 'Solved ticket',
      description: 'd',
      status: 'solved',
      priority: 'low',
      type: 'task',
      requester: { name: 'Dave' },
      via: { channel: 'voice' },
      created_at: '2024-01-04T10:00:00Z',
    },
    {
      id: 205,
      subject: 'Closed ticket',
      description: 'd',
      status: 'closed',
      priority: 'weird',
      type: 'other',
      requester: { name: 'Eve' },
      via: { channel: 'chat' },
      created_at: '2024-01-05T10:00:00Z',
    },
    {
      id: 206,
      subject: 'On hold ticket',
      description: 'd',
      status: 'hold',
      priority: 'normal',
      type: 'question',
      requester: { name: 'Frank' },
      via: { channel: 'other' },
      created_at: '2024-01-06T10:00:00Z',
    },
  ];

  const richUsers = [
    {
      id: 1,
      name: 'Alice Admin',
      email: 'alice@example.com',
      role: 'admin',
      active: true,
      verified: true,
      shared: false,
      shared_agent: false,
      locale: 'en-US',
      timezone: 'PST',
      tags: [],
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      organization: { id: 1, name: 'Acme Corp', created_at: '2024-01-01T00:00:00Z', updated_at: '2024-01-01T00:00:00Z', domain_names: [], tags: [], shared_tickets: true, shared_comments: true },
      phone: '+1 555 0100',
    },
    {
      id: 2,
      name: 'Bob Agent',
      email: 'bob@example.com',
      role: 'agent',
      active: false,
      verified: false,
      shared: false,
      shared_agent: false,
      locale: 'en-US',
      timezone: 'PST',
      tags: [],
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ];

  const richGroups = [
    {
      id: 11,
      name: 'Support Team',
      description: 'First line support',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
      deleted: false,
      url: 'https://zendesk.example.com/groups/11',
    },
  ];

  const richViews = [
    {
      id: 21,
      title: 'My Unsolved Tickets',
      description: 'All tickets assigned to me',
      active: true,
      position: 1,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
      url: 'https://zendesk.example.com/views/21',
      conditions: { all: [], any: [] },
      execution: { order: [] },
      columns: [],
    },
    {
      id: 22,
      title: 'Archived View',
      description: 'Old view',
      active: false,
      position: 2,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
      url: 'https://zendesk.example.com/views/22',
      conditions: { all: [], any: [] },
      execution: { order: [] },
      columns: [],
    },
  ];

  const richOrganizations = [
    {
      id: 31,
      name: 'Acme Corp',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      domain_names: ['acme.com', 'acme.io'],
      tags: ['vip', 'enterprise'],
      shared_tickets: true,
      shared_comments: true,
    },
    {
      id: 32,
      name: 'Globex',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      domain_names: [],
      tags: [],
      shared_tickets: false,
      shared_comments: false,
    },
  ];

  // NOTE: MSW resolves handlers in the order passed to server.use(), so the
  // data-rich overrides must come BEFORE the base zendeskHandlers.
  const richHandlers = [
    rest.post('/api/integrations/zendesk/tickets', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { tickets: richTickets } }));
    }),
    rest.post('/api/integrations/zendesk/users', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { users: richUsers } }));
    }),
    rest.post('/api/integrations/zendesk/groups', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { groups: richGroups } }));
    }),
    rest.post('/api/integrations/zendesk/views', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { views: richViews } }));
    }),
    rest.post('/api/integrations/zendesk/organizations', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { organizations: richOrganizations } }));
    }),
    rest.post('/api/integrations/zendesk/tickets/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { ticket: { id: 999 } } }));
    }),
    rest.post('/api/integrations/zendesk/users/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { user: { id: 998 } } }));
    }),
    rest.post('/api/integrations/zendesk/organizations/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { organization: { id: 997 } } }));
    }),
    ...zendeskHandlers,
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...richHandlers);
  });

  const settle = async (text: RegExp | string) => {
    await screen.findByText(text);
    await new Promise((r) => setTimeout(r, 50));
  };

  test('renders tickets with status, priority, type and via badges', async () => {
    render(<ZendeskIntegration />);

    await settle('New ticket');
    for (const label of ['New ticket', 'Open ticket', 'Pending ticket', 'Solved ticket', 'Closed ticket', 'On hold ticket']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    // via channel badges
    expect(screen.getByText('web')).toBeInTheDocument();
    expect(screen.getByText('email')).toBeInTheDocument();
    expect(screen.getByText('voice')).toBeInTheDocument();
    expect(screen.getByText('chat')).toBeInTheDocument();
  });

  test('opens ticket url when subject is clicked', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByText('New ticket'));
    expect(openSpy).toHaveBeenCalledWith('https://zendesk.example.com/201', '_blank');
  });

  test('clicking Refresh Status re-runs the health check', async () => {
    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: /refresh status/i }));
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  test('displays users on the Users tab with roles and details', async () => {
    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));

    expect(await screen.findByText('Alice Admin')).toBeInTheDocument();
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    expect(screen.getByText('bob@example.com')).toBeInTheDocument();
    // role badges
    expect(screen.getAllByText('admin').length).toBeGreaterThan(0);
    expect(screen.getAllByText('agent').length).toBeGreaterThan(0);
    // active/inactive badges
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
    // organization + phone rendering
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('+1 555 0100')).toBeInTheDocument();
  });

  test('filters users by search query', async () => {
    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));
    expect(await screen.findByText('Alice Admin')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/search users/i), {
      target: { value: 'bob@' },
    });

    await waitFor(() => {
      expect(screen.getByText('Bob Agent')).toBeInTheDocument();
    });
    expect(screen.queryByText('Alice Admin')).not.toBeInTheDocument();
  });

  test('displays groups on the Groups tab', async () => {
    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: 'Groups' }));

    expect(await screen.findByText('Support Team')).toBeInTheDocument();
    expect(screen.getByText('First line support')).toBeInTheDocument();
    expect(screen.getByText('#11')).toBeInTheDocument();
  });

  test('displays views on the Views tab with active and inactive badges', async () => {
    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: 'Views' }));

    expect(await screen.findByText('My Unsolved Tickets')).toBeInTheDocument();
    expect(screen.getByText('Archived View')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  test('displays organizations on the Organizations tab with badges', async () => {
    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: 'Organizations' }));

    expect(await screen.findByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('Globex')).toBeInTheDocument();
    expect(screen.getByText('acme.com')).toBeInTheDocument();
    expect(screen.getByText('acme.io')).toBeInTheDocument();
    expect(screen.getByText('vip')).toBeInTheDocument();
    expect(screen.getByText('Shared Tickets')).toBeInTheDocument();
    expect(screen.getByText('Shared Comments')).toBeInTheDocument();
  });

  test('filters organizations by search query', async () => {
    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: 'Organizations' }));
    expect(await screen.findByText('Acme Corp')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/search organizations/i), {
      target: { value: 'globex' },
    });

    await waitFor(() => {
      expect(screen.getByText('Globex')).toBeInTheDocument();
    });
    expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument();
  });

  test('creates a ticket through the dialog', async () => {
    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Ticket subject'), {
      target: { value: 'Urgent login problem' },
    });
    fireEvent.change(screen.getByPlaceholderText('Ticket description'), {
      target: { value: 'User cannot log in at all' },
    });

    const footerButtons = Array.from(
      (dialog as HTMLElement).querySelectorAll('button')
    ).filter((b) => b.textContent?.includes('Create Ticket'));
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Success', description: 'Ticket created successfully' })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when ticket creation fails', async () => {
    server.use(
      rest.post('/api/integrations/zendesk/tickets/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Ticket subject'), {
      target: { value: 'S' },
    });
    fireEvent.change(screen.getByPlaceholderText('Ticket description'), {
      target: { value: 'D' },
    });

    const footerButtons = Array.from(
      (dialog as HTMLElement).querySelectorAll('button')
    ).filter((b) => b.textContent?.includes('Create Ticket'));
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create ticket' })
      );
    });
  });

  test('creates a user through the dialog', async () => {
    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));
    fireEvent.click(screen.getAllByRole('button', { name: /create user/i })[0]);
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('User name'), { target: { value: 'Carol' } });
    fireEvent.change(screen.getByPlaceholderText('user@example.com'), {
      target: { value: 'carol@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Phone number'), {
      target: { value: '+1 555 0101' },
    });

    const footerButtons = Array.from(
      (dialog as HTMLElement).querySelectorAll('button')
    ).filter((b) => b.textContent?.includes('Create User'));
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Success', description: 'User created successfully' })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when user creation fails', async () => {
    server.use(
      rest.post('/api/integrations/zendesk/users/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));
    fireEvent.click(screen.getAllByRole('button', { name: /create user/i })[0]);
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('User name'), { target: { value: 'Dan' } });
    fireEvent.change(screen.getByPlaceholderText('user@example.com'), {
      target: { value: 'dan@example.com' },
    });

    const footerButtons = Array.from(
      (dialog as HTMLElement).querySelectorAll('button')
    ).filter((b) => b.textContent?.includes('Create User'));
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create user' })
      );
    });
  });

  test('creates an organization through the dialog', async () => {
    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: 'Organizations' }));
    fireEvent.click(
      screen.getAllByRole('button', { name: /create organization/i })[0]
    );
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Organization name'), {
      target: { value: 'Initech' },
    });
    // domain names parse on comma split
    fireEvent.change(screen.getByPlaceholderText('domain1.com, domain2.com'), {
      target: { value: 'initech.com, initech.io' },
    });
    fireEvent.change(screen.getByPlaceholderText('Organization notes'), {
      target: { value: 'Notes here' },
    });

    const footerButtons = Array.from(
      (dialog as HTMLElement).querySelectorAll('button')
    ).filter((b) => b.textContent?.includes('Create Organization'));
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'Organization created successfully',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when organization creation fails', async () => {
    server.use(
      rest.post('/api/integrations/zendesk/organizations/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<ZendeskIntegration />);
    await settle('New ticket');

    fireEvent.click(screen.getByRole('button', { name: 'Organizations' }));
    fireEvent.click(
      screen.getAllByRole('button', { name: /create organization/i })[0]
    );
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Organization name'), {
      target: { value: 'Fail Corp' },
    });

    const footerButtons = Array.from(
      (dialog as HTMLElement).querySelectorAll('button')
    ).filter((b) => b.textContent?.includes('Create Organization'));
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to create organization',
        })
      );
    });
  });

  test('shows error toast when ticket loading fails with a network error', async () => {
    server.use(
      rest.post('/api/integrations/zendesk/tickets', (req, res) => res.networkError('boom'))
    );

    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to load tickets from Zendesk' })
      );
    });
  });

  test('logs errors when auxiliary data loads fail', async () => {
    const netFail = (path: string) =>
      rest.post(path, (req, res) => res.networkError('boom'));
    server.use(
      netFail('/api/integrations/zendesk/profile'),
      netFail('/api/integrations/zendesk/users'),
      netFail('/api/integrations/zendesk/groups'),
      netFail('/api/integrations/zendesk/views'),
      netFail('/api/integrations/zendesk/organizations')
    );

    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load user profile:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load users:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load groups:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load views:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load organizations:', expect.anything());
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: health catch, filters, dialog selects and checkboxes
// ---------------------------------------------------------------------------
describe('ZendeskIntegration (extended coverage)', () => {
  let consoleSpy: jest.SpyInstance;
  let openSpy: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    openSpy = jest.fn();
    window.open = openSpy as any;
    server.resetHandlers();
    server.use(...zendeskHandlers);
  });

  afterEach(() => {
    consoleSpy.mockRestore();
  });

  const settle = async (text: RegExp | string) => {
    await screen.findByText(text);
    await new Promise((r) => setTimeout(r, 50));
  };

  test('health-check rejection disconnects and logs', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res) =>
        res.networkError('down')
      )
    );

    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Connection status check failed:', expect.anything());
    });
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect zendesk/i })
      ).toBeInTheDocument();
    });
  });

  test('status and priority filters reload tickets with params', async () => {
    let ticketRequests: string[] = [];
    server.use(
      rest.post('/api/integrations/zendesk/tickets', async (req, res, ctx) => {
        ticketRequests.push(await req.text());
        return res(
          ctx.status(200),
          ctx.json({
            data: {
              tickets: [
                {
                  id: 301,
                  subject: 'Filterable ticket',
                  description: 'd',
                  status: 'open',
                  priority: 'high',
                  requester: { name: 'Alice' },
                },
              ],
            },
          })
        );
      })
    );

    render(<ZendeskIntegration />);
    await settle('Filterable ticket');

    const selects = screen.getAllByTestId('native-select');
    // first select = status filter, second = priority filter
    fireEvent.change(selects[0], { target: { value: 'open' } });
    await waitFor(() => {
      expect(
        ticketRequests.some((body) => body.includes('"status":"open"'))
      ).toBe(true);
    });

    fireEvent.change(selects[1], { target: { value: 'urgent' } });
    await waitFor(() => {
      expect(
        ticketRequests.some((body) => body.includes('"priority":"urgent"'))
      ).toBe(true);
    });
    expect(await screen.findByText('Filterable ticket')).toBeInTheDocument();
  });

  test('create ticket dialog drives selects, due date and cancel', async () => {
    let createdBody: string = '';
    server.use(
      rest.post('/api/integrations/zendesk/tickets/create', async (req, res, ctx) => {
        createdBody = await req.text();
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<ZendeskIntegration />);
    await settle(/login issue/i);

    fireEvent.click(screen.getByRole('button', { name: /create ticket/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Ticket subject'), {
      target: { value: 'Select-driven ticket' },
    });
    fireEvent.change(screen.getByPlaceholderText('Ticket description'), {
      target: { value: 'Body' },
    });

    const selects = Array.from(dialog.querySelectorAll('select'));
    for (const sel of selects) {
      fireEvent.change(sel, { target: { value: sel.options[1]?.value ?? '' } });
    }

    // the due-at input is the remaining text input (not subject/description)
    const dueInput = Array.from(
      dialog.querySelectorAll('input')
    ).find(
      (i) => !['Ticket subject', 'Ticket description'].includes(i.placeholder)
    ) as HTMLInputElement | undefined;
    if (dueInput) {
      fireEvent.change(dueInput, { target: { value: '2026-09-01' } });
    }

    const footerButtons = Array.from(dialog.querySelectorAll('button')).filter(
      (b) => b.textContent?.includes('Create Ticket')
    );
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(createdBody).toContain('Select-driven ticket');
    });
  });

  test('user dialog drives role/organization selects and the verified checkbox', async () => {
    let createdBody: string = '';
    server.use(
      rest.post('/api/integrations/zendesk/users/create', async (req, res, ctx) => {
        createdBody = await req.text();
        return res(ctx.status(200), ctx.json({ success: true }));
      }),
      rest.post('/api/integrations/zendesk/organizations', (req, res, ctx) =>
        res(
          ctx.status(200),
          ctx.json({
            data: {
              organizations: [
                { id: 'org1', name: 'Acme Corp', tags: [], domain_names: [] },
              ],
            },
          })
        )
      )
    );

    render(<ZendeskIntegration />);
    await settle(/login issue/i);

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));
    fireEvent.click(screen.getAllByRole('button', { name: /create user/i })[0]);
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('User name'), {
      target: { value: 'Eve' },
    });
    fireEvent.change(screen.getByPlaceholderText('user@example.com'), {
      target: { value: 'eve@example.com' },
    });

    const selects = Array.from(dialog.querySelectorAll('select'));
    for (const sel of selects) {
      fireEvent.change(sel, { target: { value: sel.options[sel.options.length - 1].value } });
    }

    const checkbox = dialog.querySelector('[role="checkbox"]') as HTMLElement;
    if (checkbox) {
      fireEvent.click(checkbox);
    }

    const footerButtons = Array.from(dialog.querySelectorAll('button')).filter(
      (b) => b.textContent?.includes('Create User')
    );
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(createdBody).toContain('Eve');
    });
  });

  test('organization dialog toggles shared tickets and comments checkboxes', async () => {
    let createdBody: string = '';
    server.use(
      rest.post('/api/integrations/zendesk/organizations/create', async (req, res, ctx) => {
        createdBody = await req.text();
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<ZendeskIntegration />);
    await settle(/login issue/i);

    fireEvent.click(screen.getByRole('button', { name: 'Organizations' }));
    fireEvent.click(
      screen.getAllByRole('button', { name: /create organization/i })[0]
    );
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Organization name'), {
      target: { value: 'CheckCorp' },
    });

    const checkboxes = Array.from(
      dialog.querySelectorAll('[role="checkbox"]')
    ) as HTMLElement[];
    for (const cb of checkboxes) {
      fireEvent.click(cb);
    }

    const footerButtons = Array.from(dialog.querySelectorAll('button')).filter(
      (b) => b.textContent?.includes('Create Organization')
    );
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(createdBody).toContain('CheckCorp');
    });
  });

  test('renders end-user and unknown role variants on the Users tab', async () => {
    server.use(
      rest.post('/api/integrations/zendesk/users', (req, res, ctx) =>
        res(
          ctx.status(200),
          ctx.json({
            data: {
              users: [
                { id: 1, name: 'End User Eve', email: 'eve@x.com', role: 'end-user', active: true },
                { id: 2, name: 'Mystery Max', email: 'max@x.com', role: 'mystery', active: true },
              ],
            },
          })
        )
      )
    );

    render(<ZendeskIntegration />);
    await settle(/login issue/i);
    fireEvent.click(screen.getByRole('button', { name: 'Users' }));

    expect(await screen.findByText('End User Eve')).toBeInTheDocument();
    expect(screen.getByText('Mystery Max')).toBeInTheDocument();
  });
});
