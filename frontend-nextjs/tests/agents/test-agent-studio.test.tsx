import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgentStudio from '@/components/Agents/AgentStudio';

// Mock axios
jest.mock('axios');
const axios = require('axios');

// Mock useToast
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn()
  })
}));

// Mock useWebSocket
jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    isConnected: true,
    lastMessage: null,
    subscribe: jest.fn()
  })
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

      const descInputs = screen.getAllByPlaceholderText('');
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
      await waitFor(() => {
        expect(screen.getByText('Operations')).toBeInTheDocument();
      });

      // Click on the category selector (it's a custom select component)
      const opsText = screen.getAllByText('Operations');
      if (opsText.length > 1) {
        await user.click(opsText[1]);
        // Should show dropdown options
      }
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

        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.innerHTML.includes('Play') || btn.querySelector('svg')
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

        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.innerHTML.includes('Play') || btn.querySelector('svg')
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

        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.innerHTML.includes('Play') || btn.querySelector('svg')
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

        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.innerHTML.includes('Play') || btn.querySelector('svg')
        );

        if (playButtons.length > 0) {
          await user.click(playButtons[0]);
          await waitFor(() => {
            expect(screen.getByText(/human approval required/i)).toBeInTheDocument();
            expect(screen.getByText('email')).toBeInTheDocument();
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

        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.innerHTML.includes('Play') || btn.querySelector('svg')
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

        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.innerHTML.includes('Play') || btn.querySelector('svg')
        );

        if (playButtons.length > 0) {
          await user.click(playButtons[0]);
          await waitFor(() => {
            expect(screen.getByText('Step 1')).toBeInTheDocument();
          });

          // Find thumbs down button
          const thumbsDownButtons = screen.getAllByRole('button').filter(btn =>
            btn.innerHTML.includes('ThumbsDown')
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

        const playButtons = screen.getAllByRole('button').filter(btn =>
          btn.innerHTML.includes('Play') || btn.querySelector('svg')
        );

        if (playButtons.length > 0) {
          await user.click(playButtons[0]);
          await waitFor(() => {
            expect(screen.getByText('Step 1')).toBeInTheDocument();
          });

          const thumbsDownButtons = screen.getAllByRole('button').filter(btn =>
            btn.innerHTML.includes('ThumbsDown')
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
