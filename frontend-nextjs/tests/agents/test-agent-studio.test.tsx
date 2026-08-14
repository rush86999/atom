import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgentStudio from '@/components/Agents/AgentStudio';

// Mock axios. Must provide a factory: the automock returns `undefined` from
// axios.create(), so lib/api.ts's `apiClient.interceptors.request.use(...)`
// threw "Cannot read properties of undefined (reading 'interceptors')" at
// import time and the whole suite failed to run.
jest.mock('axios', () => {
  const mockAxios: any = {
    create: jest.fn(() => mockAxios),
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
  };
  return mockAxios;
});
const axios = require('axios');

// Mock useToast (stable instance so tests can assert calls; a fresh jest.fn()
// per render would make toast assertions impossible)
const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: mockToast
  })
}));

// Mock useWebSocket with a mutable state object so extended tests can inject
// WebSocket messages (agent_step_update / hitl_* / agent_status_change).
const mockWsState = {
  isConnected: true,
  lastMessage: null as any,
  subscribe: jest.fn()
};
jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => mockWsState
}));

describe('AgentStudio Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Mock successful GET request for agents
    axios.get.mockResolvedValue({
      data: [
        {
          id: 'agent-1',
          name: 'Test Agent',
          category: 'Operations',
          description: 'Test description',
          status: 'active',
          configuration: {
            system_prompt: 'You are helpful',
            tools: '*'
          },
          schedule_config: {
            active: false
          }
        }
      ]
    });
  });

  // Render tests
  describe('Rendering', () => {
    it('should render header with title and description', async () => {
      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Agent Studio')).toBeInTheDocument();
        expect(screen.getByText('Design, Schedule, and Manage Specialty Agents')).toBeInTheDocument();
      });
    });

    it('should render create new agent button', async () => {
      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /create new agent/i })).toBeInTheDocument();
      });
    });

    it('should fetch and display agents on mount', async () => {
      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });
    });

    it('should display agent category', async () => {
      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Operations')).toBeInTheDocument();
      });
    });

    it('should display agent status badge', async () => {
      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('active')).toBeInTheDocument();
      });
    });

    it('should display agent description', async () => {
      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test description')).toBeInTheDocument();
      });
    });
  });

  // Agent creation tests
  describe('Agent Creation', () => {
    it('should open creation modal when create button clicked', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));
      await waitFor(() => {
        expect(screen.getByText(/create custom agent/i)).toBeInTheDocument();
      });
    });

    it('should display form fields in modal', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Name')).toBeInTheDocument();
        expect(screen.getByText('Category')).toBeInTheDocument();
        expect(screen.getByText('Description')).toBeInTheDocument();
      });
    });

    it('should display behavior section', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Behavior')).toBeInTheDocument();
        expect(screen.getByText('System Prompt / Instructions')).toBeInTheDocument();
      });
    });

    it('should display schedule section', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Schedule')).toBeInTheDocument();
      });
    });
  });

  // Form input tests
  describe('Form Inputs', () => {
    it('should update name on input change', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Name')).toBeInTheDocument();
      });

      const nameInputs = screen.getAllByDisplayValue('');
      const nameInput = nameInputs.find(input => {
        const label = input.parentElement?.querySelector('label');
        return label?.textContent?.includes('Name');
      });

      if (nameInput) {
        await user.clear(nameInput);
        await user.type(nameInput, 'New Agent');
        expect(nameInput).toHaveValue('New Agent');
      }
    });

    it('should update description on input change', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));

      // The Description <Input> has no placeholder attribute (only an empty
      // value), so locate it the same way the Name test does: by empty
      // display-value and its parent <Label> text.
      const descInputs = screen.getAllByDisplayValue('');
      const descInput = descInputs.find(input => {
        const label = input.parentElement?.querySelector('label');
        return label?.textContent?.includes('Description');
      });

      if (descInput) {
        await user.clear(descInput);
        await user.type(descInput, 'New description');
        expect(descInput).toHaveValue('New description');
      }
    });

    it('should select category from dropdown', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));

      // The category control is a Radix Select whose trigger is a combobox.
      // Scope to the dialog so the agent card's category text ("Operations")
      // does not cause an ambiguous match.
      const dialog = await screen.findByRole('dialog');
      const combobox = within(dialog).getByRole('combobox');
      expect(combobox).toHaveTextContent('Operations');

      // Open the dropdown and pick a different category.
      await user.click(combobox);
      const financeOption = await screen.findByRole('option', { name: 'Finance' });
      await user.click(financeOption);

      // The SelectValue now reflects the selection.
      expect(within(dialog).getByRole('combobox')).toHaveTextContent('Finance');
    });
  });

  // Schedule configuration tests
  describe('Schedule Configuration', () => {
    it('should toggle schedule active switch', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Schedule')).toBeInTheDocument();
      });

      // Find the switch/toggle
      const switches = screen.getAllByRole('switch');
      if (switches.length > 0) {
        await user.click(switches[0]);
      }
    });

    it('should show schedule fields when active', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Schedule')).toBeInTheDocument();
      });

      // Toggle schedule on
      const switches = screen.getAllByRole('switch');
      if (switches.length > 0) {
        await user.click(switches[0]);

        // Should show cron expression and task fields
        await waitFor(() => {
          expect(screen.getByText('Cron Expression')).toBeInTheDocument();
          expect(screen.getByText('Scheduled Task Instructions')).toBeInTheDocument();
        });
      }
    });
  });

  // Agent editing tests
  describe('Agent Editing', () => {
    it('should open edit modal when configure button clicked', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByText(/edit agent/i)).toBeInTheDocument();
        });
      }
    });

    it('should populate form with existing agent data', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByDisplayValue('Test Agent')).toBeInTheDocument();
        });
      }
    });
  });

  // Test run functionality
  describe('Test Run', () => {
    it('should show test section when editing agent', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByText('Test')).toBeInTheDocument();
        });
      }
    });

    it('should display test input field', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByPlaceholderText(/enter a task to run/i)).toBeInTheDocument();
        });
      }
    });
  });

  // Save and cancel tests
  describe('Actions', () => {
    it('should close modal on cancel', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));
      await waitFor(() => {
        expect(screen.getByText(/create custom agent/i)).toBeInTheDocument();
      });

      const cancelButtons = screen.getAllByRole('button').filter(btn => btn.textContent === 'Cancel');
      if (cancelButtons.length > 0) {
        await user.click(cancelButtons[0]);
        await waitFor(() => {
          expect(screen.queryByText(/create custom agent/i)).not.toBeInTheDocument();
        });
      }
    });

    it('should call save agent API when save clicked', async () => {
      const user = userEvent.setup();
      axios.post.mockResolvedValue({ data: { success: true } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Name')).toBeInTheDocument();
      });

      // Fill in required fields
      const nameInputs = screen.getAllByDisplayValue('');
      const nameInput = nameInputs.find(input => {
        const label = input.parentElement?.querySelector('label');
        return label?.textContent?.includes('Name');
      });

      if (nameInput) {
        await user.clear(nameInput);
        await user.type(nameInput, 'Test Agent 2');
      }

      const roleInputs = screen.getAllByDisplayValue('');
      const roleInput = roleInputs.find(input => {
        const label = input.parentElement?.querySelector('label');
        return label?.textContent?.includes('Category');
      });

      if (roleInput) {
        await user.clear(roleInput);
        await user.type(roleInput, 'Operations');
      }

      const saveButtons = screen.getAllByRole('button').filter(btn => btn.textContent === 'Save Agent');
      if (saveButtons.length > 0) {
        await user.click(saveButtons[0]);
        // API call should be made
        expect(axios.post).toHaveBeenCalled();
      }
    });
  });

  // Edge cases
  describe('Edge Cases', () => {
    it('should handle API error gracefully', async () => {
      axios.get.mockRejectedValue(new Error('API Error'));
      render(<AgentStudio />);
      // Should not crash, just show empty state or error
      await waitFor(() => {
        expect(screen.getByText('Agent Studio')).toBeInTheDocument();
      });
    });

    it('should handle agent with empty description', async () => {
      axios.get.mockResolvedValue({
        data: [
          {
            id: 'agent-1',
            name: 'Test Agent',
            category: 'Operations',
            description: '',
            status: 'active'
          }
        ]
      });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });
    });

    it('should handle empty agent list', async () => {
      axios.get.mockResolvedValue({ data: [] });
      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Agent Studio')).toBeInTheDocument();
      });
    });

    it('should handle save API error', async () => {
      const user = userEvent.setup();
      axios.post.mockRejectedValue({ response: { data: { detail: 'Save failed' } } });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /create new agent/i }));
      await waitFor(() => {
        expect(screen.getByText('Name')).toBeInTheDocument();
      });

      // Fill required fields
      const nameInputs = screen.getAllByDisplayValue('');
      const nameInput = nameInputs.find(input => {
        const label = input.parentElement?.querySelector('label');
        return label?.textContent?.includes('Name');
      });

      if (nameInput) {
        await user.clear(nameInput);
        await user.type(nameInput, 'Test Agent 2');
      }

      const roleInputs = screen.getAllByDisplayValue('');
      const roleInput = roleInputs.find(input => {
        const label = input.parentElement?.querySelector('label');
        return label?.textContent?.includes('Category');
      });

      if (roleInput) {
        await user.clear(roleInput);
        await user.type(roleInput, 'Operations');
      }

      const saveButtons = screen.getAllByRole('button').filter(btn => btn.textContent === 'Save Agent');
      if (saveButtons.length > 0) {
        await user.click(saveButtons[0]);
        // Should handle error gracefully
      }
    });
  });

  // Test run execution tests
  describe('Test Run Execution', () => {
    it('should execute test run when play button clicked', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });
      axios.post.mockResolvedValue({
        data: {
          status: 'completed',
          result: {
            steps: [
              {
                step: 1,
                thought: 'Test thought',
                action: { tool: 'test' },
                output: 'Test output'
              }
            ],
            final_output: 'Final answer'
          }
        }
      });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByPlaceholderText(/enter a task to run/i)).toBeInTheDocument();
        });

        const testInput = screen.getByPlaceholderText(/enter a task to run/i);
        await user.type(testInput, 'Test task');

        // The run button is icon-only (a Play lucide icon, no text); the old
        // filter matched any svg-bearing button (e.g. header "Create New Agent").
        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.querySelector('.lucide-play')
        );

        if (playButtons.length > 0) {
          await user.click(playButtons[0]);
          // Should make API call
          expect(axios.post).toHaveBeenCalled();
        }
      }
    });

    it('should display trace steps when test run completes', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });
      axios.post.mockResolvedValue({
        data: {
          status: 'completed',
          result: {
            steps: [
              {
                step: 1,
                thought: 'Test thought',
                action: { tool: 'test_tool' },
                output: 'Test output'
              }
            ],
            final_output: 'Final answer'
          }
        }
      });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByPlaceholderText(/enter a task to run/i)).toBeInTheDocument();
        });

        const testInput = screen.getByPlaceholderText(/enter a task to run/i);
        await user.type(testInput, 'Test task');

        // The run button is icon-only (a Play lucide icon, no text); the old
        // filter matched any svg-bearing button (e.g. header "Create New Agent").
        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.querySelector('.lucide-play')
        );

        if (playButtons.length > 0) {
          await user.click(playButtons[0]);
          await waitFor(() => {
            expect(screen.getByText('Step 1')).toBeInTheDocument();
            expect(screen.getByText('Test thought')).toBeInTheDocument();
          });
        }
      }
    });

    it('should handle async test run dispatch', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });
      axios.post.mockResolvedValue({
        data: {
          status: 'running'
        }
      });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByPlaceholderText(/enter a task to run/i)).toBeInTheDocument();
        });

        const testInput = screen.getByPlaceholderText(/enter a task to run/i);
        await user.type(testInput, 'Test task');

        // The run button is icon-only (a Play lucide icon, no text); the old
        // filter matched any svg-bearing button (e.g. header "Create New Agent").
        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.querySelector('.lucide-play')
        );

        if (playButtons.length > 0) {
          await user.click(playButtons[0]);
          await waitFor(() => {
            expect(screen.getByText(/task dispatched/i)).toBeInTheDocument();
          });
        }
      }
    });
  });

  // HITL (Human-in-the-Loop) tests
  describe('HITL Decision Handling', () => {
    it('should show HITL paused message', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });
      axios.post.mockResolvedValue({
        data: {
          status: 'completed',
          result: {
            steps: [
              {
                type: 'hitl_paused',
                action_id: 'action-1',
                action: { tool: 'email' },
                reason: 'Email approval required'
              }
            ]
          }
        }
      });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByPlaceholderText(/enter a task to run/i)).toBeInTheDocument();
        });

        const testInput = screen.getByPlaceholderText(/enter a task to run/i);
        await user.type(testInput, 'Send email');

        // The run button is icon-only (a Play lucide icon, no text); the old
        // filter matched any svg-bearing button (e.g. header "Create New Agent").
        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.querySelector('.lucide-play')
        );

        if (playButtons.length > 0) {
          await user.click(playButtons[0]);
          await waitFor(() => {
            expect(screen.getByText(/human approval required/i)).toBeInTheDocument();
            // The tool name renders as "Action: email" inside a <p> alongside
            // the reason text, so an exact text-node match can't find it.
            expect(screen.getByText('email', { exact: false })).toBeInTheDocument();
          });
        }
      }
    });

    it('should handle HITL approve action', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });
      axios.post.mockResolvedValue({
        data: {
          status: 'completed',
          result: {
            steps: [
              {
                type: 'hitl_paused',
                action_id: 'action-1',
                action: { tool: 'email' },
                reason: 'Email approval required',
                status: 'pending'
              }
            ]
          }
        }
      });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByPlaceholderText(/enter a task to run/i)).toBeInTheDocument();
        });

        const testInput = screen.getByPlaceholderText(/enter a task to run/i);
        await user.type(testInput, 'Send email');

        // The run button is icon-only (a Play lucide icon, no text); the old
        // filter matched any svg-bearing button (e.g. header "Create New Agent").
        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.querySelector('.lucide-play')
        );

        if (playButtons.length > 0) {
          await user.click(playButtons[0]);
          await waitFor(() => {
            expect(screen.getByText(/human approval required/i)).toBeInTheDocument();
          });

          const approveButtons = screen.getAllByRole('button').filter(btn =>
            btn.textContent === 'Approve'
          );

          if (approveButtons.length > 0) {
            axios.post.mockResolvedValue({ data: { success: true } });
            await user.click(approveButtons[0]);
            // Should call approval API
            expect(axios.post).toHaveBeenCalledWith('/api/agents/approvals/action-1', {
              decision: 'approved'
            });
          }
        }
      }
    });
  });

  // Feedback submission tests
  describe('Feedback Submission', () => {
    it('should open feedback modal when thumbs down clicked', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });
      axios.post.mockResolvedValue({
        data: {
          status: 'completed',
          result: {
            steps: [
              {
                step: 1,
                thought: 'Incorrect thought',
                action: { tool: 'test' },
                output: 'Wrong output'
              }
            ],
            final_output: 'Final answer'
          }
        }
      });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByPlaceholderText(/enter a task to run/i)).toBeInTheDocument();
        });

        const testInput = screen.getByPlaceholderText(/enter a task to run/i);
        await user.type(testInput, 'Test task');

        // The run button is icon-only (a Play lucide icon, no text); the old
        // filter matched any svg-bearing button (e.g. header "Create New Agent").
        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.querySelector('.lucide-play')
        );

        if (playButtons.length > 0) {
          await user.click(playButtons[0]);
          await waitFor(() => {
            expect(screen.getByText('Step 1')).toBeInTheDocument();
          });

          // Find thumbs down button
          // The feedback button is icon-only (a ThumbsDown lucide icon);
          // btn.innerHTML never contains the literal "ThumbsDown" text.
          const thumbsDownButtons = screen.getAllByRole('button').filter(btn =>
            btn.querySelector('.lucide-thumbs-down')
          );

          if (thumbsDownButtons.length > 0) {
            await user.click(thumbsDownButtons[0]);
            await waitFor(() => {
              expect(screen.getByText('Provide Feedback')).toBeInTheDocument();
            });
          }
        }
      }
    });

    it('should submit feedback when submit button clicked', async () => {
      const user = userEvent.setup();
      axios.put.mockResolvedValue({ data: { success: true } });
      axios.post.mockResolvedValue({
        data: {
          status: 'completed',
          result: {
            steps: [
              {
                step: 1,
                thought: 'Incorrect thought',
                action: { tool: 'test' },
                output: 'Wrong output'
              }
            ],
            final_output: 'Final answer'
          }
        }
      });

      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeInTheDocument();
      });

      const configureButtons = screen.getAllByRole('button').filter(btn =>
        btn.textContent === 'Configure'
      );

      if (configureButtons.length > 0) {
        await user.click(configureButtons[0]);
        await waitFor(() => {
          expect(screen.getByPlaceholderText(/enter a task to run/i)).toBeInTheDocument();
        });

        const testInput = screen.getByPlaceholderText(/enter a task to run/i);
        await user.type(testInput, 'Test task');

        // The run button is icon-only (a Play lucide icon, no text); the old
        // filter matched any svg-bearing button (e.g. header "Create New Agent").
        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.querySelector('.lucide-play')
        );

        if (playButtons.length > 0) {
          await user.click(playButtons[0]);
          await waitFor(() => {
            expect(screen.getByText('Step 1')).toBeInTheDocument();
          });

          // The feedback button is icon-only (a ThumbsDown lucide icon);
          // btn.innerHTML never contains the literal "ThumbsDown" text.
          const thumbsDownButtons = screen.getAllByRole('button').filter(btn =>
            btn.querySelector('.lucide-thumbs-down')
          );

          if (thumbsDownButtons.length > 0) {
            await user.click(thumbsDownButtons[0]);
            await waitFor(() => {
              expect(screen.getByText('Provide Feedback')).toBeInTheDocument();
            });

            // Fill feedback
            const feedbackTextareas = screen.getAllByPlaceholderText(/explain what the agent should have done/i);
            if (feedbackTextareas.length > 0) {
              await user.type(feedbackTextareas[0], 'This is the correct behavior');

              const submitButtons = screen.getAllByRole('button').filter(btn =>
                btn.textContent === 'Submit Correction'
              );

              if (submitButtons.length > 0) {
                axios.post.mockResolvedValue({ data: { success: true } });
                await user.click(submitButtons[0]);
                // Should submit feedback
                expect(axios.post).toHaveBeenCalled();
              }
            }
          }
        }
      }
    });
  });

  // Accessibility tests
  describe('Accessibility', () => {
    it('should have proper headings', async () => {
      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Agent Studio' })).toBeInTheDocument();
      });
    });

    it('should have proper button labels', async () => {
      render(<AgentStudio />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /create new agent/i })).toBeInTheDocument();
      });
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: WebSocket trace updates, update flow, run variants,
// feedback/HITL error paths, schedule fields
// ---------------------------------------------------------------------------
describe('AgentStudio (extended coverage)', () => {
  const agentsData = () => ({
    data: [
      {
        id: 'agent-1',
        name: 'Test Agent',
        category: 'Operations',
        description: 'Test description',
        status: 'active',
        configuration: {
          system_prompt: 'You are helpful',
          tools: '*',
          scheduled_task: 'Old task'
        },
        schedule_config: { active: false, cron_expression: '0 9 * * *' }
      }
    ]
  });

  let errorSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    mockWsState.lastMessage = null;
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    axios.get.mockResolvedValue(agentsData());
    axios.post.mockResolvedValue({ data: { success: true } });
    axios.put.mockResolvedValue({ data: { success: true } });
  });

  afterEach(() => {
    errorSpy.mockRestore();
  });

  // Opens the edit dialog and returns a re-render helper that always produces
  // a fresh element (rerendering the identical element reference bails out).
  const openEditDialog = async () => {
    const makeTree = () => <AgentStudio />;
    const view = render(makeTree());
    await screen.findByText('Test Agent');

    const configureButtons = screen
      .getAllByRole('button')
      .filter((btn) => btn.textContent === 'Configure');
    fireEvent.click(configureButtons[0]);
    await screen.findByPlaceholderText(/enter a task to run/i);

    return {
      ...view,
      rerenderFresh: () => view.rerender(makeTree())
    };
  };

  const runTask = async (input = 'Test task') => {
    fireEvent.change(screen.getByPlaceholderText(/enter a task to run/i), {
      target: { value: input }
    });
    const playButtons = screen
      .getAllByRole('button')
      .filter((btn) => btn.querySelector('.lucide-play'));
    fireEvent.click(playButtons[0]);
  };

  test('updates an existing agent via PUT', async () => {
    const view = await openEditDialog();

    fireEvent.click(screen.getByRole('button', { name: /save agent/i }));

    await waitFor(() => {
      expect(axios.put).toHaveBeenCalledWith(
        '/api/agents/agent-1',
        expect.objectContaining({ name: 'Test Agent', category: 'Operations' })
      );
    });
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Updated', variant: 'success' })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    view.unmount();
  });

  test('edits the system prompt, schedule fields and saves', async () => {
    const view = await openEditDialog();

    fireEvent.change(screen.getByDisplayValue('You are helpful'), {
      target: { value: 'You are a wizard' }
    });

    // toggle schedule on
    fireEvent.click(screen.getByRole('switch'));
    fireEvent.change(screen.getByPlaceholderText('0 9 * * *'), {
      target: { value: '30 8 * * 1' }
    });
    fireEvent.change(screen.getByPlaceholderText(/generate daily summary/i), {
      target: { value: 'Weekly report task' }
    });

    fireEvent.click(screen.getByRole('button', { name: /save agent/i }));

    await waitFor(() => {
      expect(axios.put).toHaveBeenCalledWith(
        '/api/agents/agent-1',
        expect.objectContaining({
          configuration: expect.objectContaining({
            system_prompt: 'You are a wizard',
            scheduled_task: 'Weekly report task'
          }),
          schedule_config: { active: true, cron_expression: '30 8 * * 1' }
        })
      );
    });
    view.unmount();
  });

  test('stringifies object run results without steps', async () => {
    axios.post.mockResolvedValue({
      data: { status: 'completed', result: { odd: 'shape' } }
    });
    const view = await openEditDialog();

    await runTask();

    expect(await screen.findByText(/"odd": "shape"/)).toBeInTheDocument();
    view.unmount();
  });

  test('renders plain string run results', async () => {
    axios.post.mockResolvedValue({
      data: { status: 'completed', result: 'plain output' }
    });
    const view = await openEditDialog();

    await runTask();

    expect(await screen.findByText('plain output')).toBeInTheDocument();
    view.unmount();
  });

  test('reports run failures', async () => {
    axios.post.mockRejectedValue(new Error('run exploded'));
    const view = await openEditDialog();

    await runTask();

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Run Failed', variant: 'error' })
      );
    });
    expect(await screen.findByText('Error occurred.')).toBeInTheDocument();
    view.unmount();
  });

  test('rejects a pending HITL action and reports API failures', async () => {
    axios.post.mockResolvedValue({
      data: {
        status: 'completed',
        result: {
          steps: [
            {
              type: 'hitl_paused',
              action_id: 'action-9',
              action: { tool: 'email' },
              reason: 'Needs sign-off',
              status: 'pending'
            }
          ]
        }
      }
    });
    const view = await openEditDialog();

    await runTask('Send email');
    await screen.findByText(/human approval required/i);

    fireEvent.click(screen.getByRole('button', { name: /reject/i }));
    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith('/api/agents/approvals/action-9', {
        decision: 'rejected'
      });
    });

    // API failure path
    axios.post.mockRejectedValue(new Error('nope'));
    fireEvent.click(screen.getByRole('button', { name: /approve/i }));
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Failed to submit decision' })
      );
    });
    view.unmount();
  });

  test('submits feedback corrections and reports submission failures', async () => {
    axios.post.mockResolvedValue({
      data: {
        status: 'completed',
        result: {
          steps: [
            { step: 1, thought: 'Bad thought', action: { tool: 'x' }, output: 'Bad output' }
          ],
          final_output: 'Done'
        }
      }
    });
    const view = await openEditDialog();

    await runTask();
    await screen.findByText('Step 1');

    fireEvent.click(
      screen.getAllByRole('button').filter((b) => b.querySelector('.lucide-thumbs-down'))[0]
    );
    await screen.findByText('Provide Feedback');

    fireEvent.change(
      screen.getByPlaceholderText(/explain what the agent should have done/i),
      { target: { value: 'Do it correctly' } }
    );
    fireEvent.click(screen.getByRole('button', { name: /submit correction/i }));

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        '/api/agents/agent-1/feedback',
        expect.objectContaining({ user_correction: 'Do it correctly' })
      );
    });

    // failure path
    axios.post.mockRejectedValue(new Error('feedback down'));
    fireEvent.click(
      screen.getAllByRole('button').filter((b) => b.querySelector('.lucide-thumbs-down'))[0]
    );
    await screen.findByPlaceholderText(/explain what the agent should have done/i);
    fireEvent.click(screen.getByRole('button', { name: /submit correction/i }));
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ description: 'Failed to submit feedback' })
      );
    });

    // cancel closes the dialog (the edit dialog also has a Cancel button —
    // the feedback dialog is portaled later, so take the last match)
    fireEvent.click(screen.getAllByRole('button', { name: 'Cancel' }).pop()!);
    await waitFor(() => {
      expect(screen.queryByText('Provide Feedback')).not.toBeInTheDocument();
    });
    view.unmount();
  });

  test('appends, dedupes and completes WS agent steps during a live run', async () => {
    // Keep the run in-flight so isRunning stays true for WS updates.
    axios.post.mockImplementation(() => new Promise(() => {}));

    const view = await openEditDialog();
    await runTask('Live task');

    // step arrives over WS
    mockWsState.lastMessage = {
      type: 'agent_step_update',
      agent_id: 'agent-1',
      step: { step: 1, thought: 'First thought', output: 'First output' }
    };
    view.rerenderFresh();

    expect(await screen.findByText('First thought')).toBeInTheDocument();

    // duplicate step (same step + output) is ignored
    mockWsState.lastMessage = {
      type: 'agent_step_update',
      agent_id: 'agent-1',
      step: { step: 1, thought: 'First thought', output: 'First output' }
    };
    view.rerenderFresh();
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getAllByText('First thought').length).toBe(1);

    // same step number with new output updates in place
    mockWsState.lastMessage = {
      type: 'agent_step_update',
      agent_id: 'agent-1',
      step: { step: 1, output: 'Updated output' }
    };
    view.rerenderFresh();
    expect(await screen.findByText('Updated output')).toBeInTheDocument();
    expect(screen.queryByText('First output')).not.toBeInTheDocument();

    // status change completes the run: runResult is only rendered when the
    // trace is empty, so assert the run finished via the re-enabled play
    // button (it is disabled while isRunning).
    mockWsState.lastMessage = {
      type: 'agent_status_change',
      agent_id: 'agent-1',
      status: 'success',
      result: { output: 'WS final output' }
    };
    view.rerenderFresh();

    await waitFor(() => {
      const play = screen
        .getAllByRole('button')
        .find((btn) => btn.querySelector('.lucide-play'));
      expect(play).toBeEnabled();
    });
    view.unmount();
  });

  test('handles WS hitl_paused and hitl_decision messages during a live run', async () => {
    axios.post.mockImplementation(() => new Promise(() => {}));

    const view = await openEditDialog();
    await runTask('Needs approval');

    mockWsState.lastMessage = {
      type: 'hitl_paused',
      agent_id: 'agent-1',
      action_id: 'ws-action-1',
      tool: 'delete_file',
      reason: 'Destructive action'
    };
    view.rerenderFresh();

    expect(await screen.findByText(/human approval required/i)).toBeInTheDocument();
    expect(screen.getByText(/destructive action/i)).toBeInTheDocument();

    mockWsState.lastMessage = {
      type: 'hitl_decision',
      action_id: 'ws-action-1',
      decision: 'approved'
    };
    view.rerenderFresh();

    await waitFor(() => {
      expect(screen.getByText('APPROVED')).toBeInTheDocument();
    });
    view.unmount();
  });
});
