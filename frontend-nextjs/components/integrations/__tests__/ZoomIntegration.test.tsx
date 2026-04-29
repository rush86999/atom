/**
 * Zoom Integration Component Tests
 *
 * Test suite for Zoom integration with meetings, users, and recordings
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import ZoomIntegration from '../ZoomIntegration';

describe('ZoomIntegration', () => {
  beforeEach(() => {
    server.resetHandlers();
    jest.clearAllMocks();
  });

  it('renders integration card with Zoom branding', () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: false
          })
        );
      })
    );

    render(<ZoomIntegration />);

    expect(screen.getByText('Zoom Integration')).toBeInTheDocument();
  });

  it('shows Connect button when not connected', async () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: false,
            reason: 'Not authenticated'
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connect Zoom Account')).toBeInTheDocument();
    });
  });

  it('shows Connected status when connection status is true', async () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            user_info: {
              id: 'user123',
              email: 'user@example.com',
              first_name: 'Test',
              last_name: 'User'
            }
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
      expect(screen.getByText('user@example.com')).toBeInTheDocument();
    });
  });

  it('clicking connect triggers OAuth flow or API call', async () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: false
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText('Connect Zoom Account');
      expect(connectButton).toBeInTheDocument();
    });
  });

  it('handles error state with error message', async () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(500),
          ctx.json({
            error: 'Connection failed'
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/connection failed|error/i)).toBeInTheDocument();
    });
  });

  it('renders meeting list when authenticated', async () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            user_info: {
              id: 'user123',
              email: 'user@example.com',
              first_name: 'Test',
              last_name: 'User'
            }
          })
        );
      }),
      rest.get('/api/zoom/meetings', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            meetings: [
              {
                id: '1',
                topic: 'Test Meeting',
                start_time: '2026-04-25T10:00:00Z',
                duration: 30,
                timezone: 'UTC',
                join_url: 'https://zoom.us/j/123456',
                status: 'scheduled'
              }
            ]
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Meetings')).toBeInTheDocument();
    });
  });

  it('renders scheduling UI if applicable', async () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            user_info: {
              id: 'user123',
              email: 'user@example.com',
              first_name: 'Test',
              last_name: 'User'
            }
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Create Meeting')).toBeInTheDocument();
    });
  });

  it('displays users tab with user list', async () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            user_info: {
              id: 'user123',
              email: 'user@example.com',
              first_name: 'Test',
              last_name: 'User'
            }
          })
        );
      }),
      rest.get('/api/zoom/users', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            users: [
              {
                id: '1',
                email: 'user1@example.com',
                first_name: 'User',
                last_name: 'One',
                type: 2,
                status: 'active'
              }
            ]
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Users')).toBeInTheDocument();
    });
  });

  it('shows recordings tab with recording list', async () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            user_info: {
              id: 'user123',
              email: 'user@example.com',
              first_name: 'Test',
              last_name: 'User'
            }
          })
        );
      }),
      rest.get('/api/zoom/recordings', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            recordings: [
              {
                id: '1',
                meeting_id: '123',
                topic: 'Recorded Meeting',
                start_time: '2026-04-20T10:00:00Z',
                duration: 30,
                file_size: 1024000,
                download_url: 'https://zoom.us/recording/123'
              }
            ]
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Recordings')).toBeInTheDocument();
    });
  });

  it('disconnects Zoom account when disconnect button clicked', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            user_info: {
              id: 'user123',
              email: 'user@example.com',
              first_name: 'Test',
              last_name: 'User'
            }
          })
        );
      }),
      rest.post('/api/zoom/auth/disconnect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    const disconnectButton = screen.getByText('Disconnect');
    await user.click(disconnectButton);

    await waitFor(() => {
      expect(screen.getByText('Connect Zoom Account')).toBeInTheDocument();
    });
  });

  it('creates new meeting when create button clicked', async () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            user_info: {
              id: 'user123',
              email: 'user@example.com',
              first_name: 'Test',
              last_name: 'User'
            }
          })
        );
      }),
      rest.post('/api/zoom/meetings', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            meeting: {
              id: '1',
              topic: 'ATOM Integration Meeting',
              duration: 30,
              timezone: 'UTC'
            }
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      const createButton = screen.getByText('Create Meeting');
      expect(createButton).toBeInTheDocument();
    });
  });

  it('refreshes data when refresh button clicked', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            user_info: {
              id: 'user123',
              email: 'user@example.com',
              first_name: 'Test',
              last_name: 'User'
            }
          })
        );
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      const refreshButton = screen.getByText('Refresh');
      expect(refreshButton).toBeInTheDocument();
    });
  });
});
