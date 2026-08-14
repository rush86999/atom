/**
 * OneDriveIntegration Component Tests
 *
 * Tests verify the real OneDrive integration component:
 * - Connection status check (GET /api/onedrive/connection-status)
 * - Disconnected / connect state
 * - File and folder browsing (GET /api/onedrive/list-files)
 * - Disconnect flow
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/integrations/OneDriveIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import OneDriveIntegration from '@/components/integrations/OneDriveIntegration';
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const connectedStatus = {
  is_connected: true,
  email: 'rushi@example.com',
  display_name: 'Rushi Parikh',
  drive_type: 'business',
};

const onedriveHandlers = [
  rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(connectedStatus));
  }),

  rest.get('/api/onedrive/list-files', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        files: [
          {
            id: 'f1',
            name: 'Marketing',
            is_folder: true,
            icon: '📁',
            modified_time: '2024-01-15T10:00:00Z',
            size: 0,
            web_url: '',
          },
          {
            id: 'f2',
            name: 'roadmap.pdf',
            is_folder: false,
            icon: '📄',
            modified_time: '2024-01-14T10:00:00Z',
            size: 1048576,
            web_url: 'https://onedrive.com/f2',
          },
        ],
        next_page_token: null,
      })
    );
  }),

  rest.post('/api/auth/onedrive/disconnect', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

const setNotConnected = () => {
  server.use(
    rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ is_connected: false, reason: 'Not connected' }));
    })
  );
};

describe('OneDriveIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...onedriveHandlers);
  });

  // Test 1: renders component
  test('renders component', async () => {
    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /onedrive integration/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setNotConnected();

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect onedrive/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setNotConnected();

    render(<OneDriveIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect onedrive/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when connection status is healthy
  test('shows connected state when connection status is healthy', async () => {
    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays files and folders after connection
  test('displays files and folders after connection', async () => {
    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Marketing')).toBeInTheDocument();
      expect(screen.getByText('roadmap.pdf')).toBeInTheDocument();
    });
  });

  // Test 6: handles connection error as disconnected
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect onedrive/i })
      ).toBeInTheDocument();
    });
  });

  // Test 7: disconnect button is clickable without crashing
  test('disconnect button is clickable without crashing', async () => {
    render(<OneDriveIntegration />);

    const disconnectButton = await screen.findByRole('button', {
      name: /disconnect onedrive/i,
    });
    expect(() => fireEvent.click(disconnectButton)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: navigation, ingest, pagination, disconnect, error paths
// ---------------------------------------------------------------------------
describe('OneDriveIntegration (extended coverage)', () => {
  let listCalls: string[];

  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    listCalls = [];
    server.use(...onedriveHandlers);
  });

  const settle = async (text: RegExp | string) => {
    await screen.findByText(text);
    await new Promise((r) => setTimeout(r, 50));
  };

  const getFileRow = (name: string) =>
    screen.getByText(name).closest('tr') as HTMLElement;

  test('clicking a folder navigates into it and updates the breadcrumb', async () => {
    server.use(
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        listCalls.push(req.url.searchParams.toString());
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              { id: 'folder-1', name: 'Projects', is_folder: true, icon: '📁', modified_time: '2024-01-15T10:00:00Z', size: 0, web_url: '' },
            ],
            next_page_token: null,
          })
        );
      })
    );

    render(<OneDriveIntegration />);
    await settle('Projects');

    fireEvent.click(screen.getByText('Projects'));

    await waitFor(() => {
      expect(listCalls.some((c) => c.includes('folder_id=folder-1'))).toBe(true);
    });
    // breadcrumb shows the folder name
    expect(screen.getByRole('button', { name: 'Projects' })).toBeInTheDocument();

    // navigate back to root via the breadcrumb
    fireEvent.click(screen.getByRole('button', { name: 'OneDrive' }));
    await waitFor(() => {
      const last = listCalls[listCalls.length - 1];
      expect(last.includes('folder_id')).toBe(false);
    });
  });

  test('clicking a file row and the open button open the web url', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<OneDriveIntegration />);
    await settle('roadmap.pdf');

    // The row itself only navigates for folders; files open via the
    // ExternalLink action button.
    fireEvent.click(screen.getByText('roadmap.pdf'));
    expect(openSpy).not.toHaveBeenCalled();

    const row = getFileRow('roadmap.pdf');
    const buttons = row.querySelectorAll('button');
    fireEvent.click(buttons[0]);
    expect(openSpy).toHaveBeenCalledWith('https://onedrive.com/f2', '_blank');
  });

  test('ingests a file and reports failures', async () => {
    server.use(
      rest.post('/api/onedrive/ingest-document', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<OneDriveIntegration />);
    await settle('roadmap.pdf');

    const row = getFileRow('roadmap.pdf');
    const buttons = row.querySelectorAll('button');
    fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'File Ingested',
          description: 'roadmap.pdf has been added to search index',
        })
      );
    });

    // failure path
    getToastMock().mockClear();
    server.use(
      rest.post('/api/onedrive/ingest-document', (req, res) =>
        res.networkError('boom')
      )
    );
    fireEvent.click(buttons[buttons.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to ingest file' })
      );
    });
  });

  test('appends the next page when Load More Files is clicked', async () => {
    let page = 0;
    server.use(
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        const token = req.url.searchParams.get('page_token');
        if (!token && page === 0) {
          page = 1;
          return res(
            ctx.status(200),
            ctx.json({
              files: [{ id: 'p1', name: 'first-page.txt', is_folder: false, icon: '📄', modified_time: '2024-01-15T10:00:00Z', size: 10, web_url: '' }],
              next_page_token: 'token-2',
            })
          );
        }
        return res(
          ctx.status(200),
          ctx.json({
            files: [{ id: 'p2', name: 'second-page.txt', is_folder: false, icon: '📄', modified_time: '2024-01-16T10:00:00Z', size: 20, web_url: '' }],
            next_page_token: null,
          })
        );
      })
    );

    render(<OneDriveIntegration />);
    await settle('first-page.txt');

    fireEvent.click(screen.getByRole('button', { name: /load more files/i }));

    expect(await screen.findByText('second-page.txt')).toBeInTheDocument();
    expect(screen.getByText('first-page.txt')).toBeInTheDocument();
    // Load More disappears once the token is exhausted
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /load more files/i })).not.toBeInTheDocument();
    });
  });

  test('disconnects successfully and resets the view', async () => {
    render(<OneDriveIntegration />);
    await settle('roadmap.pdf');

    fireEvent.click(screen.getByRole('button', { name: /disconnect onedrive/i }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Disconnected' })
      );
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /connect onedrive/i })).toBeInTheDocument();
    });
  });

  test('reports a disconnect failure', async () => {
    server.use(
      rest.post('/api/auth/onedrive/disconnect', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<OneDriveIntegration />);
    await settle('roadmap.pdf');

    fireEvent.click(screen.getByRole('button', { name: /disconnect onedrive/i }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to disconnect OneDrive',
        })
      );
    });
  });

  test('shows an error banner when listing files fails', async () => {
    server.use(
      rest.get('/api/onedrive/list-files', (req, res) => res.networkError('boom'))
    );

    render(<OneDriveIntegration />);

    // MSW network errors surface as "Failed to fetch"
    expect(await screen.findByText(/failed to fetch/i)).toBeInTheDocument();
    expect(screen.getByText('No files found in this folder')).toBeInTheDocument();
  });

  test('shows an empty state for folders without files', async () => {
    server.use(
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ files: [], next_page_token: null }));
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('No files found in this folder')).toBeInTheDocument();
    });
  });

  test('renders N/A for missing size and modified time', async () => {
    server.use(
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              { id: 'x1', name: 'mystery.bin', is_folder: false, icon: '📄', web_url: '' },
            ],
            next_page_token: null,
          })
        );
      })
    );

    render(<OneDriveIntegration />);
    await settle('mystery.bin');

    const row = getFileRow('mystery.bin');
    expect(row.textContent).toContain('N/A');
  });
});
