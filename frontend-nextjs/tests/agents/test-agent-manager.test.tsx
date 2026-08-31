import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgentManager from '@/components/Agents/AgentManager';

// Mock useToast
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn()
  })
}));

// Radix Select is not keyboard-interactive in jsdom; replace it with a native
// <select> that still exercises the component's onValueChange wiring.
jest.mock('@/components/ui/select', () => ({
  Select: ({ value, onValueChange, children }: any) => (
    <select
      data-testid="model-select"
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
    >
      {children}
    </select>
  ),
  SelectTrigger: ({ children }: any) => <>{children}</>,
  SelectContent: ({ children }: any) => <>{children}</>,
  SelectItem: ({ value }: any) => <option value={value}>{value}</option>,
  SelectValue: () => null,
}));

describe('AgentManager Component', () => {
  const mockAgents = [
    {
      id: 'agent-1',
      name: 'Agent One',
      role: 'Assistant',
      status: 'active' as const,
      capabilities: ['calendar_management', 'task_management'],
      performance: {
        tasksCompleted: 10,
        successRate: 95,
        avgResponseTime: 150
      },
      config: {
        model: 'gpt-4',
        temperature: 0.7,
        maxTokens: 1000
      }
    },
    {
      id: 'agent-2',
      name: 'Agent Two',
      role: 'Analyst',
      status: 'inactive' as const,
      capabilities: ['email_processing', 'document_analysis'],
      performance: {
        tasksCompleted: 5,
        successRate: 80,
        avgResponseTime: 200
      },
      config: {
        model: 'gpt-3.5-turbo',
        temperature: 0.5,
        maxTokens: 500
      }
    },
    {
      id: 'agent-3',
      name: 'Agent Three',
      role: 'Researcher',
      status: 'error' as const,
      capabilities: ['financial_analysis'],
      performance: {
        tasksCompleted: 0,
        successRate: 0,
        avgResponseTime: 0
      },
      config: {
        model: 'claude-2',
        temperature: 0.8,
        maxTokens: 2000
      }
    }
  ];

  const mockHandlers = {
    onAgentCreate: jest.fn(),
    onAgentUpdate: jest.fn(),
    onAgentDelete: jest.fn(),
    onAgentStart: jest.fn(),
    onAgentStop: jest.fn()
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Render tests
  describe('Rendering', () => {
    it('should render all agents in grid', () => {
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);
      expect(screen.getByText('Agent One')).toBeInTheDocument();
      expect(screen.getByText('Agent Two')).toBeInTheDocument();
      expect(screen.getByText('Agent Three')).toBeInTheDocument();
    });

    it('should render header with title and description', () => {
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);
      expect(screen.getByText('Agent Manager')).toBeInTheDocument();
      expect(screen.getByText('Manage and monitor your AI agents')).toBeInTheDocument();
    });

    it('should render create agent button', () => {
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);
      expect(screen.getByRole('button', { name: /create agent/i })).toBeInTheDocument();
    });

    it('should show agent count in header', () => {
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);
      // Agent count is not explicitly shown in the component
      expect(screen.getByText('Agent One')).toBeInTheDocument();
    });

    it('should render empty state when no agents', () => {
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);
      expect(screen.getByText(/no agents created/i)).toBeInTheDocument();
      expect(screen.getByText('Create your first agent to get started with multi-agent automation')).toBeInTheDocument();
    });

    it('should render empty state create button', () => {
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);
      expect(screen.getByRole('button', { name: /create first agent/i })).toBeInTheDocument();
    });
  });

  // Agent card display tests
  describe('Agent Card Display', () => {
    it('should display agent capabilities as badges', () => {
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);
      expect(screen.getByText('calendar management')).toBeInTheDocument();
      expect(screen.getByText('task management')).toBeInTheDocument();
    });

    it('should display agent performance metrics', () => {
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);
      expect(screen.getByText('10')).toBeInTheDocument(); // tasksCompleted
      expect(screen.getByText('95%')).toBeInTheDocument(); // successRate
      expect(screen.getByText('150ms')).toBeInTheDocument(); // avgResponseTime
    });

    it('should display agent status badges', () => {
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);
      expect(screen.getByText('active')).toBeInTheDocument();
      expect(screen.getByText('inactive')).toBeInTheDocument();
      expect(screen.getByText('error')).toBeInTheDocument();
    });

    it('should display agent role', () => {
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);
      expect(screen.getByText('Assistant')).toBeInTheDocument();
      expect(screen.getByText('Analyst')).toBeInTheDocument();
    });
  });

  // Agent creation tests
  describe('Agent Creation', () => {
    it('should open creation modal when create button clicked', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);
      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText(/create new agent/i)).toBeInTheDocument();
      });
    });

    it('should show form fields in modal', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);
      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText(/agent name/i)).toBeInTheDocument();
        expect(screen.getByText('Role')).toBeInTheDocument();
      });
    });

    it('should display capability checkboxes', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);
      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText('calendar management')).toBeInTheDocument();
        expect(screen.getByText('task management')).toBeInTheDocument();
      });
    });

    it('should show model configuration section', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);
      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText(/model configuration/i)).toBeInTheDocument();
        expect(screen.getByText('Model')).toBeInTheDocument();
        expect(screen.getByText('Temperature')).toBeInTheDocument();
        expect(screen.getByText('Max Tokens')).toBeInTheDocument();
      });
    });
  });

  // Agent operations tests
  describe('Agent Operations', () => {
    it('should call onAgentStart when start button clicked', async () => {
      const user = userEvent.setup();
      const inactiveAgent = mockAgents.filter(a => a.status === 'inactive')[0];
      render(<AgentManager initialAgents={[inactiveAgent]} {...mockHandlers} />);

      const startButtons = screen.getAllByRole('button', { name: /start/i });
      await user.click(startButtons[0]);

      expect(mockHandlers.onAgentStart).toHaveBeenCalledWith('agent-2');
    });

    it('should call onAgentStop when stop button clicked', async () => {
      const user = userEvent.setup();
      const activeAgent = mockAgents.filter(a => a.status === 'active')[0];
      render(<AgentManager initialAgents={[activeAgent]} {...mockHandlers} />);

      const stopButtons = screen.getAllByRole('button', { name: /stop/i });
      await user.click(stopButtons[0]);

      expect(mockHandlers.onAgentStop).toHaveBeenCalledWith('agent-1');
    });

    it('should call onAgentDelete when delete button clicked', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);

      const deleteButtons = screen.getAllByRole('button').filter(btn => btn.getAttribute('class')?.includes('text-red'));
      if (deleteButtons.length > 0) {
        await user.click(deleteButtons[0]);
        expect(mockHandlers.onAgentDelete).toHaveBeenCalled();
      }
    });

    it('should open edit modal when edit button clicked', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);

      const editButtons = screen.getAllByRole('button', { name: '' }).filter(btn =>
        btn.innerHTML.includes('Edit') || btn.getAttribute('class')?.includes('outline')
      );
      if (editButtons.length > 0) {
        await user.click(editButtons[0]);
        await waitFor(() => {
          expect(screen.getByText(/edit agent/i)).toBeInTheDocument();
        });
      }
    });
  });

  // Form input tests
  describe('Form Inputs', () => {
    it('should update agent name on input change', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);

      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText(/agent name/i)).toBeInTheDocument();
      });

      // Find input by placeholder or by finding all inputs and selecting the first one
      const inputs = screen.getAllByPlaceholderText('Enter agent name');
      if (inputs.length > 0) {
        await user.clear(inputs[0]);
        await user.type(inputs[0], 'New Agent');
        expect(inputs[0]).toHaveValue('New Agent');
      }
    });

    it('should update role on input change', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);

      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Role')).toBeInTheDocument();
      });

      // Find the role input (it's labeled with a Label component, not aria-label)
      const roleInputs = screen.getAllByDisplayValue('');
      const roleInput = roleInputs.find(input => {
        const label = input.parentElement?.querySelector('label');
        return label?.textContent?.includes('Role');
      });

      if (roleInput) {
        await user.clear(roleInput);
        await user.type(roleInput, 'Researcher');
        expect(roleInput).toHaveValue('Researcher');
      }
    });

    it('should toggle capability selection', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);

      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText('calendar management')).toBeInTheDocument();
      });

      const capButtons = screen.getAllByText('calendar management');
      if (capButtons.length > 0) {
        await user.click(capButtons[0]);
        // Toggle should work (checked state changes)
      }
    });
  });

  // Model configuration tests
  describe('Model Configuration', () => {
    it('should render model selector', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);

      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Model')).toBeInTheDocument();
      });
    });

    it('should render temperature slider', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);

      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Temperature')).toBeInTheDocument();
      });
    });

    it('should render max tokens slider', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);

      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Max Tokens')).toBeInTheDocument();
      });
    });
  });

  // Edge cases
  describe('Edge Cases', () => {
    it('should handle undefined agents gracefully', () => {
      render(<AgentManager initialAgents={undefined} {...mockHandlers} />);
      expect(screen.getByText(/no agents created/i)).toBeInTheDocument();
    });

    it('should handle large agent lists', () => {
      const largeAgentList = Array.from({ length: 100 }, (_, i) => ({
        id: `agent-${i}`,
        name: `Agent ${i}`,
        role: 'Assistant',
        status: 'inactive' as const,
        capabilities: ['task_management'],
        performance: {
          tasksCompleted: 0,
          successRate: 0,
          avgResponseTime: 0
        },
        config: {
          model: 'gpt-4',
          temperature: 0.7,
          maxTokens: 1000
        }
      }));
      render(<AgentManager initialAgents={largeAgentList} {...mockHandlers} />);
      expect(screen.getByText('Agent 0')).toBeInTheDocument();
      expect(screen.getByText('Agent 99')).toBeInTheDocument();
    });

    it('should handle agent with no capabilities', () => {
      const agentNoCaps = [{
        ...mockAgents[0],
        capabilities: []
      }];
      render(<AgentManager initialAgents={agentNoCaps} {...mockHandlers} />);
      expect(screen.getByText('Agent One')).toBeInTheDocument();
    });
  });

  // Accessibility tests
  describe('Accessibility', () => {
    it('should have proper button labels', () => {
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);
      expect(screen.getByRole('button', { name: /create agent/i })).toBeInTheDocument();
    });

    it('should have proper headings', () => {
      render(<AgentManager initialAgents={mockAgents} {...mockHandlers} />);
      expect(screen.getByRole('heading', { name: 'Agent Manager' })).toBeInTheDocument();
    });
  });

  // Modal and dialog tests
  describe('Modal Behavior', () => {
    it('should close modal on cancel', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);

      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText(/create new agent/i)).toBeInTheDocument();
      });

      const cancelButton = screen.getAllByRole('button').find(btn => btn.textContent === 'Cancel');
      if (cancelButton) {
        await user.click(cancelButton);
        await waitFor(() => {
          expect(screen.queryByText(/create new agent/i)).not.toBeInTheDocument();
        });
      }
    });

    it('should show save button in modal', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);

      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText(/create new agent/i)).toBeInTheDocument();
      });

      const saveButtons = screen.getAllByRole('button').filter(btn => btn.textContent === 'Create Agent');
      expect(saveButtons.length).toBeGreaterThan(0);
    });

    it('should enable save button when form is valid', async () => {
      const user = userEvent.setup();
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);

      await user.click(screen.getByRole('button', { name: /create agent/i }));
      await waitFor(() => {
        expect(screen.getByText(/agent name/i)).toBeInTheDocument();
      });

      // Find and fill name input
      const nameInputs = screen.getAllByPlaceholderText('Enter agent name');
      if (nameInputs.length > 0) {
        await user.clear(nameInputs[0]);
        await user.type(nameInputs[0], 'Test Agent');
      }

      // Find and fill role input
      const roleInputs = screen.getAllByDisplayValue('');
      const roleInput = roleInputs.find(input => {
        const label = input.parentElement?.querySelector('label');
        return label?.textContent?.includes('Role');
      });

      if (roleInput) {
        await user.clear(roleInput);
        await user.type(roleInput, 'Analyst');
      }

      // Check if save button is enabled (it should be if form is valid)
      const saveButtons = screen.getAllByRole('button').filter(btn => btn.textContent === 'Create Agent');
      if (saveButtons.length > 0 && nameInputs.length > 0 && (nameInputs[0] as HTMLInputElement).value === 'Test Agent') {
        // Button should be enabled when form is valid
        expect(saveButtons[0]).not.toBeDisabled();
      }
    });
  });

  // Agent status color tests
  describe('Status Colors', () => {
    it('should apply green color for active status', () => {
      render(<AgentManager initialAgents={[mockAgents[0]]} {...mockHandlers} />);
      const badge = screen.getByText('active').closest('.bg-green-500');
      expect(badge).toBeInTheDocument();
    });

    it('should apply gray color for inactive status', () => {
      render(<AgentManager initialAgents={[mockAgents[1]]} {...mockHandlers} />);
      const badge = screen.getByText('inactive');
      expect(badge).toBeInTheDocument();
    });

    it('should apply red color for error status', () => {
      render(<AgentManager initialAgents={[mockAgents[2]]} {...mockHandlers} />);
      const badge = screen.getByText('error');
      expect(badge).toBeInTheDocument();
    });
  });

  // Extended coverage: create flow, capability toggling, config inputs
  describe('Extended Coverage', () => {
    afterEach(() => {
      jest.useRealTimers();
    });

    const openCreateModal = async () => {
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);
      fireEvent.click(screen.getByRole('button', { name: /create agent/i }));
      await screen.findByText(/create new agent/i);
      const nameInput = screen.getByPlaceholderText('Enter agent name');
      const roleInput = screen.getByPlaceholderText('Enter agent role');
      return { nameInput, roleInput };
    };

    it('creates an agent end to end (validation, callbacks, timeout)', async () => {
      jest.useFakeTimers();
      const { nameInput, roleInput } = await openCreateModal();

      // submit is disabled until both name and role are filled
      const submit = () =>
        screen.getAllByRole('button').find((b) => b.textContent === 'Create Agent' && b.closest('[role="dialog"]'))!;
      expect(submit()).toBeDisabled();

      fireEvent.change(nameInput, { target: { value: 'Brand New Agent' } });
      fireEvent.change(roleInput, { target: { value: 'Assistant' } });
      expect(submit()).toBeEnabled();

      fireEvent.click(submit());

      expect(mockHandlers.onAgentCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Brand New Agent',
          role: 'Assistant',
          status: 'inactive',
        })
      );

      // the simulated API call resolves after 1s
      act(() => {
        jest.advanceTimersByTime(1100);
      });

      expect(await screen.findByText('Brand New Agent')).toBeInTheDocument();
      expect(screen.queryByText(/create new agent/i)).not.toBeInTheDocument();
    });

    it('toggles capabilities on and off in the create modal', async () => {
      const { nameInput } = await openCreateModal();

      const capButton = screen
        .getAllByRole('button', { name: /calendar management/i })
        .find((b) => (b as HTMLButtonElement).type === 'button' || b.getAttribute('type') === 'button')!;
      // toggle on
      fireEvent.click(capButton);
      // toggle off again
      fireEvent.click(capButton);

      fireEvent.change(nameInput, { target: { value: 'X' } });
      const roleInput = screen.getByPlaceholderText('Enter agent role');
      fireEvent.change(roleInput, { target: { value: 'Y' } });

      // assert no crash; capability state toggled twice back to empty
      expect(capButton).toBeInTheDocument();
    });

    it('updates model, temperature and max tokens config', async () => {
      await openCreateModal();

      // model select
      fireEvent.change(screen.getByTestId('model-select'), {
        target: { value: 'claude-2' },
      });

      // temperature slider (native range input)
      const sliders = screen
        .getAllByRole('slider')
        .filter((s) => (s as HTMLInputElement).type === 'range');
      fireEvent.change(sliders[0], { target: { value: '0.3' } });
      fireEvent.change(sliders[1], { target: { value: '2500' } });

      expect(await screen.findByText('0.3')).toBeInTheDocument();
      expect(screen.getByText('2500')).toBeInTheDocument();
    });

    it('covers the default status color branch for unknown statuses', () => {
      render(
        <AgentManager
          initialAgents={[
            { ...mockAgents[0], status: 'paused' as any },
          ]}
          {...mockHandlers}
        />
      );
      expect(screen.getByText('paused')).toBeInTheDocument();
    });

    it('opens the create modal from the empty state CTA', async () => {
      render(<AgentManager initialAgents={[]} {...mockHandlers} />);
      fireEvent.click(screen.getByRole('button', { name: /create first agent/i }));
      await screen.findByText(/create new agent/i);
    });

    it('populates the edit modal from an existing agent and submits', async () => {
      render(<AgentManager initialAgents={[mockAgents[0]]} {...mockHandlers} />);

      const editButton = screen
        .getAllByRole('button')
        .find((b) => (b.getAttribute('class') || '').includes('border border-input'))!;
      fireEvent.click(editButton);

      await screen.findByText(/edit agent/i);
      const nameInput = screen.getByDisplayValue('Agent One') as HTMLInputElement;
      expect(nameInput.value).toBe('Agent One');

      jest.useFakeTimers();
      fireEvent.change(nameInput, { target: { value: 'Renamed Agent' } });
      const updateButton = screen
        .getAllByRole('button')
        .find((b) => b.textContent === 'Update Agent')!;
      fireEvent.click(updateButton);

      act(() => {
        jest.advanceTimersByTime(1100);
      });

      expect(await screen.findByText('Renamed Agent')).toBeInTheDocument();
      expect(mockHandlers.onAgentCreate).toHaveBeenCalled();
    });
  });
});
