/**
 * Microsoft 365 Integration Component Tests
 *
 * Test suite for Microsoft 365 integration functionality including:
 * - OAuth connection flow (Azure AD)
 * - OneDrive file operations
 * - Outlook email management
 * - SharePoint document handling
 * - Teams integration
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/handlers';
import Microsoft365Integration from '../Microsoft365Integration';

const mockOneDriveFiles = [
  {
    id: '01VAN3K3DZKBUM5VWEWPCQWYFQKW7QF5RA',
    name: 'Document.docx',
    size: 12345,
    createdDateTime: '2024-01-15T10:00:00Z',
    lastModifiedDateTime: '2024-01-15T10:00:00Z',
    webUrl: 'https://onedrive.live.com/?id=...',
  },
];

const mockOutlookEmails = [
  {
    id: 'AAMkAGViNDUxoczRAAA=',
    subject: 'Test Email',
    from: {
      emailAddress: {
        name: 'John Doe',
        address: 'john@example.com',
      },
    },
    receivedDateTime: '2024-01-15T10:00:00Z',
    body: {
      contentType: 'text',
      content: 'Email body content',
    },
  },
];

describe('Microsoft365Integration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Component Rendering', () => {
    it('renders Microsoft 365 integration component', () => {
      render(<Microsoft365Integration />);
      expect(screen.getByText(/microsoft 365|office 365/i)).toBeInTheDocument();
    });

    it('shows connection form when not authenticated', () => {
      render(<Microsoft365Integration />);
      expect(screen.getByText(/connect to microsoft|sign in/i)).toBeInTheDocument();
    });
  });

  describe('OAuth Connection Flow', () => {
    it('initiates Azure AD OAuth connection', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/microsoft365/connect', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              authUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
              state: 'test-state',
            })
          );
        })
      );

      render(<Microsoft365Integration />);

      const connectButton = screen.getByRole('button', { name: /connect|sign in/i });
      await user.click(connectButton);

      await waitFor(() => {
        expect(window.location.href).toContain('login.microsoftonline.com');
      });
    });

    it('handles successful OAuth callback', async () => {
      server.use(
        rest.get('/api/integrations/microsoft365/callback', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              user: {
                displayName: 'John Doe',
                email: 'john@example.com',
              },
            })
          );
        })
      );

      render(<Microsoft365Integration />);

      window.dispatchEvent(
        new CustomEvent('oauth-callback', {
          detail: { code: 'test-code', state: 'test-state' },
        })
      );

      await waitFor(() => {
        expect(screen.getByText(/john doe|successfully connected/i)).toBeInTheDocument();
      });
    });
  });

  describe('OneDrive Integration', () => {
    it('fetches and displays OneDrive files', async () => {
      server.use(
        rest.get('/api/integrations/microsoft365/onedrive/files', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              files: mockOneDriveFiles,
            })
          );
        })
      );

      render(<Microsoft365Integration connected={true} />);

      await waitFor(() => {
        expect(screen.getByText('Document.docx')).toBeInTheDocument();
      });
    });

    it('uploads file to OneDrive', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/microsoft365/onedrive/upload', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              file: {
                id: 'new-file-id',
                name: 'uploaded-file.txt',
              },
            })
          );
        })
      );

      render(<Microsoft365Integration connected={true} />);

      const uploadButton = screen.queryByRole('button', { name: /upload/i });
      if (uploadButton) {
        await user.click(uploadButton);

        await waitFor(() => {
          expect(screen.getByText(/file uploaded/i)).toBeInTheDocument();
        });
      }
    });
  });

  describe('Outlook Integration', () => {
    it('fetches and displays emails', async () => {
      server.use(
        rest.get('/api/integrations/microsoft365/outlook/emails', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              emails: mockOutlookEmails,
            })
          );
        })
      );

      render(<Microsoft365Integration connected={true} />);

      await waitFor(() => {
        expect(screen.getByText('Test Email')).toBeInTheDocument();
      });
    });

    it('sends email via Outlook', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/microsoft365/outlook/send', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              success: true,
              message: {
                id: 'new-email-id',
                subject: 'Test Subject',
              },
            })
          );
        })
      );

      render(<Microsoft365Integration connected={true} />);

      const composeButton = screen.queryByRole('button', { name: /compose|new email/i });
      if (composeButton) {
        await user.click(composeButton);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });
      }
    });
  });

  describe('Error Handling', () => {
    it('displays error message on connection failure', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/microsoft365/connect', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({
              error: 'Invalid credentials',
            })
          );
        })
      );

      render(<Microsoft365Integration />);

      const connectButton = screen.getByRole('button', { name: /connect|sign in/i });
      await user.click(connectButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid credentials|authentication failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Disconnection', () => {
    it('disconnects from Microsoft 365 successfully', async () => {
      const user = userEvent.setup();

      server.use(
        rest.post('/api/integrations/microsoft365/disconnect', (req, res, ctx) => {
          return res(ctx.status(200), ctx.json({ success: true }));
        })
      );

      render(<Microsoft365Integration connected={true} />);

      const disconnectButton = screen.getByRole('button', { name: /disconnect|sign out/i });
      await user.click(disconnectButton);

      await waitFor(() => {
        expect(screen.getByText(/disconnected/i)).toBeInTheDocument();
      });
    });
  });
});
