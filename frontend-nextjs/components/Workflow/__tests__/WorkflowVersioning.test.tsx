import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import { WorkflowVersioning } from '../WorkflowVersioning';

// Mock useToast hook
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

// Mock date-fns
jest.mock('date-fns', () => ({
  format: jest.fn((date, fmt) => '2024-01-01 12:00'),
}));

describe('WorkflowVersioning Component', () => {
  const mockWorkflowId = 'test-workflow-1';

  const mockVersion: WorkflowVersion = {
    workflow_id: mockWorkflowId,
    version: 'v1.0.0',
    version_type: 'major',
    change_type: 'breaking_change',
    created_at: '2024-01-01T12:00:00Z',
    created_by: 'user1',
    commit_message: 'Initial version',
    tags: ['stable', 'production'],
    parent_version: undefined,
    branch_name: 'main',
    checksum: 'abc123',
    is_active: true,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Mock fetch API
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({}),
        headers: new Headers(),
        status: 200,
        statusText: 'OK',
      } as Response)
    );
  });

  describe('Rendering', () => {
    it('renders without crashing', () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      expect(screen.getByText(/workflow versioning/i)).toBeInTheDocument();
    });

    it('displays workflow ID', () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      expect(screen.getByText(mockWorkflowId)).toBeInTheDocument();
    });

    it('shows version history tab by default', () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      expect(screen.getByRole('tab', { name: /history/i })).toBeInTheDocument();
    });

    it('displays all tabs', () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      expect(screen.getByRole('tab', { name: /history/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /compare/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /branches/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /metrics/i })).toBeInTheDocument();
    });
  });

  describe('Version History', () => {
    it('displays version list', async () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      await waitFor(() => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      });
    });

    it('shows version number and type', async () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      await waitFor(() => {
        expect(screen.getByText(/v1\.0\.0/i)).toBeInTheDocument();
        expect(screen.getByText(/major/i)).toBeInTheDocument();
      });
    });

    it('displays commit message', async () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      await waitFor(() => {
        expect(screen.getByText('Initial version')).toBeInTheDocument();
      });
    });

    it('shows creator information', async () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      await waitFor(() => {
        expect(screen.getByText('user1')).toBeInTheDocument();
      });
    });

    it('displays version tags', async () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      await waitFor(() => {
        expect(screen.getByText('stable')).toBeInTheDocument();
        expect(screen.getByText('production')).toBeInTheDocument();
      });
    });

    it('shows active version indicator', async () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      await waitFor(() => {
        expect(screen.getByText(/active/i)).toBeInTheDocument();
      });
    });
  });

  describe('Version Comparison', () => {
    it('switches to compare tab', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const compareTab = screen.getByRole('tab', { name: /compare/i });
      await user.click(compareTab);

      expect(screen.getByText(/compare versions/i)).toBeInTheDocument();
    });

    it('displays version selectors', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const compareTab = screen.getByRole('tab', { name: /compare/i });
      await user.click(compareTab);

      expect(screen.getByLabelText(/from version/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/to version/i)).toBeInTheDocument();
    });

    it('shows diff after selecting versions', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const compareTab = screen.getByRole('tab', { name: /compare/i });
      await user.click(compareTab);

      const fromSelect = screen.getByLabelText(/from version/i);
      const toSelect = screen.getByLabelText(/to version/i);

      await user.selectOptions(fromSelect, 'v1.0.0');
      await user.selectOptions(toSelect, 'v2.0.0');

      await waitFor(() => {
        expect(screen.getByText(/impact level/i)).toBeInTheDocument();
      });
    });

    it('displays structural changes', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const compareTab = screen.getByRole('tab', { name: /compare/i });
      await user.click(compareTab);

      await waitFor(() => {
        expect(screen.getByText(/structural changes/i)).toBeInTheDocument();
      });
    });
  });

  describe('Branch Management', () => {
    it('switches to branches tab', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const branchesTab = screen.getByRole('tab', { name: /branches/i });
      await user.click(branchesTab);

      expect(screen.getByText(/branch management/i)).toBeInTheDocument();
    });

    it('displays branch list', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const branchesTab = screen.getByRole('tab', { name: /branches/i });
      await user.click(branchesTab);

      await waitFor(() => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      });
    });

    it('opens create branch dialog', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const branchesTab = screen.getByRole('tab', { name: /branches/i });
      await user.click(branchesTab);

      const createButton = screen.getByRole('button', { name: /create branch/i });
      await user.click(createButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('shows protected branch indicator', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const branchesTab = screen.getByRole('tab', { name: /branches/i });
      await user.click(branchesTab);

      await waitFor(() => {
        expect(screen.getByText(/protected/i)).toBeInTheDocument();
      });
    });

    it('displays merge strategy', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const branchesTab = screen.getByRole('tab', { name: /branches/i });
      await user.click(branchesTab);

      await waitFor(() => {
        expect(screen.getByText(/merge strategy/i)).toBeInTheDocument();
      });
    });
  });

  describe('Rollback', () => {
    it('opens rollback dialog', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const rollbackButton = screen.getByRole('button', { name: /rollback/i });
      await user.click(rollbackButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/rollback to version/i)).toBeInTheDocument();
    });

    it('requires rollback reason', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const rollbackButton = screen.getByRole('button', { name: /rollback/i });
      await user.click(rollbackButton);

      const confirmButton = screen.getByRole('button', { name: /rollback/i });
      await user.click(confirmButton);

      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText(/reason is required/i)).toBeInTheDocument();
      });
    });

    it('submits rollback with reason', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const rollbackButton = screen.getByRole('button', { name: /rollback/i });
      await user.click(rollbackButton);

      const reasonInput = screen.getByLabelText(/reason/i);
      await user.type(reasonInput, 'Critical bug in production');

      const confirmButton = screen.getByRole('button', { name: /rollback/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalled();
      });
    });

    it('shows rollback confirmation warning', async () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const rollbackButton = screen.getByRole('button', { name: /rollback/i });
      await userEvent.click(rollbackButton);

      expect(screen.getByText(/this action cannot be undone/i)).toBeInTheDocument();
    });
  });

  describe('Version Metrics', () => {
    it('switches to metrics tab', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const metricsTab = screen.getByRole('tab', { name: /metrics/i });
      await user.click(metricsTab);

      expect(screen.getByText(/performance metrics/i)).toBeInTheDocument();
    });

    it('displays execution count', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const metricsTab = screen.getByRole('tab', { name: /metrics/i });
      await user.click(metricsTab);

      await waitFor(() => {
        expect(screen.getByText(/executions/i)).toBeInTheDocument();
      });
    });

    it('shows success rate', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const metricsTab = screen.getByRole('tab', { name: /metrics/i });
      await user.click(metricsTab);

      await waitFor(() => {
        expect(screen.getByText(/success rate/i)).toBeInTheDocument();
      });
    });

    it('displays average execution time', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const metricsTab = screen.getByRole('tab', { name: /metrics/i });
      await user.click(metricsTab);

      await waitFor(() => {
        expect(screen.getByText(/avg execution time/i)).toBeInTheDocument();
      });
    });

    it('shows error count', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const metricsTab = screen.getByRole('tab', { name: /metrics/i });
      await user.click(metricsTab);

      await waitFor(() => {
        expect(screen.getByText(/errors/i)).toBeInTheDocument();
      });
    });

    it('displays performance score', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const metricsTab = screen.getByRole('tab', { name: /metrics/i });
      await user.click(metricsTab);

      await waitFor(() => {
        expect(screen.getByText(/performance score/i)).toBeInTheDocument();
      });
    });
  });

  describe('Version Actions', () => {
    it('expands version details', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const expandButton = screen.getByRole('button', { name: /expand/i });
      await user.click(expandButton);

      await waitFor(() => {
        expect(screen.getByText(/checksum/i)).toBeInTheDocument();
      });
    });

    it('shows version metadata', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const expandButton = screen.getByRole('button', { name: /expand/i });
      await user.click(expandButton);

      await waitFor(() => {
        expect(screen.getByText('abc123')).toBeInTheDocument();
      });
    });

    it('downloads version', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const downloadButton = screen.getByRole('button', { name: /download/i });
      await user.click(downloadButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/download'),
          expect.any(Object)
        );
      });
    });
  });

  describe('Loading States', () => {
    it('shows loading indicator on mount', () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      expect(screen.getByTestId(/loading/i)).toBeInTheDocument();
    });

    it('hides loading indicator after data loads', async () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      await waitFor(() => {
        expect(screen.queryByTestId(/loading/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message on fetch failure', async () => {
      global.fetch = jest.fn(() => Promise.reject(new Error('Network error')));

      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load versions/i)).toBeInTheDocument();
      });
    });

    it('allows retry after error', async () => {
      const user = userEvent.setup();
      global.fetch = jest.fn(() => Promise.reject(new Error('Network error')));

      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load versions/i)).toBeInTheDocument();
      });

      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      expect(global.fetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('Filtering', () => {
    it('filters versions by branch', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const branchFilter = screen.getByLabelText(/filter by branch/i);
      await user.selectOptions(branchFilter, 'main');

      await waitFor(() => {
        // Should only show main branch versions
        expect(screen.getByText('main')).toBeInTheDocument();
      });
    });

    it('filters versions by tag', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      const tagFilter = screen.getByPlaceholderText(/filter by tag/i);
      await user.type(tagFilter, 'stable');

      await waitFor(() => {
        expect(screen.getByText('stable')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      expect(screen.getByRole('region', { name: /workflow versioning/i })).toBeInTheDocument();
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();
      render(<WorkflowVersioning workflowId={mockWorkflowId} />);

      await user.tab();

      const firstTab = screen.getByRole('tab', { name: /history/i });
      expect(firstTab).toHaveFocus();
    });
  });
});
