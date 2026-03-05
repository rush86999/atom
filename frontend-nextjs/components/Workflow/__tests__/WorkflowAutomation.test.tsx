import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import WorkflowAutomation from '../WorkflowAutomation';

// Mock useToast hook
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

// Mock Next.js router
jest.mock('next/router', () => ({
  useRouter: () => ({
    query: {},
    replace: jest.fn(),
  }),
}));

// Mock WorkflowBuilder component
jest.mock('../Automations/WorkflowBuilder', () => {
  return function MockWorkflowBuilder(props: any) {
    return (
      <div data-testid="workflow-builder">
        <div>Workflow Builder</div>
        <button onClick={props.onSave}>Save</button>
        <button onClick={props.onCancel}>Cancel</button>
      </div>
    );
  };
});

describe('WorkflowAutomation Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Mock fetch API
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          templates: [],
          workflows: [],
          executions: [],
          services: {},
        }),
        headers: new Headers(),
        status: 200,
        statusText: 'OK',
      } as Response)
    );
  });

  describe('Rendering', () => {
    it('renders without crashing', () => {
      render(<WorkflowAutomation />);

      expect(screen.getByText(/workflow automation/i)).toBeInTheDocument();
    });

    it('displays main tabs', () => {
      render(<WorkflowAutomation />);

      expect(screen.getByRole('tab', { name: /templates/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /workflows/i })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: /executions/i })).toBeInTheDocument();
    });

    it('shows templates tab by default', () => {
      render(<WorkflowAutomation />);

      expect(screen.getByRole('tab', { name: /templates/i })).toHaveAttribute('aria-selected', 'true');
    });
  });

  describe('Template Management', () => {
    it('displays template list', async () => {
      render(<WorkflowAutomation />);

      await waitFor(() => {
        expect(screen.getByRole('tabpanel', { name: /templates/i })).toBeInTheDocument();
      });
    });

    it('opens create template dialog', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const createButton = screen.getByRole('button', { name: /create template/i });
      await user.click(createButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('filters templates by category', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const categoryFilter = screen.getByLabelText(/filter by category/i);
      await user.selectOptions(categoryFilter, 'productivity');

      await waitFor(() => {
        expect(categoryFilter).toHaveValue('productivity');
      });
    });

    it('searches templates by name', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const searchInput = screen.getByPlaceholderText(/search templates/i);
      await user.type(searchInput, 'email');

      await waitFor(() => {
        expect(searchInput).toHaveValue('email');
      });
    });
  });

  describe('Workflow Management', () => {
    it('switches to workflows tab', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const workflowsTab = screen.getByRole('tab', { name: /workflows/i });
      await user.click(workflowsTab);

      expect(screen.getByRole('tabpanel', { name: /workflows/i })).toBeInTheDocument();
    });

    it('displays workflow list', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const workflowsTab = screen.getByRole('tab', { name: /workflows/i });
      await user.click(workflowsTab);

      await waitFor(() => {
        expect(screen.getByRole('list')).toBeInTheDocument();
      });
    });

    it('opens create workflow dialog', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const workflowsTab = screen.getByRole('tab', { name: /workflows/i });
      await user.click(workflowsTab);

      const createButton = screen.getByRole('button', { name: /create workflow/i });
      await user.click(createButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('switches to builder view', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const builderButton = screen.getByRole('button', { name: /builder view/i });
      await user.click(builderButton);

      expect(screen.getByTestId('workflow-builder')).toBeInTheDocument();
    });

    it('deletes workflow after confirmation', async () => {
      const user = userEvent.setup();
      window.confirm = jest.fn(() => true);

      render(<WorkflowAutomation />);

      const workflowsTab = screen.getByRole('tab', { name: /workflows/i });
      await user.click(workflowsTab);

      const deleteButton = screen.getByRole('button', { name: /delete/i });
      await user.click(deleteButton);

      expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining(/are you sure/i));
    });
  });

  describe('Workflow Execution', () => {
    it('switches to executions tab', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      expect(screen.getByRole('tabpanel', { name: /executions/i })).toBeInTheDocument();
    });

    it('displays execution list', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      await waitFor(() => {
        expect(screen.getByRole('list')).toBeInTheDocument();
      });
    });

    it('shows execution status badges', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      await waitFor(() => {
        expect(screen.getByText(/status/i)).toBeInTheDocument();
      });
    });

    it('opens execution details modal', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      const viewButton = screen.getByRole('button', { name: /view details/i });
      await user.click(viewButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('displays execution progress', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      await waitFor(() => {
        expect(screen.getByRole('progressbar')).toBeInTheDocument();
      });
    });

    it('pauses running execution', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      const pauseButton = screen.getByRole('button', { name: /pause/i });
      await user.click(pauseButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/pause'),
          expect.any(Object)
        );
      });
    });

    it('resumes paused execution', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      const resumeButton = screen.getByRole('button', { name: /resume/i });
      await user.click(resumeButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('Time-Travel Fork (Lesson 3)', () => {
    it('opens fork modal', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      const forkButton = screen.getByRole('button', { name: /fork from step/i });
      await user.click(forkButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/fork workflow/i)).toBeInTheDocument();
    });

    it('allows editing fork variables', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      const forkButton = screen.getByRole('button', { name: /fork from step/i });
      await user.click(forkButton);

      const variablesTextarea = screen.getByLabelText(/variables/i);
      await user.clear(variablesTextarea);
      await user.type(variablesTextarea, '{"test": "value"}');

      expect(variablesTextarea).toHaveValue('{"test": "value"}');
    });

    it('validates fork variables JSON', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      const forkButton = screen.getByRole('button', { name: /fork from step/i });
      await user.click(forkButton);

      const variablesTextarea = screen.getByLabelText(/variables/i);
      await user.clear(variablesTextarea);
      await user.type(variablesTextarea, '{invalid json}');

      const confirmButton = screen.getByRole('button', { name: /fork/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid json/i)).toBeInTheDocument();
      });
    });

    it('submits fork with valid variables', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      const forkButton = screen.getByRole('button', { name: /fork from step/i });
      await user.click(forkButton);

      const variablesTextarea = screen.getByLabelText(/variables/i);
      await user.clear(variablesTextarea);
      await user.type(variablesTextarea, '{"test": "value"}');

      const confirmButton = screen.getByRole('button', { name: /fork/i });
      await user.click(confirmButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/fork'),
          expect.any(Object)
        );
      });
    });
  });

  describe('Version History (Lesson 3)', () => {
    it('displays version history for workflow', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const workflowsTab = screen.getByRole('tab', { name: /workflows/i });
      await user.click(workflowsTab);

      const historyButton = screen.getByRole('button', { name: /version history/i });
      await user.click(historyButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/version history/i)).toBeInTheDocument();
    });

    it('shows version comparison', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const workflowsTab = screen.getByRole('tab', { name: /workflows/i });
      await user.click(workflowsTab);

      const historyButton = screen.getByRole('button', { name: /version history/i });
      await user.click(historyButton);

      expect(screen.getByText(/compare versions/i)).toBeInTheDocument();
    });

    it('supports rollback to previous version', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const workflowsTab = screen.getByRole('tab', { name: /workflows/i });
      await user.click(workflowsTab);

      const historyButton = screen.getByRole('button', { name: /version history/i });
      await user.click(historyButton);

      const rollbackButton = screen.getByRole('button', { name: /rollback/i });
      await user.click(rollbackButton);

      expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining(/are you sure/i));
    });
  });

  describe('Generative Workflow Creation', () => {
    it('opens generative create dialog', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const genCreateButton = screen.getByRole('button', { name: /ai generate/i });
      await user.click(genCreateButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/describe your workflow/i)).toBeInTheDocument();
    });

    it('generates workflow from prompt', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const genCreateButton = screen.getByRole('button', { name: /ai generate/i });
      await user.click(genCreateButton);

      const promptTextarea = screen.getByLabelText(/prompt/i);
      await user.type(promptTextarea, 'Send daily email report');

      const generateButton = screen.getByRole('button', { name: /generate/i });
      await user.click(generateButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/generate'),
          expect.any(Object)
        );
      });
    });
  });

  describe('Loading States', () => {
    it('shows loading indicator on mount', () => {
      global.fetch = jest.fn(() => new Promise(() => {})); // Never resolves

      render(<WorkflowAutomation />);

      expect(screen.getByTestId(/loading/i)).toBeInTheDocument();
    });

    it('shows executing indicator during workflow execution', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executeButton = screen.getByRole('button', { name: /execute/i });
      await user.click(executeButton);

      expect(screen.getByTestId(/executing/i)).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error message on fetch failure', async () => {
      global.fetch = jest.fn(() => Promise.reject(new Error('Network error')));

      render(<WorkflowAutomation />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
      });
    });

    it('shows execution errors', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      const executionsTab = screen.getByRole('tab', { name: /executions/i });
      await user.click(executionsTab);

      await waitFor(() => {
        expect(screen.getByText(/errors/i)).toBeInTheDocument();
      });
    });

    it('allows retry after error', async () => {
      const user = userEvent.setup();
      global.fetch = jest.fn(() => Promise.reject(new Error('Network error')));

      render(<WorkflowAutomation />);

      await waitFor(() => {
        const retryButton = screen.queryByRole('button', { name: /retry/i });
        if (retryButton) {
          user.click(retryButton);
          expect(global.fetch).toHaveBeenCalledTimes(2);
        }
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<WorkflowAutomation />);

      expect(screen.getByRole('region', { name: /workflow automation/i })).toBeInTheDocument();
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();
      render(<WorkflowAutomation />);

      await user.tab();

      const firstTab = screen.getByRole('tab', { name: /templates/i });
      expect(firstTab).toHaveFocus();
    });
  });

  describe('URL Draft Loading', () => {
    it('loads workflow from URL draft parameter', async () => {
      const mockRouter = {
        query: { draft: JSON.stringify({ name: 'Test Workflow' }) },
        replace: jest.fn(),
      };

      (require('next/router').useRouter as jest.Mock).mockReturnValue(mockRouter);

      render(<WorkflowAutomation />);

      await waitFor(() => {
        expect(mockRouter.replace).toHaveBeenCalledWith('/automation', undefined, { shallow: true });
      });
    });

    it('switches to builder view when draft loaded', async () => {
      const mockRouter = {
        query: { draft: JSON.stringify({ name: 'Test Workflow' }) },
        replace: jest.fn(),
      };

      (require('next/router').useRouter as jest.Mock).mockReturnValue(mockRouter);

      render(<WorkflowAutomation />);

      await waitFor(() => {
        expect(screen.getByTestId('workflow-builder')).toBeInTheDocument();
      });
    });

    it('handles invalid draft JSON gracefully', async () => {
      const mockRouter = {
        query: { draft: '{invalid json}' },
        replace: jest.fn(),
      };

      (require('next/router').useRouter as jest.Mock).mockReturnValue(mockRouter);

      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

      render(<WorkflowAutomation />);

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });

      consoleErrorSpy.mockRestore();
    });
  });
});
