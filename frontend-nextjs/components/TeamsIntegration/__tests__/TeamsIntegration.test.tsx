/**
 * TeamsIntegration Component Tests
 *
 * Tests verify Microsoft Teams integration connection,
 * channel management, and message handling.
 *
 * Source: components/TeamsIntegration.tsx (266 lines uncovered)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { TeamsIntegration } from '../TeamsIntegration';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  rest.get('/api/integrations/teams/status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        connected: false,
        channels: [],
      })
    );
  }),

  rest.post('/api/integrations/teams/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        channels: [
          { id: '1', name: 'General' },
          { id: '2', name: 'Projects' },
        ],
      })
    );
  }),

  rest.post('/api/integrations/teams/disconnect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true })
    );
  }),

  rest.post('/api/integrations/teams/send-message', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true })
    );
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('TeamsIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<TeamsIntegration />);

    expect(screen.getByText(/teams integration/i)).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    render(<TeamsIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/connect/i)).toBeInTheDocument();
    });
  });

  // Test 3: handles connection flow
  test('handles connection flow', async () => {
    render(<TeamsIntegration />);

    const connectButton = screen.getByText(/connect/i);
    fireEvent.click(connectButton);

    await waitFor(() => {
      expect(screen.getByText(/general/i)).toBeInTheDocument();
    });
  });

  // Test 4: displays channels after connection
  test('displays channels after connection', async () => {
    render(<TeamsIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    await waitFor(() => {
      expect(screen.getByText('General')).toBeInTheDocument();
      expect(screen.getByText('Projects')).toBeInTheDocument();
    });
  });

  // Test 5: handles disconnect action
  test('handles disconnect action', async () => {
    render(<TeamsIntegration />);

    // Connect first
    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    // Then disconnect
    await waitFor(() => {
      const disconnectButton = screen.getByText(/disconnect/i);
      fireEvent.click(disconnectButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/connect/i)).toBeInTheDocument();
    });
  });

  // Test 6: sends message to channel
  test('sends message to channel', async () => {
    render(<TeamsIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    await waitFor(() => {
      const messageInput = screen.getByPlaceholderText(/type a message/i);
      fireEvent.change(messageInput, { target: { value: 'Test message' } });

      const sendButton = screen.getByText(/send/i);
      fireEvent.click(sendButton);
    });
  });

  // Test 7: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.post('/api/integrations/teams/connect', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<TeamsIntegration />);

    const connectButton = screen.getByText(/connect/i);
    fireEvent.click(connectButton);

    await waitFor(() => {
      expect(screen.getByText(/connection failed/i)).toBeInTheDocument();
    });
  });

  // Test 8: displays loading state during connection
  test('displays loading state during connection', async () => {
    server.use(
      rest.post('/api/integrations/teams/connect', (req, res, ctx) => {
        return res(
          ctx.delay(100),
          ctx.json({ success: true })
        );
      })
    );

    render(<TeamsIntegration />);

    const connectButton = screen.getByText(/connect/i);
    fireEvent.click(connectButton);

    expect(screen.getByText(/connecting/i)).toBeInTheDocument();
  });

  // Test 9: validates channel selection
  test('validates channel selection', async () => {
    render(<TeamsIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    await waitFor(() => {
      const channelSelect = screen.getByRole('combobox');
      expect(channelSelect).toBeInTheDocument();
    });
  });

  // Test 10: handles message send error
  test('handles message send error', async () => {
    server.use(
      rest.post('/api/integrations/teams/send-message', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<TeamsIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    await waitFor(() => {
      const messageInput = screen.getByPlaceholderText(/type a message/i);
      fireEvent.change(messageInput, { target: { value: 'Test' } });

      const sendButton = screen.getByText(/send/i);
      fireEvent.click(sendButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/failed to send/i)).toBeInTheDocument();
    });
  });
});
