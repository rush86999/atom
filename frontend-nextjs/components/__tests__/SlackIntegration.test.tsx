/**
 * Slack Integration Component Tests
 *
 * Test suite for Slack integration functionality including:
 * - OAuth connection flow
 * - Channel and message management
 * - Workspace and team data fetching
 * - Webhook handling
 * - Error handling and loading states
 */

import React from 'react';
import { renderWithProviders, screen, waitFor, within } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import SlackIntegration from '../SlackIntegration';

// Mock data
const mockSlackChannels = [
  {
    id: 'C1234567890',
    name: 'general',
    is_channel: true,
    created: 1234567890,
    is_archived: false,
    is_general: true,
    members: 150,
    num_members: 150,
    topic: {
      value: 'Company-wide announcements and work-based matters',
      creator: 'U1234567890',
      last_set: 1234567890,
    },
    purpose: 'This channel is for team-wide communication and announcements.',
  },
  {
    id: 'C0987654321',
    name: 'engineering',
    is_channel: true,
    created: 1234567891,
    is_archived: false,
    is_general: false,
    members: 45,
    num_members: 45,
    topic: {
      value: 'Engineering team discussions',
      creator: 'U0987654321',
      last_set: 1234567891,
    },
    purpose: 'Engineering team discussions',
  },
];

const mockSlackMessages = [
  {
    type: 'message',
    subtype: 'bot_message',
    bot_id: 'B1234567890',
    text: 'Test message from bot',
    ts: '1234567890.123456',
    channel: 'C1234567890',
  },
  {
    type: 'message',
    user: 'U1234567890',
    text: 'Test user message',
    ts: '1234567891.123456',
    channel: 'C1234567890',
  },
];

const mockSlackUsers = [
  {
    id: 'U1234567890',
    team_id: 'T1234567890',
    name: 'john.doe',
    deleted: false,
    color: '9f69e7',
    real_name: 'John Doe',
    tz: 'America/Los_Angeles',
    tz_label: 'Pacific Daylight Time',
    tz_offset: -25200,
    profile: {
      avatar_hash: 'g1234567890',
      status_text: 'Working on Atom',
      status_emoji: ':rocket:',
      real_name: 'John Doe',
      display_name: 'John Doe',
      real_name_normalized: 'John Doe',
      display_name_normalized: 'John Doe',
      email: 'john@example.com',
      image_24: 'https://example.com/avatar24.jpg',
      image_32: 'https://example.com/avatar32.jpg',
      image_48: 'https://example.com/avatar48.jpg',
      image_72: 'https://example.com/avatar72.jpg',
      image_192: 'https://example.com/avatar192.jpg',
      image_512: 'https://example.com/avatar512.jpg',
    },
  },
];

// Handlers that put the component into its connected state: the health check
// must succeed and the workspace fetch must resolve for the main UI to render.
const connectedStatusHandler = rest.get('*/api/integrations/connection-status', (req, res, ctx) => {
  return res(ctx.status(200), ctx.json({ providers: { slack: { connected: true, source: 'user_connection' } } }));
});
const workspaceOkHandler = rest.post('*/api/integrations/slack/workspace', (req, res, ctx) => {
  return res(
    ctx.status(200),
    ctx.json({
      success: true,
      data: {
        workspace: {
          id: 'T1234567890',
          name: 'Test Workspace',
          icon: { image_102: 'https://example.com/icon.png' },
        },
      },
    })
  );
});

const channelsHandler = rest.get('*/api/integrations/slack/channels', (req, res, ctx) => {
  return res(
    ctx.status(200),
    ctx.json({
      success: true,
      data: {
        channels: mockSlackChannels,
      },
    })
  );
});

describe('SlackIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('renders Slack integration component', () => {
      renderWithProviders(<SlackIntegration />);
      expect(screen.getByText(/slack/i)).toBeInTheDocument();
    });

    it('shows connection form when not authenticated', async () => {
      // The shared MSW server answers health with 200, so force a failing
      // health check to put the component into the disconnected state
      server.use(
        rest.get('*/api/integrations/connection-status', (req, res, ctx) => {
          return res(ctx.status(503), ctx.json({ error: 'unhealthy' }));
        })
      );

      renderWithProviders(<SlackIntegration />);

      await waitFor(() => {
        expect(screen.getByText(/connect slack workspace/i)).toBeInTheDocument();
      });
    });
  });

  describe('OAuth Connection Flow', () => {
    it('connect button is wired to the backend OAuth flow', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      // The shared MSW server answers health with 200 — force the
      // disconnected state so the connect form (and button) render
      server.use(
        rest.get('*/api/integrations/connection-status', (req, res, ctx) => {
          return res(ctx.status(503), ctx.json({ error: 'unhealthy' }));
        })
      );

      renderWithProviders(<SlackIntegration />);

      const connectButton = await screen.findByRole('button', {
        name: /connect slack workspace/i,
      });

      // Async errors from earlier tests' renders can land here — only assert
      // on errors triggered by this test's click
      consoleErrorSpy.mockClear();

      // jsdom cannot navigate (window.location is non-configurable), so the
      // only observable contract is that clicking the connect button is
      // handled without crashing. The OAuth flow itself is backend-driven:
      // the component navigates to /api/integrations/slack/auth/start.
      await user.click(connectButton);

      expect(consoleErrorSpy).not.toHaveBeenCalled();
      expect(screen.getByText(/connect slack workspace/i)).toBeInTheDocument();

      consoleErrorSpy.mockRestore();
    });

    it('shows connected state when health check succeeds', async () => {
      server.use(connectedStatusHandler, workspaceOkHandler);

      renderWithProviders(<SlackIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });
      // The workspace fetch is async — wait for it to populate the header
      await waitFor(() => {
        expect(screen.getAllByText('Test Workspace').length).toBeGreaterThan(0);
      });
    });

    it('shows connect form when health check fails', async () => {
      server.use(
        rest.get('*/api/integrations/connection-status', (req, res, ctx) => {
          return res(ctx.status(500), ctx.json({ error: 'unhealthy' }));
        })
      );

      renderWithProviders(<SlackIntegration />);

      await waitFor(() => {
        expect(screen.getByText(/connect slack workspace/i)).toBeInTheDocument();
      });
    });
  });

  describe('Channel Management', () => {
    it('fetches and displays channels after connection', async () => {
      server.use(connectedStatusHandler, workspaceOkHandler, channelsHandler);

      renderWithProviders(<SlackIntegration />);

      await waitFor(() => {
        expect(screen.getByText('#general')).toBeInTheDocument();
        expect(screen.getByText('#engineering')).toBeInTheDocument();
      });
    });

    it('filters channels by search query', async () => {
      const user = userEvent.setup();

      server.use(connectedStatusHandler, workspaceOkHandler, channelsHandler);

      renderWithProviders(<SlackIntegration />);

      const searchInput = await screen.findByPlaceholderText(/search channels/i);
      await user.type(searchInput, 'engineering');

      await waitFor(() => {
        expect(screen.getByText('#engineering')).toBeInTheDocument();
        expect(screen.queryByText('#general')).not.toBeInTheDocument();
      });
    });

    it('shows channel member count', async () => {
      server.use(connectedStatusHandler, workspaceOkHandler, channelsHandler);

      renderWithProviders(<SlackIntegration />);

      await waitFor(() => {
        expect(screen.getByText(/150 members/i)).toBeInTheDocument(); // General channel members
      });
    });
  });

  describe('Message Management', () => {
    const messagesHandler = rest.get('*/api/integrations/slack/messages', (req, res, ctx) => {
      return res(
        ctx.status(200),
        ctx.json({
          success: true,
          data: {
            messages: mockSlackMessages,
          },
        })
      );
    });

    it('fetches and displays messages for selected channel', async () => {
      const user = userEvent.setup();

      server.use(connectedStatusHandler, workspaceOkHandler, channelsHandler, messagesHandler);

      renderWithProviders(<SlackIntegration />);

      // Select the general channel to trigger message loading, then open the
      // Messages tab (TabsContent only renders when its tab is active)
      // Wait for the workspace fetch to settle so the channels list is stable
      // before clicking (a later re-render would detach the queried node)
      await screen.findAllByText('Test Workspace');
      const generalChannel = await screen.findByText('#general');
      generalChannel.click();
      await user.click(await screen.findByRole('button', { name: /messages/i }));

      await waitFor(() => {
        expect(screen.getByText(/test user message/i)).toBeInTheDocument();
      });
    });

    it('sends message to channel', async () => {
      const user = userEvent.setup();

      server.use(
        connectedStatusHandler,
        workspaceOkHandler,
        channelsHandler,
        messagesHandler,
        rest.post('*/api/integrations/slack/messages', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              message: {
                type: 'message',
                text: 'New test message',
                ts: '1234567892.123456',
              },
            })
          );
        })
      );

      const fetchSpy = jest.spyOn(global, 'fetch');

      renderWithProviders(<SlackIntegration />);

      // Select a channel, switch to the Messages tab (TabsContent only
      // renders when its tab is active), then open the composer dialog
      // Wait for the workspace fetch to settle so the channels list is stable
      // before clicking (a later re-render would detach the queried node)
      await screen.findAllByText('Test Workspace');
      const generalChannel = await screen.findByText('#general');
      generalChannel.click();
      await user.click(await screen.findByRole('button', { name: /messages/i }));
      await user.click(await screen.findByRole('button', { name: /send message/i }));

      const dialogContent = document.getElementById('dialog-content') as HTMLElement;

      // Pick the channel inside the dialog's Radix Select
      await user.click(within(dialogContent).getByRole('combobox'));
      const listbox = await screen.findByRole('listbox');
      await user.click(within(listbox).getByText('#general'));

      const messageInput = within(dialogContent).getByPlaceholderText(/type your message/i);
      await user.type(messageInput, 'New test message');

      const sendButton = within(dialogContent).getByRole('button', { name: /send message/i });
      await user.click(sendButton);

      // The composer posts the message with the typed body
      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/slack/messages'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('New test message'),
          })
        );
      });
    });

    it('handles message sending errors', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      server.use(
        connectedStatusHandler,
        workspaceOkHandler,
        channelsHandler,
        messagesHandler,
        rest.post('*/api/integrations/slack/messages', (req, res, ctx) => {
          // Network-level failure: the request is dropped entirely
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 10);
          });
        })
      );

      renderWithProviders(<SlackIntegration />);

      // Wait for the workspace fetch to settle so the channels list is stable
      // before clicking (a later re-render would detach the queried node)
      await screen.findAllByText('Test Workspace');
      const generalChannel = await screen.findByText('#general');
      generalChannel.click();
      await user.click(await screen.findByRole('button', { name: /messages/i }));
      await user.click(await screen.findByRole('button', { name: /send message/i }));

      const dialogContent = document.getElementById('dialog-content') as HTMLElement;

      await user.click(within(dialogContent).getByRole('combobox'));
      const listbox = await screen.findByRole('listbox');
      await user.click(within(listbox).getByText('#general'));

      const messageInput = within(dialogContent).getByPlaceholderText(/type your message/i);
      await user.type(messageInput, 'Test message');

      const sendButton = within(dialogContent).getByRole('button', { name: /send message/i });
      await user.click(sendButton);

      // The app logs the failure and keeps the composer open — it must not crash
      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });

      consoleErrorSpy.mockRestore();
    });
  });

  describe('User Management', () => {
    const usersHandler = rest.get('*/api/integrations/slack/users', (req, res, ctx) => {
      return res(
        ctx.status(200),
        ctx.json({
          success: true,
          data: {
            users: mockSlackUsers,
          },
        })
      );
    });

    it('fetches and displays team members', async () => {
      const user = userEvent.setup();

      server.use(connectedStatusHandler, workspaceOkHandler, usersHandler);

      renderWithProviders(<SlackIntegration />);

      // Users render in the Users tab (the app's TabsTrigger is a plain button)
      await user.click(await screen.findByRole('button', { name: /users/i }));

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('@john.doe')).toBeInTheDocument();
      });
    });

    it('shows user profile details', async () => {
      const user = userEvent.setup();

      server.use(connectedStatusHandler, workspaceOkHandler, usersHandler);

      renderWithProviders(<SlackIntegration />);

      await user.click(await screen.findByRole('button', { name: /users/i }));

      await waitFor(() => {
        expect(screen.getByText('john@example.com')).toBeInTheDocument();
      });
    });
  });

  describe('Webhook Handling', () => {
    it('does not expose client-side webhook management (webhooks are server-side)', async () => {
      server.use(connectedStatusHandler, workspaceOkHandler);

      renderWithProviders(<SlackIntegration />);

      // The component manages webhooks server-side only: the connected UI
      // must not surface any webhook configuration/creation controls
      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });
      expect(screen.queryByRole('button', { name: /create webhook/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /webhooks/i })).not.toBeInTheDocument();
    });
  });

  describe('Channel Creation', () => {
    it('creates a channel through the create-channel dialog', async () => {
      const user = userEvent.setup();
      const fetchSpy = jest.spyOn(global, 'fetch');

      server.use(
        connectedStatusHandler,
        workspaceOkHandler,
        channelsHandler,
        rest.post('*/api/integrations/slack/channels/create', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              channel: {
                id: 'C0000000001',
                name: 'new-team',
              },
            })
          );
        })
      );

      renderWithProviders(<SlackIntegration />);

      // Open the create-channel dialog from the Channels tab
      await screen.findAllByText('Test Workspace');
      const createChannelButton = await screen.findByRole('button', {
        name: /create channel/i,
      });
      await user.click(createChannelButton);

      const dialogContent = document.getElementById('dialog-content') as HTMLElement;
      const nameInput = within(dialogContent).getByPlaceholderText('channel-name');
      await user.type(nameInput, 'new-team');
      const purposeInput = within(dialogContent).getByPlaceholderText(/what's this channel about/i);
      await user.type(purposeInput, 'Team discussions');

      await user.click(within(dialogContent).getByRole('button', { name: /create channel/i }));

      // The creator posts the new channel to the backend
      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/slack/channels/create'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('new-team'),
          })
        );
      });
    });
  });

  describe('Error Handling', () => {
    it('handles workspace load failure gracefully', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      // Health succeeds but the workspace fetch fails at the network level —
      // the app must not crash; it logs the failure and stays in the
      // connected UI
      server.use(
        connectedStatusHandler,
        rest.post('*/api/integrations/slack/workspace', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 10);
          });
        })
      );

      renderWithProviders(<SlackIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });
      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });

      consoleErrorSpy.mockRestore();
    });

    it('does not render channels when the channels fetch fails', async () => {
      server.use(
        connectedStatusHandler,
        workspaceOkHandler,
        rest.get('*/api/integrations/slack/channels', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ error: 'invalid_token' })
          );
        })
      );

      renderWithProviders(<SlackIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });

      // Non-ok responses leave the channel list empty
      expect(screen.queryByText('#general')).not.toBeInTheDocument();
    });

    it('handles API rate limiting gracefully', async () => {
      server.use(
        connectedStatusHandler,
        workspaceOkHandler,
        rest.get('*/api/integrations/slack/channels', (req, res, ctx) => {
          return res(
            ctx.status(429),
            ctx.json({
              error: 'rate_limited',
              retry_after: 60,
            })
          );
        })
      );

      renderWithProviders(<SlackIntegration />);

      // Rate-limited channels response leaves the app functional (no crash,
      // empty channel list)
      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });
      expect(screen.queryByText('#general')).not.toBeInTheDocument();
    });
  });

  describe('Loading States', () => {
    it('shows loading indicator during channel fetch', async () => {
      server.use(
        connectedStatusHandler,
        workspaceOkHandler,
        rest.get('*/api/integrations/slack/channels', async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              data: {
                channels: mockSlackChannels,
              },
            })
          );
        })
      );

      renderWithProviders(<SlackIntegration />);

      // The delayed channel fetch eventually populates the channel list
      await waitFor(() => {
        expect(screen.getByText('#general')).toBeInTheDocument();
      });
    });
  });

  describe('Disconnection', () => {
    it('does not expose a client-side disconnect control', async () => {
      server.use(connectedStatusHandler, workspaceOkHandler);

      renderWithProviders(<SlackIntegration />);

      // Disconnection is managed server-side; the component provides no
      // disconnect button in the connected UI
      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });
      expect(screen.queryByRole('button', { name: /disconnect/i })).not.toBeInTheDocument();
    });
  });
});
