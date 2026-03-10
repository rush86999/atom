import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AzureIntegration from '@/components/AzureIntegration';

// Mock dependencies
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

// Mock fetch globally
global.fetch = jest.fn();

describe('AzureIntegration Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  describe('test_azure_connection_form', () => {
    it('should render Azure AD connection form', () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: false }),
      } as Response);

      render(<AzureIntegration />);

      expect(screen.getByText(/connect azure ad/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/tenant id/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/client id/i)).toBeInTheDocument();
    });

    it('should display all required connection fields', () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: false }),
      } as Response);

      render(<AzureIntegration />);

      expect(screen.getByLabelText(/tenant id/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/client id/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/client secret/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /connect/i })).toBeInTheDocument();
    });

    it('should validate tenant ID format', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: false }),
      } as Response);

      render(<AzureIntegration />);

      const tenantInput = screen.getByLabelText(/tenant id/i);
      fireEvent.change(tenantInput, { target: { value: 'invalid-tenant' } });

      const connectButton = screen.getByRole('button', { name: /connect/i });
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid tenant id/i)).toBeInTheDocument();
      });
    });
  });

  describe('test_azure_oauth_flow', () => {
    it('should initiate OAuth flow', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: false }),
      } as Response);

      render(<AzureIntegration />);

      const oauthButton = screen.getByRole('button', { name: /sign in with azure/i });
      fireEvent.click(oauthButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/v1/integrations/azure/oauth/url',
          expect.objectContaining({
            method: 'GET',
          })
        );
      });
    });

    it('should redirect to Azure authorization URL', async () => {
      const mockAuthUrl = 'https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize';

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          connected: false,
          authUrl: mockAuthUrl,
        }),
      } as Response);

      render(<AzureIntegration />);

      const oauthButton = screen.getByRole('button', { name: /sign in with azure/i });
      fireEvent.click(oauthButton);

      await waitFor(() => {
        expect(screen.getByText(/redirecting to azure/i)).toBeInTheDocument();
      });
    });

    it('should handle OAuth callback with code', async () => {
      const mockTokenResponse = {
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        expires_in: 3600,
      };

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: false }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockTokenResponse,
        } as Response);

      render(<AzureIntegration />);

      // Simulate OAuth callback
      window.location.search = '?code=test-auth-code';

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/v1/integrations/azure/oauth/callback',
          expect.objectContaining({
            method: 'POST',
          })
        );
      });
    });

    it('should handle OAuth errors', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: false }),
      } as Response);

      render(<AzureIntegration />);

      // Simulate OAuth error callback
      window.location.search = '?error=access_denied';

      await waitFor(() => {
        expect(screen.getByText(/access denied/i)).toBeInTheDocument();
      });
    });
  });

  describe('test_azure_user_sync', () => {
    it('should display synchronized users', async () => {
      const mockUsers = [
        {
          id: 'user-1',
          displayName: 'John Doe',
          mail: 'john@example.com',
          userPrincipalName: 'john@example.com',
          department: 'Engineering',
        },
        {
          id: 'user-2',
          displayName: 'Jane Smith',
          mail: 'jane@example.com',
          userPrincipalName: 'jane@example.com',
          department: 'Marketing',
        },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ users: mockUsers }),
        } as Response);

      render(<AzureIntegration />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      });
    });

    it('should handle user sync pagination', async () => {
      const mockUsersPage1 = [
        { id: 'user-1', displayName: 'User 1', mail: 'user1@example.com' },
      ];

      const mockUsersPage2 = [
        { id: 'user-2', displayName: 'User 2', mail: 'user2@example.com' },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            users: mockUsersPage1,
            nextPage: '/api/v1/integrations/azure/users?page=2',
          }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ users: mockUsersPage2 }),
        } as Response);

      render(<AzureIntegration />);

      await waitFor(() => {
        expect(screen.getByText('User 1')).toBeInTheDocument();
        expect(screen.getByText('User 2')).toBeInTheDocument();
      });
    });

    it('should filter users by department', async () => {
      const mockUsers = [
        { id: 'user-1', displayName: 'John Doe', department: 'Engineering' },
        { id: 'user-2', displayName: 'Jane Smith', department: 'Marketing' },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ users: mockUsers }),
        } as Response);

      render(<AzureIntegration />);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });

      const filterButton = screen.getByRole('button', { name: /filter/i });
      fireEvent.click(filterButton);

      const departmentFilter = screen.getByLabelText(/department/i);
      fireEvent.change(departmentFilter, { target: { value: 'Engineering' } });

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
      });
    });
  });

  describe('test_azure_group_sync', () => {
    it('should display synchronized groups', async () => {
      const mockGroups = [
        {
          id: 'group-1',
          displayName: 'Engineering Team',
          description: 'All engineers',
          mailEnabled: true,
        },
        {
          id: 'group-2',
          displayName: 'Marketing Team',
          description: 'Marketing department',
          mailEnabled: true,
        },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ groups: mockGroups }),
        } as Response);

      render(<AzureIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Engineering Team')).toBeInTheDocument();
        expect(screen.getByText('Marketing Team')).toBeInTheDocument();
      });
    });

    it('should show group members', async () => {
      const mockMembers = [
        { id: 'user-1', displayName: 'John Doe' },
        { id: 'user-2', displayName: 'Jane Smith' },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ groups: [{ id: 'group-1', displayName: 'Team' }] }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ members: mockMembers }),
        } as Response);

      render(<AzureIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Team')).toBeInTheDocument();
      });

      const groupButton = screen.getByText('Team');
      fireEvent.click(groupButton);

      await waitFor(() => {
        expect(screen.getByText('John Doe')).toBeInTheDocument();
        expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      });
    });
  });

  describe('test_azure_disconnect', () => {
    it('should disconnect Azure AD successfully', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true }),
        } as Response);

      render(<AzureIntegration />);

      const disconnectButton = screen.getByRole('button', { name: /disconnect/i });
      fireEvent.click(disconnectButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/v1/integrations/azure/disconnect',
          expect.objectContaining({
            method: 'POST',
          })
        );
      });
    });

    it('should confirm disconnect action', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: true }),
      } as Response);

      render(<AzureIntegration />);

      const disconnectButton = screen.getByRole('button', { name: /disconnect/i });
      fireEvent.click(disconnectButton);

      await waitFor(() => {
        expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      });
    });

    it('should handle disconnect errors', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockRejectedValueOnce(new Error('Disconnect failed'));

      render(<AzureIntegration />);

      const disconnectButton = screen.getByRole('button', { name: /disconnect/i });
      fireEvent.click(disconnectButton);

      const confirmButton = screen.getByRole('button', { name: /confirm/i });
      fireEvent.click(confirmButton);

      await waitFor(() => {
        expect(screen.getByText(/disconnect failed/i)).toBeInTheDocument();
      });
    });
  });
});
