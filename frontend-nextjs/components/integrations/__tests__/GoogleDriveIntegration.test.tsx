/**
 * GoogleDriveIntegration Component Tests
 *
 * Tests verify the real Google Drive integration component:
 * - Connection status check (GET /api/gdrive/connection-status)
 * - Disconnected / connect state
 * - File and folder browsing (GET /api/gdrive/list-files)
 * - Disconnect flow
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/integrations/GoogleDriveIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GoogleDriveIntegration from '@/components/integrations/GoogleDriveIntegration';
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const connectedStatus = {
  isConnected: true,
  email: 'rushi@example.com',
};

const gdriveHandlers = [
  rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(connectedStatus));
  }),

  rest.get('/api/gdrive/list-files', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        files: [
          {
            id: 'f1',
            name: 'Projects',
            isFolder: true,
            mimeType: 'application/vnd.google-apps.folder',
            modifiedTime: '2024-01-15T10:00:00Z',
            size: 0,
            webViewLink: '',
          },
          {
            id: 'f2',
            name: 'deck.pdf',
            isFolder: false,
            mimeType: 'application/pdf',
            modifiedTime: '2024-01-14T10:00:00Z',
            size: 2097152,
            webViewLink: 'https://drive.google.com/f2',
          },
        ],
        nextPageToken: null,
      })
    );
  }),

  rest.post('/api/auth/gdrive/disconnect', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

const setNotConnected = () => {
  server.use(
    rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ isConnected: false, reason: 'Not connected' }));
    })
  );
};

describe('GoogleDriveIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...gdriveHandlers);
  });

  // Test 1: renders component
  test('renders component', async () => {
    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /google drive integration/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setNotConnected();

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect google drive/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setNotConnected();

    render(<GoogleDriveIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect google drive/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when connection status is healthy
  test('shows connected state when connection status is healthy', async () => {
    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays files and folders after connection
  test('displays files and folders after connection', async () => {
    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument();
      expect(screen.getByText('deck.pdf')).toBeInTheDocument();
    });
  });

  // Test 6: handles connection error as disconnected
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect google drive/i })
      ).toBeInTheDocument();
    });
  });

  // Test 7: disconnect button is clickable without crashing
  test('disconnect button is clickable without crashing', async () => {
    render(<GoogleDriveIntegration />);

    const disconnectButton = await screen.findByRole('button', {
      name: /disconnect google drive/i,
    });
    expect(() => fireEvent.click(disconnectButton)).not.toThrow();
  });

  // Test 8: shows loading state while the connection status is pending
  test('shows loading state while connection status is pending', async () => {
    let resolveStatus: (value: any) => void;
    let statusRes: any;
    let statusCtx: any;
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        statusRes = res;
        statusCtx = ctx;
        return new Promise((resolve) => {
          resolveStatus = resolve;
        });
      })
    );

    render(<GoogleDriveIntegration />);

    expect(
      screen.getByText(/loading google drive integration/i)
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(statusRes).toBeDefined();
    });
    resolveStatus!(statusRes(statusCtx.status(200), statusCtx.json(connectedStatus)));

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 9: shows files loading spinner before the file list arrives
  test('shows files loading state while the file list is pending', async () => {
    let resolveFiles: (value: any) => void;
    let filesRes: any;
    let filesCtx: any;
    server.use(
      rest.get('/api/gdrive/list-files', (req, res, ctx) => {
        filesRes = res;
        filesCtx = ctx;
        return new Promise((resolve) => {
          resolveFiles = resolve;
        });
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/loading files/i)).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(filesRes).toBeDefined();
    });
    resolveFiles!(
      filesRes(
        filesCtx.status(200),
        filesCtx.json({
          files: [{ id: 'f1', name: 'notes.txt', isFolder: false, mimeType: 'text/plain', size: 10 }],
          nextPageToken: undefined,
        })
      )
    );

    await waitFor(() => {
      expect(screen.getByText('notes.txt')).toBeInTheDocument();
    });
  });

  // Test 10: shows empty state when the folder has no files
  test('shows empty state when the folder has no files', async () => {
    server.use(
      rest.get('/api/gdrive/list-files', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ files: [], nextPageToken: null }))
      )
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/no files found in this folder/i)).toBeInTheDocument();
    });
  });

  // Test 11: clicking a folder navigates into it and updates the breadcrumb
  test('clicking a folder navigates into it and updates the breadcrumb', async () => {
    server.use(
      rest.get('/api/gdrive/list-files', (req, res, ctx) => {
        const folderId = req.url.searchParams.get('folder_id');
        if (folderId === 'f1') {
          return res(
            ctx.status(200),
            ctx.json({
              files: [
                { id: 'f3', name: 'deep.pdf', isFolder: false, mimeType: 'application/pdf', size: 100 },
                { id: 'f4', name: 'Sub', isFolder: true, mimeType: 'application/vnd.google-apps.folder' },
              ],
              nextPageToken: null,
            })
          );
        }
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              { id: 'f1', name: 'Projects', isFolder: true, mimeType: 'application/vnd.google-apps.folder' },
            ],
            nextPageToken: null,
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Projects'));

    await waitFor(() => {
      expect(screen.getByText('deep.pdf')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Projects' })).toBeInTheDocument();
  });

  // Test 12: breadcrumb click navigates back to the root folder
  test('breadcrumb click navigates back to the root folder', async () => {
    server.use(
      rest.get('/api/gdrive/list-files', (req, res, ctx) => {
        const folderId = req.url.searchParams.get('folder_id');
        if (folderId === 'f1') {
          return res(
            ctx.status(200),
            ctx.json({
              files: [
                { id: 'f3', name: 'deep.pdf', isFolder: false, mimeType: 'application/pdf', size: 100 },
              ],
              nextPageToken: null,
            })
          );
        }
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              { id: 'f1', name: 'Projects', isFolder: true, mimeType: 'application/vnd.google-apps.folder' },
            ],
            nextPageToken: null,
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Projects'));
    await waitFor(() => {
      expect(screen.getByText('deep.pdf')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'My Drive' }));

    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument();
    });
    expect(screen.queryByText('deep.pdf')).not.toBeInTheDocument();
  });

  // Test 13: open-file button opens the webViewLink in a new tab
  test('open-file button opens the webViewLink in a new tab', async () => {
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('deck.pdf')).toBeInTheDocument();
    });
    fireEvent.click(screen.getAllByRole('button', { name: '' })[0]);

    expect(openSpy).toHaveBeenCalledWith('https://drive.google.com/f2', '_blank');
  });

  // Test 14: ingest button posts the file to the search index
  test('ingest button posts the file to the search index', async () => {
    const ingestHandler = jest.fn();
    server.use(
      rest.post('/api/ingest-gdrive-document', (req, res, ctx) => {
        ingestHandler(req.body);
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('deck.pdf')).toBeInTheDocument();
    });
    fireEvent.click(screen.getAllByRole('button', { name: '' })[1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'File Ingested',
        description: 'deck.pdf has been added to search index',
      });
    });
    expect(ingestHandler).toHaveBeenCalledWith(
      expect.objectContaining({ file_id: 'f2', metadata: expect.objectContaining({ name: 'deck.pdf' }) })
    );
  });

  // Test 15: ingest failure shows an error toast
  test('ingest failure shows an error toast', async () => {
    server.use(
      rest.post('/api/ingest-gdrive-document', (req, res, ctx) => res(ctx.status(500)))
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('deck.pdf')).toBeInTheDocument();
    });
    fireEvent.click(screen.getAllByRole('button', { name: '' })[1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Error',
        description: 'Failed to ingest file',
        variant: 'error',
      });
    });
  });

  // Test 16: load-more appends the next page of files
  test('load more appends the next page of files', async () => {
    server.use(
      rest.get('/api/gdrive/list-files', (req, res, ctx) => {
        const pageToken = req.url.searchParams.get('page_token');
        if (pageToken === 'tok1') {
          return res(
            ctx.status(200),
            ctx.json({
              files: [
                { id: 'f9', name: 'page2.txt', isFolder: false, mimeType: 'text/plain', size: 5 },
              ],
              nextPageToken: undefined,
            })
          );
        }
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              { id: 'f1', name: 'page1.txt', isFolder: false, mimeType: 'text/plain', size: 5 },
            ],
            nextPageToken: 'tok1',
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('page1.txt')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /load more files/i }));

    await waitFor(() => {
      expect(screen.getByText('page2.txt')).toBeInTheDocument();
    });
    expect(screen.getByText('page1.txt')).toBeInTheDocument();
  });

  // Test 17: file list error shows the error alert and clears the list
  test('file list error shows the error alert and clears the list', async () => {
    server.use(
      rest.get('/api/gdrive/list-files', (req, res, ctx) => res(ctx.status(500)))
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/failed to fetch files/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/no files found in this folder/i)).toBeInTheDocument();
  });

  // Test 18: connection check failure shows the error and disconnected state
  test('connection check failure shows the error and disconnected state', async () => {
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => res((ctx as any).networkError('boom')))
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /connect google drive/i })).toBeInTheDocument();
    });
    expect(screen.getByText(/connection failed/i)).toBeInTheDocument();
    expect(screen.queryByText(/files & folders/i)).not.toBeInTheDocument();
  });

  // Test 19: successful disconnect returns to the disconnected state
  test('successful disconnect returns to the disconnected state', async () => {
    let connected = true;
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ isConnected: connected, email: 'rushi@example.com' }))
      ),
      rest.post('/api/auth/gdrive/disconnect', (req, res, ctx) => {
        connected = false;
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /disconnect google drive/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /disconnect google drive/i }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Disconnected',
        description: 'Google Drive has been disconnected',
      });
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /connect google drive/i })).toBeInTheDocument();
    });
    expect(screen.queryByText(/files & folders/i)).not.toBeInTheDocument();
  });

  // Test 20: disconnect failure shows an error toast and stays connected
  test('disconnect failure shows an error toast and stays connected', async () => {
    server.use(
      rest.post('/api/auth/gdrive/disconnect', (req, res, ctx) => res(ctx.status(500)))
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /disconnect google drive/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /disconnect google drive/i }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Error',
        description: 'Failed to disconnect Google Drive',
        variant: 'error',
      });
    });
    expect(screen.getByText('Connected')).toBeInTheDocument();
  });

  // Test 21: renders file sizes, dates, and icons across mime types
  test('renders file sizes, dates, and icons across mime types', async () => {
    server.use(
      rest.get('/api/gdrive/list-files', (req, res, ctx) =>
        res(
          ctx.status(200),
          ctx.json({
            files: [
              { id: 'z1', name: 'zero.txt', isFolder: false, mimeType: 'text/plain', size: 0 },
              { id: 'z2', name: 'tiny.txt', isFolder: false, mimeType: 'text/plain', size: 512 },
              { id: 'z3', name: 'doc.doc', isFolder: false, mimeType: 'application/vnd.google-apps.document' },
              { id: 'z4', name: 'sheet.xls', isFolder: false, mimeType: 'application/vnd.google-apps.spreadsheet' },
              { id: 'z5', name: 'slides.ppt', isFolder: false, mimeType: 'application/vnd.google-apps.presentation' },
              { id: 'z6', name: 'pic.png', isFolder: false, mimeType: 'image/png', size: 5242880 },
              { id: 'z7', name: 'clip.mp4', isFolder: false, mimeType: 'video/mp4', size: 1073741824 },
              { id: 'z8', name: 'song.mp3', isFolder: false, mimeType: 'audio/mpeg' },
              { id: 'z9', name: 'blob.bin', isFolder: false, mimeType: 'application/octet-stream', size: 2048 },
              { id: 'z10', name: 'nodate.pdf', isFolder: false, mimeType: 'application/pdf' },
            ],
            nextPageToken: null,
          })
        )
      )
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('doc.doc')).toBeInTheDocument();
    });

    expect(screen.getByText('0 Bytes')).toBeInTheDocument();
    expect(screen.getByText('512 Bytes')).toBeInTheDocument();
    expect(screen.getByText('5 MB')).toBeInTheDocument();
    expect(screen.getByText('1 GB')).toBeInTheDocument();
    expect(screen.getByText('2 KB')).toBeInTheDocument();
    expect(screen.getAllByText('N/A').length).toBeGreaterThanOrEqual(2);
  });
});
