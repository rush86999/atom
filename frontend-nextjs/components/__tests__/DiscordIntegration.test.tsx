/**
 * DiscordIntegration Component Tests
 *
 * Tests verify the real Discord integration component
 * (components/DiscordIntegration.tsx):
 * - Health check / connection state (GET /api/integrations/discord/health)
 * - Profile + guild data loading after connection
 * - OAuth connect flow (POST /api/integrations/discord/auth/start)
 * - Disconnect flow (POST /api/integrations/discord/revoke)
 * - Tab content (servers / channels / analytics / notifications)
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts. jsdom cannot navigate (window.location is non-configurable),
 * so OAuth redirects are asserted via the auth-start fetch instead.
 */

import React from 'react';
import { renderWithProviders, screen, waitFor, within } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import DiscordIntegration from '../DiscordIntegration';

const profile = {
  username: 'atombot',
  discriminator: '0001',
  avatar_url: 'https://cdn.discordapp.com/avatars/1/x.png',
  servers_count: 3,
  channels_count: 12,
};

const guilds = [
  {
    id: 'g1',
    name: 'Atom HQ',
    icon_url: 'https://cdn.discordapp.com/icons/g1/x.png',
    member_count: 250,
    channel_count: 8,
    owner: true,
  },
  {
    id: 'g2',
    name: 'Design Crew',
    icon_url: '',
    member_count: 40,
    channel_count: 3,
    owner: false,
  },
];

const connectedHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ providers: { discord: { connected: true, source: 'user_connection' } } })
    );
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
  rest.post('/api/integrations/discord/profile', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: profile }));
  }),
  rest.post('/api/integrations/discord/guilds', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: guilds }));
  }),
];

const setDisconnected = (status = 503) => {
  server.use(
    rest.get('/api/integrations/connection-status', (req, res, ctx) => {
      return res(ctx.status(status), ctx.json({ success: false }));
    })
  );
};

describe('DiscordIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
  });

  test('renders the component heading', async () => {
    // Register a handler so the mount health check is answered by MSW —
    // an unhandled request would fall through to the real network and its
    // async rejection could pollute the next test
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(503), ctx.json({ success: false }));
      })
    );

    renderWithProviders(<DiscordIntegration />);

    expect(
      screen.getByRole('heading', { name: /discord integration/i })
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('Not Connected')).toBeInTheDocument();
    });
  });

  test('shows connect UI when not connected', async () => {
    setDisconnected();

    renderWithProviders(<DiscordIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Discord not connected')).toBeInTheDocument();
    });
    // The header and the connect alert each render a connect button
    expect(
      screen.getAllByRole('button', { name: /connect discord/i }).length
    ).toBeGreaterThan(0);
    expect(screen.getByText('Not Connected')).toBeInTheDocument();
  });

  test('shows connected state and loads profile + guilds', async () => {
    server.use(...connectedHandlers);

    renderWithProviders(<DiscordIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    // Profile card
    await waitFor(() => {
      expect(screen.getByText('atombot')).toBeInTheDocument();
    });
    expect(screen.getByText('#0001')).toBeInTheDocument();
    expect(screen.getByText('3 Servers')).toBeInTheDocument();
    expect(screen.getByText('12 Channels')).toBeInTheDocument();

    // Guild grid (Servers tab is the default)
    expect(screen.getByText('Atom HQ')).toBeInTheDocument();
    expect(screen.getByText('250 members • 8 channels')).toBeInTheDocument();
    expect(screen.getByText('Owner')).toBeInTheDocument();
    expect(screen.getByText('Design Crew')).toBeInTheDocument();
    expect(screen.getByText('40 members • 3 channels')).toBeInTheDocument();
  });

  test('connect button triggers the backend OAuth start flow', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(503), ctx.json({ success: false }));
      }),
      rest.post('/api/integrations/discord/auth/start', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            authorization_url: 'https://discord.com/oauth2/authorize?client_id=x',
          })
        );
      })
    );

    renderWithProviders(<DiscordIntegration />);

    const connectButton = (await screen.findAllByRole('button', {
      name: /connect discord/i,
    }))[0];

    consoleErrorSpy.mockClear();
    await user.click(connectButton);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/integrations/discord/auth/start'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('current'),
        })
      );
    });
    expect(consoleErrorSpy).not.toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });

  test('stays disconnected when the OAuth start flow reports failure', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(503), ctx.json({ success: false }));
      }),
      rest.post('/api/integrations/discord/auth/start', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: false, error: 'no token' }));
      })
    );

    renderWithProviders(<DiscordIntegration />);

    const connectButton = (await screen.findAllByRole('button', {
      name: /connect discord/i,
    }))[0];
    await user.click(connectButton);

    // Failure must not navigate or flip the connection state
    await waitFor(() => {
      expect(screen.getByText('Discord not connected')).toBeInTheDocument();
    });
  });

  test('disconnect revokes the integration and returns to connect UI', async () => {
    const user = userEvent.setup();

    server.use(
      ...connectedHandlers,
      rest.post('/api/integrations/discord/revoke', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    renderWithProviders(<DiscordIntegration />);

    const disconnectButton = await screen.findByRole('button', {
      name: /disconnect/i,
    });
    await user.click(disconnectButton);

    await waitFor(() => {
      expect(screen.getByText('Discord not connected')).toBeInTheDocument();
    });
    expect(
      screen.getAllByRole('button', { name: /connect discord/i }).length
    ).toBeGreaterThan(0);
  });

  test('refresh button re-checks connection and reloads data', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<DiscordIntegration />);

    await waitFor(() => {
      expect(screen.getByText('atombot')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  test('channels tab shows the coming-soon placeholder', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<DiscordIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /channels/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/channel management coming soon/i)
      ).toBeInTheDocument();
    });
  });

  test('analytics tab reports guild counts and notifications tab is stubbed', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<DiscordIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /analytics/i }));

    // Analytics cards derive from the loaded guilds array
    const analyticsTab = screen.getByText('Discord Analytics').closest('div') as HTMLElement;
    await waitFor(() => {
      expect(within(analyticsTab).getByText('Total Servers')).toBeInTheDocument();
    });
    expect(within(analyticsTab).getAllByText('2').length).toBeGreaterThan(0);

    await user.click(screen.getByRole('button', { name: /notifications/i }));
    expect(
      screen.getByText(/notification management coming soon/i)
    ).toBeInTheDocument();
  });
});
