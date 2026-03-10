import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import Dashboard from '@/components/Dashboard';

// Mock dependencies
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

jest.mock('@/components/WorkflowAutomation', () => {
  return function MockWorkflowAutomation() {
    return <div data-testid="workflow-automation">Workflow Automation</div>;
  };
});

// Mock fetch globally
global.fetch = jest.fn();

describe('Dashboard Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('test_dashboard_renders', () => {
    it('should render dashboard without crashing', () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          calendar: [],
          tasks: [],
          messages: [],
          stats: {
            upcomingEvents: 0,
            overdueTasks: 0,
            unreadMessages: 0,
            completedTasks: 0,
          },
        }),
      } as Response);

      render(<Dashboard />);
      expect(screen.getByTestId('dashboard')).toBeInTheDocument();
    });
  });

  describe('test_dashboard_displays_widgets', () => {
    it('should display all dashboard widgets', async () => {
      const mockData = {
        calendar: [
          {
            id: '1',
            title: 'Team Meeting',
            start: new Date('2026-03-10T10:00:00'),
            end: new Date('2026-03-10T11:00:00'),
            status: 'confirmed' as const,
          },
        ],
        tasks: [
          {
            id: '1',
            title: 'Complete Project',
            dueDate: new Date('2026-03-11'),
            priority: 'high' as const,
            status: 'todo' as const,
          },
        ],
        messages: [
          {
            id: '1',
            platform: 'email' as const,
            from: 'john@example.com',
            subject: 'Project Update',
            preview: 'Here is the update...',
            timestamp: new Date('2026-03-09T09:00:00'),
            unread: true,
            priority: 'normal' as const,
          },
        ],
        stats: {
          upcomingEvents: 5,
          overdueTasks: 2,
          unreadMessages: 10,
          completedTasks: 15,
        },
      };

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockData,
      } as Response);

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('Team Meeting')).toBeInTheDocument();
        expect(screen.getByText('Complete Project')).toBeInTheDocument();
        expect(screen.getByText('Project Update')).toBeInTheDocument();
        expect(screen.getByTestId('workflow-automation')).toBeInTheDocument();
      });
    });

    it('should display stats cards', async () => {
      const mockData = {
        calendar: [],
        tasks: [],
        messages: [],
        stats: {
          upcomingEvents: 5,
          overdueTasks: 2,
          unreadMessages: 10,
          completedTasks: 15,
        },
      };

      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => mockData,
      } as Response);

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('5')).toBeInTheDocument(); // upcoming events
        expect(screen.getByText('2')).toBeInTheDocument(); // overdue tasks
        expect(screen.getByText('10')).toBeInTheDocument(); // unread messages
        expect(screen.getByText('15')).toBeInTheDocument(); // completed tasks
      });
    });
  });

  describe('test_dashboard_loading_state', () => {
    it('should show loading indicator while fetching data', () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<Dashboard />);
      expect(screen.getByTestId('spinner')).toBeInTheDocument();
    });

    it('should hide loading indicator after data loads', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          calendar: [],
          tasks: [],
          messages: [],
          stats: {
            upcomingEvents: 0,
            overdueTasks: 0,
            unreadMessages: 0,
            completedTasks: 0,
          },
        }),
      } as Response);

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.queryByTestId('spinner')).not.toBeInTheDocument();
      });
    });
  });

  describe('test_dashboard_error_state', () => {
    it('should display error boundary message on fetch failure', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValueOnce(
        new Error('Network error')
      );

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText(/error/i)).toBeInTheDocument();
      });

      consoleSpy.mockRestore();
    });

    it('should handle API error responses', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      } as Response);

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText(/error/i)).toBeInTheDocument();
      });
    });
  });

  describe('test_dashboard_navigation', () => {
    it('should navigate to different sections via tabs', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          calendar: [],
          tasks: [],
          messages: [],
          stats: {
            upcomingEvents: 0,
            overdueTasks: 0,
            unreadMessages: 0,
            completedTasks: 0,
          },
        }),
      } as Response);

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /calendar/i })).toBeInTheDocument();
      });

      const calendarTab = screen.getByRole('tab', { name: /calendar/i });
      fireEvent.click(calendarTab);

      await waitFor(() => {
        expect(calendarTab).toHaveAttribute('aria-selected', 'true');
      });
    });

    it('should navigate between dashboard sections', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          calendar: [],
          tasks: [],
          messages: [],
          stats: {
            upcomingEvents: 0,
            overdueTasks: 0,
            unreadMessages: 0,
            completedTasks: 0,
          },
        }),
      } as Response);

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByRole('tab', { name: /tasks/i })).toBeInTheDocument();
      });

      const tasksTab = screen.getByRole('tab', { name: /tasks/i });
      fireEvent.click(tasksTab);

      await waitFor(() => {
        expect(tasksTab).toHaveAttribute('aria-selected', 'true');
      });
    });
  });

  describe('test_dashboard_data_refresh', () => {
    it('should refresh data when refresh button is clicked', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            calendar: [],
            tasks: [],
            messages: [],
            stats: {
              upcomingEvents: 0,
              overdueTasks: 0,
              unreadMessages: 0,
              completedTasks: 0,
            },
          }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            calendar: [{ id: '2', title: 'New Event', start: new Date(), end: new Date(), status: 'confirmed' as const }],
            tasks: [],
            messages: [],
            stats: {
              upcomingEvents: 1,
              overdueTasks: 0,
              unreadMessages: 0,
              completedTasks: 0,
            },
          }),
        } as Response);

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
      });

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(2);
      });
    });

    it('should show refreshing state during refresh', async () => {
      (global.fetch as jest.MockedFunction<typeof fetch>)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            calendar: [],
            tasks: [],
            messages: [],
            stats: {
              upcomingEvents: 0,
              overdueTasks: 0,
              unreadMessages: 0,
              completedTasks: 0,
            },
          }),
        } as Response)
        .mockImplementationOnce(() => new Promise(() => {})); // Second call never resolves

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
      });

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(refreshButton).toBeDisabled();
      });
    });
  });
});
