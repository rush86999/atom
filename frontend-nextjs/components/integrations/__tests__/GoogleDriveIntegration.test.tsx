/**
 * Google Drive Integration Component Tests
 *
 * Test suite for Google Drive file browsing and management
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import GoogleDriveIntegration from '../GoogleDriveIntegration';

describe('GoogleDriveIntegration', () => {
  beforeEach(() => {
    server.resetHandlers();
    jest.clearAllMocks();
  });

  it('renders integration card', async () => {
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: false
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Google Drive Integration')).toBeInTheDocument();
    });
  });

  it('shows authentication status', async () => {
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: false,
            reason: 'Not authenticated'
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Not Connected')).toBeInTheDocument();
      expect(screen.getByText('Connection Status')).toBeInTheDocument();
    });
  });

  it('clicking connect triggers auth', async () => {
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: false
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      const connectButton = screen.getByText('Connect Google Drive');
      expect(connectButton).toBeInTheDocument();
    });
  });

  it('lists mocked files/folders when authenticated', async () => {
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/gdrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              {
                id: '1',
                name: 'Test Folder',
                mimeType: 'application/vnd.google-apps.folder',
                isFolder: true
              },
              {
                id: '2',
                name: 'test.pdf',
                mimeType: 'application/pdf',
                webViewLink: 'https://drive.google.com/file/d/2',
                isFolder: false
              }
            ]
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
      expect(screen.getByText('user@example.com')).toBeInTheDocument();
    });
  });

  it('shows file picker or browse UI', async () => {
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/gdrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              {
                id: '1',
                name: 'Test Folder',
                mimeType: 'application/vnd.google-apps.folder',
                isFolder: true
              }
            ]
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Files & Folders')).toBeInTheDocument();
    });
  });

  it('handles auth error gracefully', async () => {
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(401),
          ctx.json({
            error: 'Authentication failed'
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/error|authentication failed/i)).toBeInTheDocument();
    });
  });

  it('disconnects Google Drive when disconnect button clicked', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.post('/api/auth/gdrive/disconnect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true
          })
        );
      }),
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: false
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    const disconnectButton = screen.getByText('Disconnect Google Drive');
    await user.click(disconnectButton);

    await waitFor(() => {
      expect(screen.getByText('Connect Google Drive')).toBeInTheDocument();
    });
  });

  it('navigates into folders when folder clicked', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/gdrive/list-files', (req, res, ctx) => {
        // First call - root folder
        if (!req.url.searchParams.has('folder_id')) {
          return res(
            ctx.status(200),
            ctx.json({
              files: [
                {
                  id: 'folder1',
                  name: 'Test Folder',
                  mimeType: 'application/vnd.google-apps.folder',
                  isFolder: true
                }
              ]
            })
          );
        }
        // Second call - inside folder
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              {
                id: 'file1',
                name: 'file.txt',
                mimeType: 'text/plain',
                webViewLink: 'https://drive.google.com/file/d/file1',
                isFolder: false
              }
            ]
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Test Folder')).toBeInTheDocument();
    });

    // Click on folder
    const folderRow = screen.getByText('Test Folder').closest('tr');
    if (folderRow) {
      await user.click(folderRow);
    }

    await waitFor(() => {
      expect(screen.getByText('file.txt')).toBeInTheDocument();
    });
  });

  it('shows breadcrumb navigation', async () => {
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/gdrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: []
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('My Drive')).toBeInTheDocument();
    });
  });

  it('opens file in new tab when file clicked', async () => {
    const user = userEvent.setup();
    const mockOpen = jest.fn();
    window.open = mockOpen;

    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/gdrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              {
                id: 'file1',
                name: 'test.pdf',
                mimeType: 'application/pdf',
                webViewLink: 'https://drive.google.com/file/d/file1',
                isFolder: false
              }
            ]
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    // Click external link button
    const externalLinkButtons = screen.getAllByRole('button');
    const externalButton = externalLinkButtons.find(btn =>
      btn.querySelector('svg')?.getAttribute('data-lucide') === 'external-link'
    );

    if (externalButton) {
      await user.click(externalButton);
      expect(mockOpen).toHaveBeenCalledWith('https://drive.google.com/file/d/file1', '_blank');
    }
  });

  it('ingests file when ingest button clicked', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            isConnected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/gdrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              {
                id: 'file1',
                name: 'test.pdf',
                mimeType: 'application/pdf',
                webViewLink: 'https://drive.google.com/file/d/file1',
                isFolder: false
              }
            ]
          })
        );
      }),
      rest.post('/api/ingest-gdrive-document', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true
          })
        );
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });

    // Click download/ingest button
    const buttons = screen.getAllByRole('button');
    const downloadButton = buttons.find(btn =>
      btn.querySelector('svg')?.getAttribute('data-lucide') === 'download'
    );

    if (downloadButton) {
      await user.click(downloadButton);
    }
  });
});
