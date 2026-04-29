/**
 * LinearIntegration Component Tests
 *
 * Tests verify Linear integration connection, issue management,
 * and team synchronization.
 *
 * Source: components/LinearIntegration.tsx (145 lines uncovered)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LinearIntegration } from '../LinearIntegration';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  rest.get('/api/integrations/linear/status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        connected: false,
        teams: [],
      })
    );
  }),

  rest.post('/api/integrations/linear/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        teams: [
          { id: '1', name: 'Engineering' },
          { id: '2', name: 'Design' },
        ],
      })
    );
  }),

  rest.post('/api/integrations/linear/disconnect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true })
    );
  }),

  rest.get('/api/integrations/linear/issues', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        issues: [
          { id: '1', title: 'Bug fix', status: 'Open' },
          { id: '2', title: 'Feature request', status: 'In Progress' },
        ],
      })
    );
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('LinearIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<LinearIntegration />);

    expect(screen.getByText(/linear integration/i)).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    render(<LinearIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/connect/i)).toBeInTheDocument();
    });
  });

  // Test 3: handles connection flow
  test('handles connection flow', async () => {
    render(<LinearIntegration />);

    const connectButton = screen.getByText(/connect/i);
    fireEvent.click(connectButton);

    await waitFor(() => {
      expect(screen.getByText(/engineering/i)).toBeInTheDocument();
    });
  });

  // Test 4: displays teams after connection
  test('displays teams after connection', async () => {
    render(<LinearIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument();
      expect(screen.getByText('Design')).toBeInTheDocument();
    });
  });

  // Test 5: loads issues from Linear
  test('loads issues from Linear', async () => {
    render(<LinearIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    await waitFor(() => {
      const issuesButton = screen.getByText(/load issues/i);
      fireEvent.click(issuesButton);
    });

    await waitFor(() => {
      expect(screen.getByText('Bug fix')).toBeInTheDocument();
      expect(screen.getByText('Feature request')).toBeInTheDocument();
    });
  });

  // Test 6: handles disconnect action
  test('handles disconnect action', async () => {
    render(<LinearIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    await waitFor(() => {
      const disconnectButton = screen.getByText(/disconnect/i);
      fireEvent.click(disconnectButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/connect/i)).toBeInTheDocument();
    });
  });

  // Test 7: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.post('/api/integrations/linear/connect', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<LinearIntegration />);

    const connectButton = screen.getByText(/connect/i);
    fireEvent.click(connectButton);

    await waitFor(() => {
      expect(screen.getByText(/connection failed/i)).toBeInTheDocument();
    });
  });

  // Test 8: filters issues by status
  test('filters issues by status', async () => {
    render(<LinearIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    await waitFor(() => {
      const issuesButton = screen.getByText(/load issues/i);
      fireEvent.click(issuesButton);
    });

    await waitFor(() => {
      const filterButton = screen.getByText(/filter/i);
      fireEvent.click(filterButton);
    });

    expect(screen.getByText('Open')).toBeInTheDocument();
  });

  // Test 9: creates new issue
  test('creates new issue', async () => {
    render(<LinearIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    const createButton = screen.getByText(/new issue/i);
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByText(/create issue/i)).toBeInTheDocument();
    });
  });

  // Test 10: handles issue creation error
  test('handles issue creation error', async () => {
    server.use(
      rest.post('/api/integrations/linear/create-issue', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<LinearIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText(/connect/i);
      fireEvent.click(connectButton);
    });

    const createButton = screen.getByText(/new issue/i);
    fireEvent.click(createButton);

    await waitFor(() => {
      const titleInput = screen.getByPlaceholderText(/title/i);
      fireEvent.change(titleInput, { target: { value: 'Test issue' } });

      const submitButton = screen.getByText(/create/i);
      fireEvent.click(submitButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/failed to create/i)).toBeInTheDocument();
    });
  });
});
