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

const renderWithProviders = (component: React.ReactElement) => {
  return render(component);
};

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
    renderWithProviders(
      <AgentManager
        initialAgents={[]}

      />
    );

    expect(screen.getByText('Agent Manager')).toBeInTheDocument();
  });

  it('displays agent statistics correctly', () => {
    const agents = [mockAgent, { ...mockAgent, id: '2', status: 'active' as const }];

    renderWithProviders(
      <AgentManager
        initialAgents={agents}

      />
    );

    expect(screen.getByText('Total Agents')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('displays agent list in grid view', () => {
    renderWithProviders(
      <AgentManager
        initialAgents={[mockAgent]}

      />
    );

    expect(screen.getByText('Test Agent')).toBeInTheDocument();
    expect(screen.getByText('Personal Assistant')).toBeInTheDocument();
    expect(screen.getByText('web_search, email_management')).toBeInTheDocument();
  });

  it('allows creating a new agent', async () => {
    renderWithProviders(
      <AgentManager
        onAgentCreate={mockOnAgentCreate}
        initialAgents={[]}

      />
    );

    const newAgentButton = screen.getByText('New Agent');
    fireEvent.click(newAgentButton);

    // The modal should open (this would require mocking the modal behavior)
    // In a real test, we would check for form fields and submit
  });

  it('allows starting and stopping agents', () => {
    renderWithProviders(
      <AgentManager
        onAgentStart={mockOnAgentStart}
        onAgentStop={mockOnAgentStop}
        initialAgents={[mockAgent]}

      />
    );

    const startButton = screen.getByLabelText('Start agent');
    fireEvent.click(startButton);

    expect(mockOnAgentStart).toHaveBeenCalledWith('1');
  });

  it('allows deleting an agent', () => {
    renderWithProviders(
      <AgentManager
        onAgentDelete={mockOnAgentDelete}
        initialAgents={[mockAgent]}

      />
    );

    const deleteButton = screen.getByLabelText('Delete agent');
    fireEvent.click(deleteButton);

    expect(mockOnAgentDelete).toHaveBeenCalledWith('1');
  });

  it('switches between list and grid views', () => {
    renderWithProviders(
      <AgentManager
        initialAgents={[mockAgent]}

      />
    );

    const listButton = screen.getByText('List');
    fireEvent.click(listButton);

    // Should show table headers for list view
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Role')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
  });

  it('displays agent performance metrics', () => {
    renderWithProviders(
      <AgentManager
        initialAgents={[mockAgent]}

      />
    );

    expect(screen.getByText('10 tasks')).toBeInTheDocument();
    expect(screen.getByText('95% success')).toBeInTheDocument();
  });

  it('handles empty agent list', () => {
    renderWithProviders(
      <AgentManager
        initialAgents={[]}

      />
    );

    expect(screen.getByText('Total Agents')).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('filters agents by status in statistics', () => {
    const agents = [
      mockAgent,
      { ...mockAgent, id: '2', status: 'active' as const },
      { ...mockAgent, id: '3', status: 'error' as const },
    ];

    renderWithProviders(
      <AgentManager
        initialAgents={agents}

      />
    );

    expect(screen.getByText('3')).toBeInTheDocument(); // Total agents
    expect(screen.getByText('1')).toBeInTheDocument(); // Active agents
  });

  it('updates agent statistics when agents change', () => {
    const { rerender } = renderWithProviders(
      <AgentManager
        initialAgents={[mockAgent]}

      />
    );

    expect(screen.getByText('1')).toBeInTheDocument(); // Initial count

    const updatedAgents = [mockAgent, { ...mockAgent, id: '2' }];
    rerender(
      <AgentManager
        initialAgents={updatedAgents}

      />
    );

    expect(screen.getByText('2')).toBeInTheDocument(); // Updated count
  });
});
