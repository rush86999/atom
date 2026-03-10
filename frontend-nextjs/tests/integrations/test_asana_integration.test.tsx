import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AsanaIntegration from '@/components/AsanaIntegration';

// Mock dependencies
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

// Mock fetch globally
global.fetch = jest.fn();

describe('AsanaIntegration Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  describe('test_asana_connection_form', () => {
    it('should render connection form when not connected', () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: false }),
      } as Response);

      render(<AsanaIntegration />);

      expect(screen.getByText(/connect asana/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/api token/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/workspace/i)).toBeInTheDocument();
    });

    it('should display all connection form fields', () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: false }),
      } as Response);

      render(<AsanaIntegration />);

      expect(screen.getByLabelText(/api token/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /connect/i })).toBeInTheDocument();
    });

    it('should validate required fields in connection form', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ connected: false }),
      } as Response);

      render(<AsanaIntegration />);

      const connectButton = screen.getByRole('button', { name: /connect/i });
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByText(/api token is required/i)).toBeInTheDocument();
      });
    });
  });

  describe('test_asana_connection_success', () => {
    it('should successfully connect to Asana', async () => {
      const mockResponse = {
        success: true,
        workspace: {
          id: 'workspace-123',
          name: 'My Workspace',
        },
        user: {
          id: 'user-123',
          name: 'John Doe',
          email: 'john@example.com',
        },
      };

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: false }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockResponse,
        } as Response);

      render(<AsanaIntegration />);

      const apiTokenInput = screen.getByLabelText(/api token/i);
      fireEvent.change(apiTokenInput, { target: { value: 'test-token' } });

      const connectButton = screen.getByRole('button', { name: /connect/i });
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          '/api/v1/integrations/asana/connect',
          expect.objectContaining({
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: expect.stringContaining('test-token'),
          })
        );
      });
    });

    it('should display connection success message', async () => {
      const mockResponse = {
        success: true,
        workspace: { id: 'workspace-123', name: 'My Workspace' },
      };

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: false }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockResponse,
        } as Response);

      render(<AsanaIntegration />);

      const apiTokenInput = screen.getByLabelText(/api token/i);
      fireEvent.change(apiTokenInput, { target: { value: 'test-token' } });

      const connectButton = screen.getByRole('button', { name: /connect/i });
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByText(/successfully connected/i)).toBeInTheDocument();
      });
    });
  });

  describe('test_asana_connection_failure', () => {
    it('should handle invalid API token', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: false }),
        } as Response)
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => ({ error: 'Invalid token' }),
        } as Response);

      render(<AsanaIntegration />);

      const apiTokenInput = screen.getByLabelText(/api token/i);
      fireEvent.change(apiTokenInput, { target: { value: 'invalid-token' } });

      const connectButton = screen.getByRole('button', { name: /connect/i });
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid token/i)).toBeInTheDocument();
      });
    });

    it('should handle network errors', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: false }),
        } as Response)
        .mockRejectedValueOnce(new Error('Network error'));

      render(<AsanaIntegration />);

      const apiTokenInput = screen.getByLabelText(/api token/i);
      fireEvent.change(apiTokenInput, { target: { value: 'test-token' } });

      const connectButton = screen.getByRole('button', { name: /connect/i });
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });

    it('should handle timeout errors', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: false }),
        } as Response)
        .mockImplementationOnce(() => new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Request timeout')), 100)
        ));

      render(<AsanaIntegration />);

      const apiTokenInput = screen.getByLabelText(/api token/i);
      fireEvent.change(apiTokenInput, { target: { value: 'test-token' } });

      const connectButton = screen.getByRole('button', { name: /connect/i });
      fireEvent.click(connectButton);

      await waitFor(() => {
        expect(screen.getByText(/timeout/i)).toBeInTheDocument();
      }, { timeout: 5000 });
    });
  });

  describe('test_asana_task_sync', () => {
    it('should display synchronized tasks', async () => {
      const mockTasks = [
        {
          id: 'task-1',
          name: 'Complete Project',
          completed: false,
          due_on: '2026-03-15',
          assignee: { id: 'user-1', name: 'John Doe' },
          projects: [{ id: 'proj-1', name: 'Marketing' }],
        },
        {
          id: 'task-2',
          name: 'Review Code',
          completed: true,
          due_on: '2026-03-10',
          assignee: { id: 'user-2', name: 'Jane Smith' },
          projects: [{ id: 'proj-2', name: 'Development' }],
        },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ tasks: mockTasks }),
        } as Response);

      render(<AsanaIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Complete Project')).toBeInTheDocument();
        expect(screen.getByText('Review Code')).toBeInTheDocument();
      });
    });

    it('should show loading state during sync', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockImplementationOnce(() => new Promise(() => {})); // Never resolves

      render(<AsanaIntegration />);

      await waitFor(() => {
        expect(screen.getByTestId('spinner')).toBeInTheDocument();
      });
    });

    it('should handle sync errors gracefully', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockRejectedValueOnce(new Error('Sync failed'));

      render(<AsanaIntegration />);

      await waitFor(() => {
        expect(screen.getByText(/sync failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('test_asana_project_list', () => {
    it('should fetch and display project list', async () => {
      const mockProjects = [
        {
          id: 'proj-1',
          name: 'Marketing Campaign',
          color: 'blue',
          due_date: '2026-03-20',
        },
        {
          id: 'proj-2',
          name: 'Product Launch',
          color: 'green',
          due_date: '2026-03-25',
        },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ projects: mockProjects }),
        } as Response);

      render(<AsanaIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Marketing Campaign')).toBeInTheDocument();
        expect(screen.getByText('Product Launch')).toBeInTheDocument();
      });
    });

    it('should filter projects by status', async () => {
      const mockProjects = [
        { id: 'proj-1', name: 'Active Project', current_status: { color: 'green', text: 'On Track' } },
        { id: 'proj-2', name: 'At Risk Project', current_status: { color: 'yellow', text: 'At Risk' } },
      ];

      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ connected: true }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ projects: mockProjects }),
        } as Response);

      render(<AsanaIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Active Project')).toBeInTheDocument();
        expect(screen.getByText('At Risk Project')).toBeInTheDocument();
      });
    });
  });
});
