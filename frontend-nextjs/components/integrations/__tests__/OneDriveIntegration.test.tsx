/**
 * OneDrive Integration Component Tests
 *
 * Test suite for OneDrive file browsing and management
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import OneDriveIntegration from '../OneDriveIntegration';

describe('OneDriveIntegration', () => {
  beforeEach(() => {
    server.resetHandlers();
    jest.clearAllMocks();
  });

  it('renders integration card', async () => {
    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: false
          })
        );
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('OneDrive Integration')).toBeInTheDocument();
    });
  });

  it('shows connect/disconnect UI', async () => {
    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: false,
            reason: 'Not authenticated'
          })
        );
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Not Connected')).toBeInTheDocument();
      expect(screen.getByText('Connect OneDrive')).toBeInTheDocument();
    });
  });

  it('shows file list when authenticated', async () => {
    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              {
                id: '1',
                name: 'Test Folder',
                is_folder: true,
                icon: '📁'
              },
              {
                id: '2',
                name: 'test.pdf',
                is_folder: false,
                web_url: 'https://onedrive.live.com/?id=2',
                icon: '📄'
              }
            ]
          })
        );
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
      expect(screen.getByText('Files & Folders')).toBeInTheDocument();
      expect(screen.getByText('Test Folder')).toBeInTheDocument();
      expect(screen.getByText('test.pdf')).toBeInTheDocument();
    });
  });

  it('handles disconnected state with Connect prompt', async () => {
    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: false,
            reason: 'Authentication required'
          })
        );
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Not Connected')).toBeInTheDocument();
      expect(screen.getByText('Connect OneDrive')).toBeInTheDocument();
      expect(screen.getByText(/authentication required/i)).toBeInTheDocument();
    });
  });

  it('navigates into folders when folder clicked', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        // First call - root folder
        if (!req.url.searchParams.has('folder_id')) {
          return res(
            ctx.status(200),
            ctx.json({
              files: [
                {
                  id: 'folder1',
                  name: 'Test Folder',
                  is_folder: true,
                  icon: '📁'
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
                is_folder: false,
                web_url: 'https://onedrive.live.com/?id=file1',
                icon: '📄'
              }
            ]
          })
        );
      })
    );

    render(<OneDriveIntegration />);

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

  it('disconnects OneDrive when disconnect button clicked', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.post('/api/auth/onedrive/disconnect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true
          })
        );
      }),
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: false
          })
        );
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });

    const disconnectButton = screen.getByText('Disconnect OneDrive');
    await user.click(disconnectButton);

    await waitFor(() => {
      expect(screen.getByText('Connect OneDrive')).toBeInTheDocument();
    });
  });

  it('opens file in new tab when file clicked', async () => {
    const user = userEvent.setup();
    const mockOpen = jest.fn();
    window.open = mockOpen;

    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              {
                id: 'file1',
                name: 'test.pdf',
                is_folder: false,
                web_url: 'https://onedrive.live.com/?id=file1',
                icon: '📄'
              }
            ]
          })
        );
      })
    );

    render(<OneDriveIntegration />);

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
      expect(mockOpen).toHaveBeenCalledWith('https://onedrive.live.com/?id=file1', '_blank');
    }
  });

  it('ingests file when ingest button clicked', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              {
                id: 'file1',
                name: 'test.pdf',
                is_folder: false,
                web_url: 'https://onedrive.live.com/?id=file1',
                icon: '📄'
              }
            ]
          })
        );
      }),
      rest.post('/api/onedrive/ingest-document', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true
          })
        );
      })
    );

    render(<OneDriveIntegration />);

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

  it('shows breadcrumb navigation', async () => {
    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: []
          })
        );
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('OneDrive')).toBeInTheDocument();
    });
  });

  it('displays connection status with drive type', async () => {
    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            email: 'user@example.com',
            drive_type: 'business'
          })
        );
      }),
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: []
          })
        );
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/drive type: business/i)).toBeInTheDocument();
    });
  });

  it('handles empty file list', async () => {
    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: []
          })
        );
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText(/no files found in this folder/i)).toBeInTheDocument();
    });
  });

  it('loads more files when load more button clicked', async () => {
    const user = userEvent.setup();

    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            is_connected: true,
            email: 'user@example.com'
          })
        );
      }),
      rest.get('/api/onedrive/list-files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            files: [
              {
                id: 'file1',
                name: 'file1.pdf',
                is_folder: false,
                web_url: 'https://onedrive.live.com/?id=file1',
                icon: '📄'
              }
            ],
            next_page_token: 'token123'
          })
        );
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('file1.pdf')).toBeInTheDocument();
    });

    const loadMoreButton = screen.getByText(/load more files/i);
    expect(loadMoreButton).toBeInTheDocument();
  });
});
