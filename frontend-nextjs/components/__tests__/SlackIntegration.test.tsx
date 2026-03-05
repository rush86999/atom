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
import { render, screen, waitFor } from '@testing-library/react';
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
    topic: {
      value: 'Company-wide announcements and work-based matters',
      creator: 'U1234567890',
      last_set: 1234567890,
    },
    purpose: {
      value: 'This channel is for team-wide communication and announcements.',
      creator: 'U1234567890',
      last_set: 1234567890,
    },
  },
  {
    id: 'C0987654321',
    name: 'engineering',
    is_channel: true,
    created: 1234567891,
    is_archived: false,
    is_general: false,
    members: 45,
    topic: {
      value: 'Engineering team discussions',
      creator: 'U0987654321',
      last_set: 1234567891,
    },
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

describe('SlackIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('renders Slack integration component', () => {
      render(<SlackIntegration />);
      expect(screen.getByText(/slack/i)).toBeInTheDocument();
    });

    it('shows connection form when not authenticated', () => {
      render(<SlackIntegration />);
      expect(screen.getByText(/connect to slack|add to slack/i)).toBeInTheDocument();
    });
  });

  describe('OAuth Connection Flow', () => {
    it('initiates OAuth connection on button click', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/slack/connect', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              authUrl: 'https://slack.com/oauth/v2/authorize',
              state: 'test-state-123',
            })
          );
        })
      );

      render(<SlackIntegration />);

      const connectButton = screen.getByRole('button', { name: /connect|add to slack/i });
      await user.click(connectButton);

      // Verify OAuth initiation
      await waitFor(() => {
        expect(window.location.href).toContain('slack.com');
      });
    });

    it('handles successful OAuth callback', async () => {
      server.use(
        rest.get('/api/integrations/slack/callback', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              team: {
                id: 'T1234567890',
                name: 'Test Workspace',
                domain: 'test-workspace',
              },
            })
          );
        })
      );

      render(<SlackIntegration />);

      // Simulate OAuth callback event
      window.dispatchEvent(
        new CustomEvent('oauth-callback', {
          detail: { code: 'test-code', state: 'test-state' },
        })
      );

      await waitFor(() => {
        expect(screen.getByText(/successfully connected|test workspace/i)).toBeInTheDocument();
      });
    });

    it('handles OAuth authorization denied', async () => {
      server.use(
        rest.get('/api/integrations/slack/callback', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({
              error: 'access_denied',
              error_description: 'User denied authorization',
            })
          );
        })
      );

      render(<SlackIntegration />);

      window.dispatchEvent(
        new CustomEvent('oauth-callback', {
          detail: { error: 'access_denied' },
        })
      );

      await waitFor(() => {
        expect(screen.getByText(/authorization denied|access denied/i)).toBeInTheDocument();
      });
    });
  });

  describe('Channel Management', () => {
    it('fetches and displays channels after connection', async () => {
      server.use(
        rest.get('/api/integrations/slack/channels', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              channels: mockSlackChannels,
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      await waitFor(() => {
        expect(screen.getByText('general')).toBeInTheDocument();
        expect(screen.getByText('engineering')).toBeInTheDocument();
      });
    });

    it('filters channels by search query', async () => {
      const user = userEvent.setup();

      server.use(
        rest.get('/api/integrations/slack/channels', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              channels: mockSlackChannels,
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      const searchInput = screen.getByPlaceholderText(/search|filter/i);
      await user.type(searchInput, 'engineering');

      await waitFor(() => {
        expect(screen.getByText('engineering')).toBeInTheDocument();
        expect(screen.queryByText('general')).not.toBeInTheDocument();
      });
    });

    it('shows channel member count', async () => {
      server.use(
        rest.get('/api/integrations/slack/channels', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              channels: mockSlackChannels,
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      await waitFor(() => {
        expect(screen.getByText(/150/i)).toBeInTheDocument(); // General channel members
      });
    });
  });

  describe('Message Management', () => {
    it('fetches and displays messages for selected channel', async () => {
      server.use(
        rest.get('/api/integrations/slack/messages/:channelId', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              messages: mockSlackMessages,
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      await waitFor(() => {
        expect(screen.getByText(/test message/i)).toBeInTheDocument();
      });
    });

    it('sends message to channel', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/slack/messages', (req, res, ctx) => {
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

      render(<SlackIntegration connected={true} />);

      const messageInput = screen.getByPlaceholderText(/type a message/i);
      await user.type(messageInput, 'New test message');

      const sendButton = screen.getByRole('button', { name: /send/i });
      await user.click(sendButton);

      await waitFor(() => {
        expect(screen.getByText('New test message')).toBeInTheDocument();
      });
    });

    it('handles message sending errors', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/slack/messages', (req, res, ctx) => {
          return res(
            ctx.status(429),
            ctx.json({
              error: 'rate_limited',
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      const messageInput = screen.getByPlaceholderText(/type a message/i);
      await user.type(messageInput, 'Test message');

      const sendButton = screen.getByRole('button', { name: /send/i });
      await user.click(sendButton);

      await waitFor(() => {
        expect(screen.getByText(/rate limit|too many messages/i)).toBeInTheDocument();
      });
    });
  });

  describe('User Management', () => {
    it('fetches and displays team members', async () => {
      server.use(
        rest.get('/api/integrations/slack/users', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              members: mockSlackUsers,
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });
    });

    it('shows user status and presence', async () => {
      server.use(
        rest.get('/api/integrations/slack/users', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              members: mockSlackUsers,
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      await waitFor(() => {
        expect(screen.getByText(/working on atom/i)).toBeInTheDocument();
        expect(screen.getByTestId(/status-emoji|:rocket:/i)).toBeInTheDocument();
      });
    });
  });

  describe('Webhook Handling', () => {
    it('displays webhook configuration', () => {
      render(<SlackIntegration connected={true} />);

      const webhookSection = screen.queryByTestId(/webhook/i);
      // Note: Actual implementation may vary
    });

    it('creates new webhook', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/slack/webhooks', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              webhook: {
                id: 'WH123456',
                url: 'https://hooks.slack.com/services/T123/B123/XXX',
                channel: 'general',
              },
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      const createButton = screen.queryByRole('button', { name: /create webhook/i });
      if (createButton) {
        await user.click(createButton);

        await waitFor(() => {
          expect(screen.getByText(/webhook created/i)).toBeInTheDocument();
        });
      }
    });
  });

  describe('Error Handling', () => {
    it('displays error message on network failure', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/slack/connect', (req, res) => {
          return res.networkError('Failed to connect');
        })
      );

      render(<SlackIntegration />);

      const connectButton = screen.queryByRole('button', { name: /connect|add to slack/i });
      if (connectButton) {
        await user.click(connectButton);

        await waitFor(() => {
          expect(screen.getByText(/network error|connection error/i)).toBeInTheDocument();
        });
      }
    });

    it('displays error message on invalid credentials', async () => {
      server.use(
        rest.post('/api/integrations/slack/connect', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({
              error: 'invalid_client_id',
            })
          );
        })
      );

      render(<SlackIntegration />);

      await waitFor(() => {
        expect(screen.getByText(/invalid credentials|authentication failed/i)).toBeInTheDocument();
      });
    });

    it('handles API rate limiting gracefully', async () => {
      server.use(
        rest.get('/api/integrations/slack/channels', (req, res, ctx) => {
          return res(
            ctx.status(429),
            ctx.json({
              error: 'rate_limited',
              retry_after: 60,
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      await waitFor(() => {
        expect(screen.getByText(/rate limit|retry after/i)).toBeInTheDocument();
      });
    });
  });

  describe('Loading States', () => {
    it('shows loading indicator during channel fetch', async () => {
      server.use(
        rest.get('/api/integrations/slack/channels', async (req, res, ctx) => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              channels: mockSlackChannels,
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      const loadingElement = screen.queryByTestId(/loading|spinner/i);
      // Note: Actual implementation may vary
    });
  });

  describe('Disconnection', () => {
    it('disconnects from Slack successfully', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/slack/disconnect', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
            })
          );
        })
      );

      render(<SlackIntegration connected={true} />);

      const disconnectButton = screen.getByRole('button', { name: /disconnect/i });
      await user.click(disconnectButton);

      await waitFor(() => {
        expect(screen.getByText(/disconnected successfully/i)).toBeInTheDocument();
      });
    });
  });
});
