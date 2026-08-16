/**
 * MailchimpIntegration Component Tests
 *
 * Tests verify the real Mailchimp integration component
 * (components/MailchimpIntegration.tsx):
 * - Connection status (GET /api/v1/mailchimp/health)
 * - API-key connect flow (POST /api/v1/mailchimp/auth)
 * - Audiences, campaigns, automations, templates, contacts, stats loading
 * - Audience/campaign/contact detail dialogs, load-contacts, and search
 * - Empty-data resilience
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts.
 */

import React from 'react';
import { renderWithProviders, screen, waitFor, within } from '../../tests/test-utils';
import { cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import MailchimpIntegration from '../MailchimpIntegration';

const stats = {
  total_audiences: 2,
  total_contacts: 1234,
  total_campaigns: 5,
  total_automations: 2,
  active_campaigns: 1,
  open_rate: 0.42,
  click_rate: 0.18,
  bounce_rate: 0.02,
  unsubscribe_rate: 0.01,
  revenue: 12345,
};

const audiences = [
  {
    id: 'aud1',
    name: 'Product Updates',
    member_count: 1234,
    unsubscribe_count: 21,
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2026-01-01T10:00:00Z',
    contact: {
      company: 'Atom Inc',
      address1: '1 Market St',
      city: 'San Francisco',
      state: 'CA',
      country: 'US',
    },
    permission_reminder: 'We send occasional product updates.',
    campaign_defaults: {},
    stats: {
      open_rate: 0.42,
      click_rate: 0.18,
      sub_rate: 0.05,
      unsub_rate: 0.01,
    },
  },
];

const campaigns = [
  {
    id: 'cam1',
    type: 'regular',
    create_time: '2026-01-05T10:00:00Z',
    archive_url: 'https://mailchimp.example/archive/1',
    status: 'sent',
    emails_sent: 1200,
    send_time: '2026-01-06T10:00:00Z',
    content_type: 'template',
    recipients: { list_name: 'Product Updates' },
    settings: { subject_line: 'January Product Digest' },
    tracking: {},
    report_summary: {
      opens: 500,
      unique_opens: 480,
      open_rate: 0.42,
      clicks: 90,
      click_rate: 0.18,
    },
  },
];

const automations = [
  {
    id: 'auto1',
    create_time: '2026-01-01T10:00:00Z',
    status: 'sending',
    emails_sent: 320,
    recipients: { list_name: 'Product Updates' },
    settings: { title: 'Welcome Series' },
    tracking: {},
    trigger_settings: {},
    report_summary: {
      open_rate: 0.38,
      click_rate: 0.12,
    },
  },
];

const templates = [
  {
    id: 1,
    type: 'user',
    name: 'Newsletter Template',
    drag_and_drop: true,
    responsive: true,
    category: 'Newsletters',
    date_created: '2025-03-01T10:00:00Z',
    date_edited: '2025-03-02T10:00:00Z',
    created_by: 'admin',
    edited_by: 'admin',
    active: true,
  },
];

const contactsList = [
  {
    id: 'contact1',
    email_address: 'vip@example.com',
    status: 'subscribed',
    full_name: 'Grace Kim',
    member_rating: 4,
    vip: true,
    last_changed: '2026-01-02T10:00:00Z',
    tags: ['vip-customer'],
    timestamp_signup: '2025-06-01T10:00:00Z',
    email_client: 'Gmail',
  },
];

const connectedHandlers = [
  rest.get('/api/v1/mailchimp/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, status: 'healthy' }));
  }),
  rest.get('/api/v1/mailchimp/audiences', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: audiences }));
  }),
  rest.get('/api/v1/mailchimp/campaigns', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: campaigns }));
  }),
  rest.get('/api/v1/mailchimp/automations', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: automations }));
  }),
  rest.get('/api/v1/mailchimp/templates', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: templates }));
  }),
  rest.get('/api/v1/mailchimp/stats', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: stats }));
  }),
];

const setDisconnected = (status = 503) => {
  server.use(
    rest.get('/api/v1/mailchimp/health', (req, res, ctx) => {
      return res(ctx.status(status), ctx.json({ error: 'not connected' }));
    })
  );
};

describe('MailchimpIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
  });

  test('shows connect screen when not connected', async () => {
    setDisconnected();

    renderWithProviders(<MailchimpIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /connect mailchimp/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: /connect mailchimp/i })
    ).toBeInTheDocument();
  });

  test('connect requires server prefix and API key before hitting the backend', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');

    setDisconnected();

    renderWithProviders(<MailchimpIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect mailchimp/i,
    });
    await user.click(connectButton);

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await waitFor(() => {
      expect(within(dialogContent).getByText('API Authentication')).toBeInTheDocument();
    });
    await user.click(within(dialogContent).getByRole('button', { name: /^connect$/i }));

    await new Promise((r) => setTimeout(r, 50));
    expect(
      fetchSpy.mock.calls.some(([url]) => String(url).includes('/api/v1/mailchimp/auth'))
    ).toBe(false);
    // Dialog stays open (missing-credentials toast, no state change)
    expect(within(dialogContent).getByPlaceholderText('us1')).toBeInTheDocument();
  });

  test('connects with API key and server prefix and loads the dashboard', async () => {
    const user = userEvent.setup();

    // Stateful health: disconnected at mount, healthy after connect reload
    let healthOk = false;
    server.use(
      rest.get('/api/v1/mailchimp/health', (req, res, ctx) => {
        return res(ctx.status(healthOk ? 200 : 503), ctx.json({ success: true }));
      }),
      rest.get('/api/v1/mailchimp/audiences', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: audiences }));
      }),
      rest.get('/api/v1/mailchimp/campaigns', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: campaigns }));
      }),
      rest.get('/api/v1/mailchimp/automations', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: automations }));
      }),
      rest.get('/api/v1/mailchimp/templates', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: templates }));
      }),
      rest.get('/api/v1/mailchimp/stats', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: stats }));
      }),
      rest.post('/api/v1/mailchimp/auth', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    renderWithProviders(<MailchimpIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect mailchimp/i,
    });
    await user.click(connectButton);

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(within(dialogContent).getByPlaceholderText('us1'), 'us1');
    await user.type(
      within(dialogContent).getByPlaceholderText(/enter your api key/i),
      'key123-us1'
    );

    healthOk = true;
    await user.click(within(dialogContent).getByRole('button', { name: /^connect$/i }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Mailchimp' })).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('Total Contacts')).toBeInTheDocument();
    });
    expect(screen.getByText('1,234')).toBeInTheDocument();
    expect(screen.getByText('42.0%')).toBeInTheDocument();
    expect(screen.getByText('18.0%')).toBeInTheDocument();
    expect(screen.getByText('$12,345')).toBeInTheDocument();
  });

  test('reports connection failure and stays on the connect screen', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/v1/mailchimp/health', (req, res, ctx) => {
        return res(ctx.status(503), ctx.json({ error: 'not connected' }));
      }),
      rest.post('/api/v1/mailchimp/auth', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'bad credentials' }));
      })
    );

    renderWithProviders(<MailchimpIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect mailchimp/i,
    });
    await user.click(connectButton);

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(within(dialogContent).getByPlaceholderText('us1'), 'us1');
    await user.type(
      within(dialogContent).getByPlaceholderText(/enter your api key/i),
      'bad-key'
    );
    await user.click(within(dialogContent).getByRole('button', { name: /^connect$/i }));

    // Auth 500 -> toast + dialog stays open, still disconnected
    await waitFor(() => {
      expect(
        within(dialogContent).getByPlaceholderText('us1')
      ).toBeInTheDocument();
    });
    expect(
      screen.getAllByRole('heading', { name: /connect mailchimp/i }).length
    ).toBeGreaterThan(0);
  });

  test('renders audiences with member counts and opens the details dialog', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<MailchimpIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Mailchimp' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /audiences/i }));

    await waitFor(() => {
      expect(screen.getByText('Product Updates')).toBeInTheDocument();
    });
    expect(screen.getByText('1,234 members')).toBeInTheDocument();
    expect(screen.getByText('21 unsubscribed')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /details/i }));

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /audience details/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/Atom Inc/)).toBeInTheDocument();
    expect(screen.getByText(/1 Market St/)).toBeInTheDocument();
    expect(screen.getByText(/San Francisco/)).toBeInTheDocument();
    expect(screen.getAllByText('42.0%').length).toBeGreaterThan(0);
  });

  test('loads contacts for an audience and shows them in the contacts tab', async () => {
    const user = userEvent.setup();

    server.use(
      ...connectedHandlers,
      rest.get('/api/v1/mailchimp/contacts', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: contactsList }));
      })
    );

    renderWithProviders(<MailchimpIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Mailchimp' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /audiences/i }));
    await waitFor(() => {
      expect(screen.getByText('Product Updates')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /load contacts/i }));

    // The component loads contacts into state but keeps the Audiences tab
    // active — switch to Contacts to see the populated table
    await user.click(screen.getByRole('button', { name: /^contacts$/i }));
    await waitFor(() => {
      expect(screen.getByText('Contacts (1)')).toBeInTheDocument();
    });
    expect(screen.getByText('vip@example.com')).toBeInTheDocument();
    expect(screen.getByText('Grace Kim')).toBeInTheDocument();
    expect(screen.getAllByText('VIP').length).toBeGreaterThan(0);
  });

  test('renders campaigns and opens the campaign detail dialog', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<MailchimpIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Mailchimp' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /campaigns/i }));

    await waitFor(() => {
      expect(screen.getByText('January Product Digest')).toBeInTheDocument();
    });
    expect(screen.getByText('sent')).toBeInTheDocument();
    expect(screen.getByText('Product Updates')).toBeInTheDocument();
    expect(screen.getByText('1,200')).toBeInTheDocument();
    expect(screen.getByText('42.0%')).toBeInTheDocument();

    const eyeButton = screen
      .getAllByRole('button')
      .find((b) => b.querySelector('svg.lucide-eye')) as HTMLElement;
    await user.click(eyeButton);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /campaign details/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByText('500')).toBeInTheDocument();
    expect(screen.getByText('90')).toBeInTheDocument();
    expect(screen.getByText('View Campaign Archive')).toBeInTheDocument();
  });

  test('renders automations and templates', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<MailchimpIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Mailchimp' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /automations/i }));
    await waitFor(() => {
      expect(screen.getByText('Welcome Series')).toBeInTheDocument();
    });
    expect(screen.getByText('sending')).toBeInTheDocument();
    expect(screen.getByText('320')).toBeInTheDocument();
    expect(screen.getByText('38.0%')).toBeInTheDocument();
    expect(screen.getByText('12.0%')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /templates/i }));
    await waitFor(() => {
      expect(screen.getByText('Newsletter Template')).toBeInTheDocument();
    });
    expect(screen.getByText('Newsletters')).toBeInTheDocument();
    expect(screen.getByText('Drag & Drop')).toBeInTheDocument();
    expect(screen.getByText('Responsive')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  test('renders contacts with VIP badge and opens the contact dialog', async () => {
    const user = userEvent.setup();

    server.use(
      ...connectedHandlers,
      rest.get('/api/v1/mailchimp/contacts', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: contactsList }));
      })
    );

    renderWithProviders(<MailchimpIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Mailchimp' })).toBeInTheDocument();
    });

    // Contacts only populate via the per-audience "Load Contacts" action
    await user.click(screen.getByRole('button', { name: /audiences/i }));
    await waitFor(() => {
      expect(screen.getByText('Product Updates')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: /load contacts/i }));
    await user.click(screen.getByRole('button', { name: /^contacts$/i }));

    await waitFor(() => {
      expect(screen.getByText('vip@example.com')).toBeInTheDocument();
    });
    expect(screen.getByText('Grace Kim')).toBeInTheDocument();
    expect(screen.getByText('subscribed')).toBeInTheDocument();
    expect(screen.getAllByText('VIP').length).toBeGreaterThan(0);

    const eyeButton = screen
      .getAllByRole('button')
      .find((b) => b.querySelector('svg.lucide-eye')) as HTMLElement;
    await user.click(eyeButton);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /contact details/i })
      ).toBeInTheDocument();
    });
    expect(screen.getByText('vip-customer')).toBeInTheDocument();
    expect(screen.getByText('Gmail')).toBeInTheDocument();
  });

  test('search posts the query to the search endpoint', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');

    server.use(
      ...connectedHandlers,
      rest.post('/api/v1/mailchimp/search', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({ success: true, data: { total_count: 4 } })
        );
      })
    );

    renderWithProviders(<MailchimpIntegration />);

    const searchInput = await screen.findByPlaceholderText(
      /search campaigns, contacts/i
    );
    await user.type(searchInput, 'digest{enter}');

    await waitFor(() => {
      expect(
        fetchSpy.mock.calls.some(
          ([url, init]) =>
            String(url).includes('/api/v1/mailchimp/search') &&
            (init as RequestInit)?.method === 'POST' &&
            String((init as RequestInit)?.body).includes('digest')
        )
      ).toBe(true);
    });
  });

  test('survives empty data responses without crashing', async () => {
    server.use(
      rest.get('/api/v1/mailchimp/health', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true }));
      }),
      rest.get('/api/v1/mailchimp/audiences', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/mailchimp/campaigns', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/mailchimp/automations', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/mailchimp/templates', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/mailchimp/stats', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'boom' }));
      })
    );

    renderWithProviders(<MailchimpIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Mailchimp' })).toBeInTheDocument();
    });
    expect(screen.queryByText('Total Contacts')).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /refresh data/i })
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: error paths, status variants, detail modal bodies
// ---------------------------------------------------------------------------
describe('MailchimpIntegration (extended coverage)', () => {
  let consoleSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    server.resetHandlers();
  });

  afterEach(() => {
    consoleSpy.mockRestore();
  });

  const connected = async (extra: typeof connectedHandlers = []) => {
    server.use(...connectedHandlers, ...extra);
    renderWithProviders(<MailchimpIntegration />);
    await screen.findByRole('heading', { name: 'Mailchimp' });
  };

  test('a failed data load disconnects the integration', async () => {
    server.use(
      rest.get('/api/v1/mailchimp/health', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, status: 'healthy' }))
      ),
      rest.get('/api/v1/mailchimp/audiences', (req, res) =>
        res.networkError('down')
      )
    );

    renderWithProviders(<MailchimpIntegration />);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to load Mailchimp data:',
        expect.anything()
      );
    });
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /connect mailchimp/i })
      ).toBeInTheDocument();
    });
  });

  test('search failures are logged without crashing', async () => {
    const user = userEvent.setup();
    await connected([
      rest.post('/api/v1/mailchimp/search', (req, res) =>
        res.networkError('down')
      ),
    ]);

    const searchInput = await screen.findByPlaceholderText(
      /search campaigns, contacts/i
    );
    await user.type(searchInput, 'boom{enter}');

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Search failed:', expect.anything());
    });
  });

  test('contact loading failures are logged without crashing', async () => {
    const user = userEvent.setup();
    await connected([
      rest.get('/api/v1/mailchimp/contacts', (req, res) =>
        res.networkError('down')
      ),
    ]);

    await user.click(screen.getByRole('button', { name: /audiences/i }));
    await screen.findByText('Product Updates');
    await user.click(screen.getByRole('button', { name: /load contacts/i }));

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to load contacts:',
        expect.anything()
      );
    });
  });

  test('renders every campaign status variant', async () => {
    const user = userEvent.setup();
    const multiStatusCampaigns = [
      'scheduled',
      'sending',
      'draft',
      'paused',
      'mystery',
    ].map((status, i) => ({
      ...campaigns[0],
      id: `cam-${status}`,
      status,
      settings: { subject_line: `Campaign ${status}` },
    }));

    server.use(
      rest.get('/api/v1/mailchimp/health', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, status: 'healthy' }))
      ),
      rest.get('/api/v1/mailchimp/audiences', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, data: [] }))
      ),
      rest.get('/api/v1/mailchimp/automations', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, data: [] }))
      ),
      rest.get('/api/v1/mailchimp/templates', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, data: [] }))
      ),
      rest.get('/api/v1/mailchimp/stats', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true }))
      ),
      rest.get('/api/v1/mailchimp/campaigns', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, data: multiStatusCampaigns }))
      )
    );
    renderWithProviders(<MailchimpIntegration />);
    await screen.findByRole('heading', { name: 'Mailchimp' });

    await user.click(screen.getByRole('button', { name: /campaigns/i }));
    await screen.findByText('Campaign scheduled');
    for (const status of ['scheduled', 'sending', 'draft', 'paused', 'mystery']) {
      expect(screen.getByText(status)).toBeInTheDocument();
    }
  });

  test('renders every contact status variant', async () => {
    const user = userEvent.setup();
    const multiStatusContacts = [
      'subscribed',
      'unsubscribed',
      'cleaned',
      'pending',
      'archived',
    ].map((status, i) => ({
      ...contactsList[0],
      id: `contact-${status}`,
      status,
      email_address: `${status}@example.com`,
    }));

    await connected([
      rest.get('/api/v1/mailchimp/contacts', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, data: multiStatusContacts }))
      ),
    ]);

    await user.click(screen.getByRole('button', { name: /audiences/i }));
    await screen.findByText('Product Updates');
    await user.click(screen.getByRole('button', { name: /load contacts/i }));
    await user.click(screen.getByRole('button', { name: /^contacts$/i }));

    await screen.findByText('Contacts (5)');
    for (const status of ['subscribed', 'unsubscribed', 'cleaned', 'pending', 'archived']) {
      expect(screen.getByText(status)).toBeInTheDocument();
    }
  });

  test('campaign detail modal renders the full body and archive link', async () => {
    const user = userEvent.setup();
    const openSpy = jest.fn();
    window.open = openSpy as any;

    await connected();

    await user.click(screen.getByRole('button', { name: /campaigns/i }));
    await screen.findByText('January Product Digest');

    const eyeButton = screen
      .getAllByRole('button')
      .find((b) => b.querySelector('svg.lucide-eye')) as HTMLElement;
    await user.click(eyeButton);

    await screen.findByRole('heading', { name: /campaign details/i });
    expect(screen.getByText('Subject Line')).toBeInTheDocument();
    expect(screen.getByText('Send Time')).toBeInTheDocument();
    expect(screen.getByText('Performance Metrics')).toBeInTheDocument();
    expect(screen.getByText('Unique Opens')).toBeInTheDocument();
    expect(screen.getAllByText('Open Rate').length).toBeGreaterThan(1);
    expect(screen.getByText('Click Rate')).toBeInTheDocument();

    await user.click(screen.getByText('View Campaign Archive'));
    expect(openSpy).toHaveBeenCalledWith(
      'https://mailchimp.example/archive/1',
      '_blank'
    );

    await user.click(screen.getByRole('button', { name: /close/i }));
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: /campaign details/i })).not.toBeInTheDocument();
    });
  });

  test('opens the create campaign and add contact modals', async () => {
    const user = userEvent.setup();

    await connected();

    await user.click(screen.getByRole('button', { name: /audiences/i }));
    await screen.findByText('Product Updates');
    await user.click(screen.getByRole('button', { name: /create campaign/i }));
    await waitFor(() => {
      expect(screen.getByText('Create Campaign')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /^contacts$/i }));
    await user.click(screen.getByRole('button', { name: /add contact/i }));
    await waitFor(() => {
      expect(screen.getByText('Add Contact')).toBeInTheDocument();
    });
  });
});

describe('MailchimpIntegration (dialog close buttons)', () => {
  test('connect modal cancel, audience modal close, and contact modal close', async () => {
    const user = userEvent.setup();
    server.use(...connectedHandlers);

    // connect modal cancel
    server.use(
      rest.get('/api/v1/mailchimp/health', (req, res, ctx) =>
        res(ctx.status(503), ctx.json({ error: 'nope' }))
      )
    );
    renderWithProviders(<MailchimpIntegration />);
    await user.click(await screen.findByRole('button', { name: /connect mailchimp/i }));
    await screen.findByText('API Authentication');
    await user.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByText('API Authentication')).not.toBeInTheDocument();
    });

    // remount in the connected state for the detail modals
    cleanup();
    server.use(...connectedHandlers);
    renderWithProviders(<MailchimpIntegration />);
    await screen.findByRole('heading', { name: 'Mailchimp' });

    // audience modal close
    await user.click(screen.getByRole('button', { name: /audiences/i }));
    await screen.findByText('Product Updates');
    await user.click(screen.getByRole('button', { name: /details/i }));
    await screen.findByRole('heading', { name: /audience details/i });
    await user.click(screen.getByRole('button', { name: /close/i }));
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: /audience details/i })).not.toBeInTheDocument();
    });

    // contact modal close
    server.use(
      rest.get('/api/v1/mailchimp/contacts', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, data: contactsList }))
      )
    );
    await user.click(screen.getByRole('button', { name: /load contacts/i }));
    await user.click(screen.getByRole('button', { name: /^contacts$/i }));
    await screen.findByText('vip@example.com');
    const eyeButton = screen
      .getAllByRole('button')
      .find((b) => b.querySelector('svg.lucide-eye')) as HTMLElement;
    await user.click(eyeButton);
    await screen.findByRole('heading', { name: /contact details/i });
    await user.click(screen.getByRole('button', { name: /close/i }));
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: /contact details/i })).not.toBeInTheDocument();
    });
  });
});
