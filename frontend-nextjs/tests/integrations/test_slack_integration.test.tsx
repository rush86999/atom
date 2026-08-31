/**
 * SlackIntegration Component Tests
 *
 * Tests verify the real Slack integration component
 * (components/SlackIntegration.tsx):
 * - Connection status check (GET /api/integrations/slack/health)
 * - Disconnected / connect state
 * - Channels, messages, users, and workspace data loading
 * - Channel search filtering, send-message, and create-channel dialogs
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SlackIntegration from '@/components/SlackIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

// The setup.ts useToast mock returns a fresh object every render, which changes
// the identity of loadChannels (deps [toast]) -> checkConnection -> re-triggers
// the mount effect -> infinite refetch loop (heap OOM). Return a stable toast
// so the component's useCallback identities are stable.
const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const channels = [
  {
    id: 'ch-1',
    name: 'general',
    purpose: 'Company-wide announcements',
    num_members: 42,
    is_archived: false,
    is_general: true,
    created: 1700000000,
    creator: 'U1',
    is_private: false,
  },
  {
    id: 'ch-2',
    name: 'engineering',
    purpose: 'Engineering discussion',
    num_members: 12,
    is_archived: false,
    is_general: false,
    created: 1700000001,
    creator: 'U1',
    is_private: false,
  },
  {
    id: 'ch-3',
    name: 'confidential',
    purpose: 'Leadership only',
    num_members: 5,
    is_archived: false,
    is_general: false,
    created: 1700000002,
    creator: 'U1',
    is_private: true,
  },
];

const messages = [
  {
    team: 'T1',
    user: 'U1',
    user_profile: {
      real_name: 'Rushi Parikh',
      display_name: 'Rushi',
      image_48: '',
      image_32: '',
      image_24: '',
    },
    text: 'Hello team!',
    ts: '1700000000.000',
    attachments: [],
    reactions: [],
    replies: [],
    files: [],
  },
  {
    team: 'T1',
    user: 'U2',
    user_profile: {
      real_name: 'Jane Smith',
      display_name: 'Jane',
      image_48: '',
      image_32: '',
      image_24: '',
    },
    text: 'Morning!',
    ts: '1700000001.000',
    attachments: [],
    reactions: [{ name: 'wave', count: 2, users: ['U1', 'U2'] }],
    replies: [],
    files: [],
  },
];

const users = [
  {
    id: 'U1',
    name: 'rushi',
    real_name: 'Rushi Parikh',
    display_name: 'Rushi',
    email: 'rushi@example.com',
    phone: '',
    title: 'Engineer',
    is_admin: true,
    is_owner: false,
    is_bot: false,
    deleted: false,
    profile: {
      real_name: 'Rushi Parikh',
      display_name: 'Rushi',
      real_name_normalized: '',
      display_name_normalized: '',
      email: 'rushi@example.com',
      image_48: '',
    },
  },
  {
    id: 'U2',
    name: 'jane',
    real_name: 'Jane Smith',
    display_name: 'Jane',
    email: 'jane@example.com',
    phone: '',
    title: 'Designer',
    is_admin: false,
    is_owner: false,
    is_bot: false,
    deleted: false,
    profile: {
      real_name: 'Jane Smith',
      display_name: 'Jane',
      real_name_normalized: '',
      display_name_normalized: '',
      email: 'jane@example.com',
      image_48: '',
    },
  },
];

const workspace = {
  id: 'T1',
  name: 'Acme Workspace',
  domain: 'acme',
  email_domain: 'acme.com',
  icon: { image_102: '' },
};

const slackHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { slack: { connected: true, source: 'user_connection' } } }));
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { slack: { connected: true, source: 'user_connection' } } }));
  }),

  rest.post('/api/integrations/slack/workspace', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { workspace } }));
  }),

  rest.get('/api/integrations/slack/channels', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { channels } }));
  }),

  rest.get('/api/integrations/slack/messages', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { messages } }));
  }),

  rest.get('/api/integrations/slack/users', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { users } }));
  }),

  rest.post('/api/integrations/slack/messages', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/slack/channels/create', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

const setNotConnected = () => {
  server.use(
    rest.get('/api/integrations/connection-status', (req, res, ctx) => {
      return res(ctx.status(500), ctx.json({ error: 'not connected' }));
    })
  );
};

describe('SlackIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...slackHandlers);
  });

  // Test 1: shows the connect screen when not connected
  test('shows connect screen when not connected', async () => {
    setNotConnected();

    render(<SlackIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /connect slack/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /connect slack workspace/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setNotConnected();

    render(<SlackIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect slack workspace/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 3: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<SlackIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /slack integration/i })
      ).toBeInTheDocument();
      expect(screen.getAllByText('Connected').length).toBeGreaterThan(0);
    });
  });

  // Test 4: displays overview stat cards
  test('displays overview stat cards', async () => {
    render(<SlackIntegration />);

    await waitFor(() => {
      expect(screen.getByText('1 private')).toBeInTheDocument();
      expect(screen.getByText('2 total')).toBeInTheDocument();
      expect(screen.getByText('In selected channel')).toBeInTheDocument();
    });
  });

  // Test 5: displays channels in the default tab
  test('displays channels in the default tab', async () => {
    render(<SlackIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/#general/)).toBeInTheDocument();
      expect(screen.getByText(/#engineering/)).toBeInTheDocument();
      expect(screen.getByText(/#confidential/)).toBeInTheDocument();
      expect(screen.getByText('General')).toBeInTheDocument();
      expect(screen.getByText('Private')).toBeInTheDocument();
    });
  });

  // Test 6: filters channels by search query
  test('filters channels by search query', async () => {
    render(<SlackIntegration />);

    await screen.findByText(/#general/);

    const searchInput = screen.getByPlaceholderText('Search channels...');
    fireEvent.change(searchInput, { target: { value: 'engineer' } });

    expect(screen.getByText(/#engineering/)).toBeInTheDocument();
    expect(screen.queryByText(/#general/)).not.toBeInTheDocument();
  });

  // Test 7: selecting a channel loads messages
  test('selecting a channel loads messages', async () => {
    render(<SlackIntegration />);

    await screen.findByText(/#general/);

    // The component fires loadChannels from BOTH checkConnection and the
    // connected effect, so the loader can briefly flicker back in and unmount
    // the rows between findByText and the click. Wait until the loader is
    // fully gone (both loads settled) so the row is stable before clicking.
    await waitFor(() => {
      expect(screen.getByText(/#general/)).toBeInTheDocument();
      expect(document.querySelector('.lucide-loader-2')).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/#general/));

    fireEvent.click(screen.getByRole('button', { name: 'Messages' }));

    await waitFor(() => {
      expect(screen.getByText('Hello team!')).toBeInTheDocument();
      expect(screen.getByText('Morning!')).toBeInTheDocument();
    });
  });

  // Test 8: displays users on the Users tab
  test('displays users on the Users tab', async () => {
    render(<SlackIntegration />);

    await screen.findByText(/#general/);

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    });
  });

  // Test 9: displays workspace on the Workspace tab
  test('displays workspace on the Workspace tab', async () => {
    render(<SlackIntegration />);

    await screen.findByText(/#general/);

    fireEvent.click(screen.getByRole('button', { name: 'Workspace' }));

    await waitFor(() => {
      expect(screen.getByText('acme.slack.com')).toBeInTheDocument();
      expect(screen.getByText('Email domain: acme.com')).toBeInTheDocument();
    });
  });

  // Test 10: Create Channel button opens the create channel dialog
  test('opens create channel dialog', async () => {
    render(<SlackIntegration />);

    await screen.findByText(/#general/);

    fireEvent.click(screen.getByRole('button', { name: /create channel/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: /create channel/i })
      ).toBeInTheDocument();
    });
  });

  // Test 11: creating a channel calls POST /api/integrations/slack/channels/create
  test('creating a channel calls the create endpoint', async () => {
    let requestBody: any = null;
    server.use(
      rest.post('/api/integrations/slack/channels/create', (req, res, ctx) => {
        // MSW pre-parses JSON request bodies into objects
        requestBody = req.body as any;
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<SlackIntegration />);

    await screen.findByText(/#general/);

    fireEvent.click(screen.getByRole('button', { name: /create channel/i }));

    const nameInput = screen.getByPlaceholderText('channel-name');
    fireEvent.change(nameInput, { target: { value: 'new-channel' } });

    // Form submit button is the second "Create Channel" button (toolbar first)
    fireEvent.click(
      screen.getAllByRole('button', { name: /create channel/i })[1]
    );

    await waitFor(() => {
      expect(requestBody).toEqual(
        expect.objectContaining({ name: 'new-channel' })
      );
    });
  });

  // Test 12: Send Message button opens the send message dialog
  test('opens send message dialog', async () => {
    render(<SlackIntegration />);

    await screen.findByText(/#general/);

    // Wait for the double-fired loadChannels to settle (loader flicker) so
    // the row is stable before clicking.
    await waitFor(() => {
      expect(screen.getByText(/#general/)).toBeInTheDocument();
      expect(document.querySelector('.lucide-loader-2')).not.toBeInTheDocument();
    });

    // Select a channel first so the toolbar Send Message button is enabled
    fireEvent.click(screen.getByText(/#general/));
    fireEvent.click(screen.getByRole('button', { name: 'Messages' }));

    fireEvent.click(screen.getByRole('button', { name: /send message/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: /send message/i })
      ).toBeInTheDocument();
    });
  });

  // Test 13: shows refresh status button
  test('shows refresh status button', async () => {
    render(<SlackIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /refresh status/i })
      ).toBeInTheDocument();
    });
  });

  // Test 14: handles connection error as disconnected
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Server error' }));
      })
    );

    render(<SlackIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect slack workspace/i })
      ).toBeInTheDocument();
    });
  });
});
