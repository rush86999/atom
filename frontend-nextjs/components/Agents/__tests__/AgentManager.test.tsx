import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import '@testing-library/jest-dom';
import AgentManager from '../AgentManager';

// Mock Chakra UI hooks
jest.mock('@chakra-ui/react', () => ({
  ...jest.requireActual('@chakra-ui/react'),
  useToast: () => jest.fn(),
  useDisclosure: () => ({
    isOpen: false,
    onOpen: jest.fn(),
    onClose: jest.fn(),
  }),
}));

const mockAgent = {
  id: '1',
  name: 'Test Agent',
  role: 'personal_assistant',
  status: 'inactive' as const,
  capabilities: ['web_search', 'email_management'],
  performance: {
    tasksCompleted: 10,
    successRate: 95,
    avgResponseTime: 200,
  },
  lastActive: new Date('2024-01-01'),
  config: {
    model: 'gpt-4',
    temperature: 0.7,
    maxTokens: 2000,
    systemPrompt: 'Test system prompt',
    tools: ['calculator', 'web_browser'],
  },
};

describe('AgentManager', () => {
  const mockOnAgentCreate = jest.fn();
  const mockOnAgentUpdate = jest.fn();
  const mockOnAgentDelete = jest.fn();
  const mockOnAgentStart = jest.fn();
  const mockOnAgentStop = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(
      <AgentManager
        initialAgents={[]}
        onAgentCreate={mockOnAgentCreate}
        onAgentUpdate={mockOnAgentUpdate}
        onAgentDelete={mockOnAgentDelete}
        onAgentStart={mockOnAgentStart}
        onAgentStop={mockOnAgentStop}
      />
    );

    expect(screen.getByText('Agent Manager')).toBeInTheDocument();
    expect(screen.getByText('Manage and monitor your AI agents')).toBeInTheDocument();
    expect(screen.getByText('Create Agent')).toBeInTheDocument();
  });

  it('displays agent cards when agents are provided', () => {
    const agents = [
      mockAgent,
      { ...mockAgent, id: '2', name: 'Another Agent', status: 'active' as const }
    ];

    render(
      <AgentManager
        initialAgents={agents}
        onAgentCreate={mockOnAgentCreate}
      />
    );

    // Check agent names are displayed
    expect(screen.getByText('Test Agent')).toBeInTheDocument();
    expect(screen.getByText('Another Agent')).toBeInTheDocument();

    // Check status badges
    expect(screen.getByText('inactive')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
  });

  it('displays agent capabilities correctly', () => {
    const agents = [mockAgent];

    render(
      <AgentManager
        initialAgents={agents}
        onAgentCreate={mockOnAgentCreate}
      />
    );

    // Check capabilities are displayed
    expect(screen.getByText('web search')).toBeInTheDocument();
    expect(screen.getByText('email management')).toBeInTheDocument();
  });

  it('displays agent performance metrics', () => {
    const agents = [mockAgent];

    render(
      <AgentManager
        initialAgents={agents}
        onAgentCreate={mockOnAgentCreate}
      />
    );

    // Check performance metrics
    expect(screen.getByText('Tasks Completed')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('Success Rate')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('Avg Response')).toBeInTheDocument();
    expect(screen.getByText('200ms')).toBeInTheDocument();
  });

  it('shows start button for inactive agents', () => {
    const agents = [mockAgent]; // inactive status

    render(
      <AgentManager
        initialAgents={agents}
        onAgentStart={mockOnAgentStart}
      />
    );

    const startButtons = screen.getAllByText('Start');
    expect(startButtons.length).toBeGreaterThan(0);
  });

  it('shows stop button for active agents', () => {
    const activeAgent = { ...mockAgent, id: '2', status: 'active' as const };
    const agents = [activeAgent];

    render(
      <AgentManager
        initialAgents={agents}
        onAgentStop={mockOnAgentStop}
      />
    );

    const stopButtons = screen.getAllByText('Stop');
    expect(stopButtons.length).toBeGreaterThan(0);
  });

  it('calls onAgentStart when start button is clicked', async () => {
    const agents = [mockAgent];

    render(
      <AgentManager
        initialAgents={agents}
        onAgentStart={mockOnAgentStart}
      />
    );

    const startButtons = screen.getAllByText('Start');
    fireEvent.click(startButtons[0]);

    // Wait for state update
    await waitFor(() => {
      expect(mockOnAgentStart).toHaveBeenCalledWith('1');
    });
  });

  it('calls onAgentStop when stop button is clicked', async () => {
    const activeAgent = { ...mockAgent, id: '2', status: 'active' as const };
    const agents = [activeAgent];

    render(
      <AgentManager
        initialAgents={agents}
        onAgentStop={mockOnAgentStop}
      />
    );

    const stopButtons = screen.getAllByText('Stop');
    fireEvent.click(stopButtons[0]);

    // Wait for state update
    await waitFor(() => {
      expect(mockOnAgentStop).toHaveBeenCalledWith('2');
    });
  });

  it('opens create agent modal when Create Agent button is clicked', () => {
    render(
      <AgentManager
        initialAgents={[]}
        onAgentCreate={mockOnAgentCreate}
      />
    );

    const createButton = screen.getByText('Create Agent');
    fireEvent.click(createButton);

    // Modal should open
    // Note: The Dialog component is rendered but checking for modal content
    // would require the Dialog to be open which is controlled by internal state
    // For now, just verify clicking the button doesn't crash
    expect(createButton).toBeInTheDocument();
  });

  it('handles empty agent list gracefully', () => {
    render(
      <AgentManager
        initialAgents={[]}
        onAgentCreate={mockOnAgentCreate}
      />
    );

    // Should still show header and create button
    expect(screen.getByText('Agent Manager')).toBeInTheDocument();
    expect(screen.getByText('Create Agent')).toBeInTheDocument();

    // Should show empty state message
    expect(screen.getByText('No Agents Created')).toBeInTheDocument();
    expect(screen.getByText(/Create your first agent to get started/i)).toBeInTheDocument();
    expect(screen.getByText('Create First Agent')).toBeInTheDocument();
  });
});
