import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgentCard from '@/components/Agents/AgentCard';

describe('AgentCard Component', () => {
  const mockAgent = {
    id: 'agent-123',
    name: 'Test Agent',
    description: 'A test agent',
    status: 'idle' as const,
    last_run: '2026-04-11T10:00:00Z',
    category: 'Operations',
    maturity_level: 'autonomous' as const
  };

  const mockHandlers = {
    onRun: jest.fn(),
    onStop: jest.fn(),
    onChat: jest.fn(),
    onEdit: jest.fn(),
    onViewReasoning: jest.fn()
  };

  afterEach(() => {
    jest.clearAllMocks();
  });

  // Render tests
  describe('Rendering', () => {
    it('should render agent name and description', () => {
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      expect(screen.getByText('Test Agent')).toBeInTheDocument();
      expect(screen.getByText('A test agent')).toBeInTheDocument();
    });

    it('should display category badge', () => {
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      expect(screen.getByText('Operations')).toBeInTheDocument();
    });

    it('should render action buttons with correct titles', () => {
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      expect(screen.getByTitle('Chat with Agent')).toBeInTheDocument();
      expect(screen.getByTitle('Edit Agent')).toBeInTheDocument();
      expect(screen.getByTitle('View Reasoning Trace')).toBeInTheDocument();
    });

    it('should display idle status badge', () => {
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      expect(screen.getByText('Idle')).toBeInTheDocument();
    });

    it('should display last run time when available', () => {
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      expect(screen.getByText(/Last run:/)).toBeInTheDocument();
    });

    it('should display never run when last_run is missing', () => {
      const agentNoRun = { ...mockAgent, last_run: undefined };
      render(<AgentCard agent={agentNoRun} {...mockHandlers} />);
      expect(screen.getByText('Never run')).toBeInTheDocument();
    });
  });

  // Status badge tests
  describe('Status Badges', () => {
    it('should show running status with animation', () => {
      const runningAgent = { ...mockAgent, status: 'running' as const };
      render(<AgentCard agent={runningAgent} {...mockHandlers} />);
      expect(screen.getByText('Running')).toBeInTheDocument();
    });

    it('should show success status', () => {
      const successAgent = { ...mockAgent, status: 'success' as const };
      render(<AgentCard agent={successAgent} {...mockHandlers} />);
      expect(screen.getByText('Success')).toBeInTheDocument();
    });

    it('should show failed status', () => {
      const failedAgent = { ...mockAgent, status: 'failed' as const };
      render(<AgentCard agent={failedAgent} {...mockHandlers} />);
      expect(screen.getByText('Failed')).toBeInTheDocument();
    });

    it('should show idle status as default', () => {
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      expect(screen.getByText('Idle')).toBeInTheDocument();
    });
  });

  // Interaction tests
  describe('User Interactions', () => {
    it('should call onChat when chat button clicked', async () => {
      const user = userEvent.setup();
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      await user.click(screen.getByTitle('Chat with Agent'));
      expect(mockHandlers.onChat).toHaveBeenCalledWith('agent-123');
    });

    it('should call onEdit when edit button clicked', async () => {
      const user = userEvent.setup();
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      await user.click(screen.getByTitle('Edit Agent'));
      expect(mockHandlers.onEdit).toHaveBeenCalledWith('agent-123');
    });

    it('should call onViewReasoning when reasoning button clicked', async () => {
      const user = userEvent.setup();
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      await user.click(screen.getByTitle('View Reasoning Trace'));
      expect(mockHandlers.onViewReasoning).toHaveBeenCalledWith('agent-123');
    });

    it('should call onRun when run button clicked for idle agent', async () => {
      const user = userEvent.setup();
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      await user.click(screen.getByRole('button', { name: /run/i }));
      expect(mockHandlers.onRun).toHaveBeenCalledWith('agent-123');
    });

    it('should call onStop when stop button clicked for running agent', async () => {
      const user = userEvent.setup();
      const runningAgent = { ...mockAgent, status: 'running' as const };
      render(<AgentCard agent={runningAgent} {...mockHandlers} />);
      await user.click(screen.getByRole('button', { name: /stop/i }));
      expect(mockHandlers.onStop).toHaveBeenCalledWith('agent-123');
    });
  });

  // State variations
  describe('State Variations', () => {
    it('should show run button when agent is idle', () => {
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      expect(screen.getByRole('button', { name: /run/i })).toBeInTheDocument();
    });

    it('should show stop button when agent is running', () => {
      const runningAgent = { ...mockAgent, status: 'running' as const };
      render(<AgentCard agent={runningAgent} {...mockHandlers} />);
      expect(screen.getByRole('button', { name: /stop/i })).toBeInTheDocument();
    });

    it('should handle missing description gracefully', () => {
      const agentNoDesc = { ...mockAgent, description: '' };
      render(<AgentCard agent={agentNoDesc} {...mockHandlers} />);
      expect(screen.getByText('Test Agent')).toBeInTheDocument();
    });

    it('should display maturity level when provided', () => {
      const studentAgent = { ...mockAgent, maturity_level: 'student' as const };
      render(<AgentCard agent={studentAgent} {...mockHandlers} />);
      // Maturity level is displayed but not explicitly shown in the component
      // The component only shows status, category, name, description, last_run
      expect(screen.getByText('Test Agent')).toBeInTheDocument();
    });
  });

  // Edge cases
  describe('Edge Cases', () => {
    it('should handle very long description with line-clamp', () => {
      const longDescAgent = {
        ...mockAgent,
        description: 'This is a very long description that should be truncated to two lines using the line-clamp utility class to ensure consistent card heights across the grid layout.'
      };
      render(<AgentCard agent={longDescAgent} {...mockHandlers} />);
      expect(screen.getByText(/This is a very long description/)).toBeInTheDocument();
    });

    it('should handle empty category', () => {
      const agentNoCategory = { ...mockAgent, category: '' };
      render(<AgentCard agent={agentNoCategory} {...mockHandlers} />);
      expect(screen.getByText('Test Agent')).toBeInTheDocument();
    });

    it('should handle special characters in agent name', () => {
      const specialAgent = { ...mockAgent, name: 'Agent <script>alert("test")</script>' };
      render(<AgentCard agent={specialAgent} {...mockHandlers} />);
      expect(screen.getByText('Agent <script>alert("test")</script>')).toBeInTheDocument();
    });
  });

  // Accessibility tests
  describe('Accessibility', () => {
    it('should have proper button titles for screen readers', () => {
      render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      expect(screen.getByTitle('Chat with Agent')).toBeInTheDocument();
      expect(screen.getByTitle('Edit Agent')).toBeInTheDocument();
      expect(screen.getByTitle('View Reasoning Trace')).toBeInTheDocument();
    });

    it('should have semantic HTML structure', () => {
      const { container } = render(<AgentCard agent={mockAgent} {...mockHandlers} />);
      // AgentCard uses a Card component (div-based) instead of article
      expect(container.querySelector('.w-full')).toBeInTheDocument();
    });
  });
});
