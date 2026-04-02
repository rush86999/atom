import type { Meta, StoryObj } from '@storybook/react';
import { SupervisedAgentMonitor } from './SupervisedAgentMonitor';

const meta: Meta<typeof SupervisedAgentMonitor> = {
  title: 'Canvas/Monitoring/SupervisedAgentMonitor',
  component: SupervisedAgentMonitor,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof SupervisedAgentMonitor>;

// Idle agent state (pending)
export const Pending: Story = {
  args: {
    executionId: 'exec-pending-123',
    agentId: 'agent-finance-001',
    agentName: 'FinanceReconciler',
    supervisorInfo: {
      type: 'user',
      user_id: 'user-123',
    },
  },
};

// Active agent state (simulated running)
export const Running: Story = {
  args: {
    executionId: 'exec-running-456',
    agentId: 'agent-coding-002',
    agentName: 'CodeReviewer',
    supervisorInfo: {
      type: 'autonomous_agent',
      agent_id: 'agent-auto-789',
      name: 'AutoChief',
    },
  },
};

// Multiple agents (would need to render multiple instances)
export const MultipleAgents: Story = {
  render: () => (
    <div className="space-y-4 max-w-2xl">
      <SupervisedAgentMonitor
        executionId="exec-multi-1"
        agentId="agent-001"
        agentName="FinanceReconciler"
        supervisorInfo={{
          type: 'autonomous_agent',
          agent_id: 'agent-chief',
          name: 'AutoChief',
        }}
      />
      <SupervisedAgentMonitor
        executionId="exec-multi-2"
        agentId="agent-002"
        agentName="DataAnalyzer"
        supervisorInfo={{
          type: 'user',
          user_id: 'user-123',
        }}
      />
      <SupervisedAgentMonitor
        executionId="exec-multi-3"
        agentId="agent-003"
        agentName="ReportGenerator"
        supervisorInfo={{
          type: 'autonomous_agent',
          agent_id: 'agent-chief',
          name: 'AutoChief',
        }}
      />
    </div>
  ),
};

// Error state (simulated failed execution)
export const Error: Story = {
  args: {
    executionId: 'exec-error-789',
    agentId: 'agent-broken-003',
    agentName: 'FaultyAgent',
    supervisorInfo: {
      type: 'user',
      user_id: 'user-123',
    },
    onError: (error) => console.error('Agent error:', error),
  },
};

// Empty state (no logs yet)
export const Empty: Story = {
  args: {
    executionId: 'exec-empty-000',
    agentId: 'agent-new-004',
    agentName: 'NewAgent',
    supervisorInfo: {
      type: 'autonomous_agent',
      agent_id: 'agent-chief',
      name: 'AutoChief',
    },
  },
};

// User supervision
export const UserSupervised: Story = {
  args: {
    executionId: 'exec-user-101',
    agentId: 'agent-task-202',
    agentName: 'TaskExecutor',
    supervisorInfo: {
      type: 'user',
      user_id: 'user-456',
    },
    onComplete: (result) => console.log('Task completed:', result),
  },
};

// Autonomous agent supervision
export const AutonomousSupervised: Story = {
  args: {
    executionId: 'exec-auto-303',
    agentId: 'agent-worker-404',
    agentName: 'DataProcessor',
    supervisorInfo: {
      type: 'autonomous_agent',
      agent_id: 'agent-supervisor-999',
      name: 'SupervisorBot',
    },
    onComplete: (result) => console.log('Processing complete:', result),
  },
};

// Light theme
export const LightTheme: Story = {
  args: {
    executionId: 'exec-light-505',
    agentId: 'agent-light-606',
    agentName: 'ThemeTester',
    supervisorInfo: {
      type: 'user',
      user_id: 'user-789',
    },
  },
  globals: {
    theme: 'light',
  },
};

// Dark theme
export const DarkTheme: Story = {
  args: {
    executionId: 'exec-dark-707',
    agentId: 'agent-dark-808',
    agentName: 'DarkTester',
    supervisorInfo: {
      type: 'autonomous_agent',
      agent_id: 'agent-auto-999',
      name: 'NightSupervisor',
    },
  },
  globals: {
    theme: 'dark',
  },
  parameters: {
    backgrounds: {
      default: 'dark',
    },
  },
};
