import React from 'react';
import { renderWithProviders, screen, waitFor } from '../test-utils';
import { AgentTerminal, LogEntry } from '@/components/Agents/AgentTerminal';

describe('AgentTerminal Component', () => {
  // Fixed timestamps: the terminal must render the ts captured at append
  // time, not the time of the latest re-render (a past regression).
  const T1 = new Date('2026-01-01T10:00:00').getTime();
  const T2 = new Date('2026-01-01T10:00:05').getTime();

  const entry = (text: string, ts: number = T1): LogEntry => ({ text, ts });

  const mockLogs: LogEntry[] = [
    entry('Thought: Checking inventory levels'),
    entry('Action: {"name": "search"}', T2),
    entry('Observation: found 3 records', T2),
    entry('Task completed successfully', T2),
  ];

  // Render tests
  describe('Rendering', () => {
    it('should render terminal container', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should render agent name in header', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);
      expect(screen.getByText('TestAgent')).toBeInTheDocument();
    });

    it('should render log messages', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText('Thought: Checking inventory levels')).toBeInTheDocument();
      expect(screen.getByText('Observation: found 3 records')).toBeInTheDocument();
    });

    it('should render empty state when no logs', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);
      expect(screen.getByText(/no activity yet/i)).toBeInTheDocument();
      expect(screen.getByText(/run an agent/i)).toBeInTheDocument();
    });

    it('should not render fabricated telemetry', () => {
      // These were hardcoded decorations that claimed false system state.
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" />);
      expect(screen.queryByText(/latency/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/ssh/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/54321/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/cognitive/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/ephemeral browser/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/sandbox isolated/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/execution_log/i)).not.toBeInTheDocument();
    });
  });

  // Status display tests
  describe('Status Display', () => {
    it('should show Running badge when running', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" />);
      expect(screen.getByText('Running')).toBeInTheDocument();
    });

    it('should show Completed badge on success', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="success" />);
      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    it('should show Failed badge on failure', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="failed" />);
      expect(screen.getByText('Failed')).toBeInTheDocument();
    });

    it('should show Idle badge when idle', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText('Idle')).toBeInTheDocument();
    });

    it('should show pulse animation while running', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" />);
      expect(container.querySelector('.animate-ping')).toBeInTheDocument();
    });

    it('should not show pulse animation when idle', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(container.querySelector('.animate-ping')).not.toBeInTheDocument();
    });
  });

  // Log display tests
  describe('Log Display', () => {
    it('should display success logs with green styling', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      const successLog = screen.getByText('Task completed successfully');
      expect(successLog.className).toMatch(/emerald/);
    });

    it('should display error logs with red styling', () => {
      const errorLogs = [...mockLogs, entry('Error: Connection failed')];
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={errorLogs} status="idle" />);
      const errorLog = screen.getByText('Error: Connection failed');
      expect(errorLog.className).toMatch(/red/);
    });

    it('should display final answer logs prominently', () => {
      const logs = [...mockLogs, entry('Final Answer: 42')];
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={logs} status="idle" />);
      const finalLog = screen.getByText('Final Answer: 42');
      expect(finalLog.className).toMatch(/emerald/);
      expect(finalLog.className).toMatch(/font-semibold/);
    });

    it('should render the timestamp captured at append time', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      // T1 and T2 were fixed when the entries were created; both must render
      // regardless of when the component re-renders. Anchored so the footer's
      // "Last event ..." label doesn't count as a line timestamp.
      expect(screen.getAllByText(/^\d{2}:\d{2}:\d{2}$/).length).toBe(mockLogs.length);
    });

    it('should keep per-line timestamps distinct after re-render', () => {
      const { rerender } = renderWithProviders(
        <AgentTerminal agentName="TestAgent" logs={[entry('First', T1)]} status="idle" />
      );
      rerender(<AgentTerminal agentName="TestAgent" logs={[entry('First', T1), entry('Second', T2)]} status="idle" />);
      // The old line keeps its original timestamp instead of being redrawn
      // with the current time.
      expect(screen.getByText('10:00:00')).toBeInTheDocument();
      expect(screen.getByText('10:00:05')).toBeInTheDocument();
    });
  });

  // Footer tests
  describe('Footer', () => {
    it('should display the real event count', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByTestId('terminal-event-count')).toHaveTextContent('4 events');
    });

    it('should display singular event count', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[entry('Only one')]} status="idle" />);
      expect(screen.getByTestId('terminal-event-count')).toHaveTextContent('1 event');
    });

    it('should display last event time', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText(/Last event/)).toBeInTheDocument();
    });
  });

  // Auto-scroll tests
  describe('Auto-scroll', () => {
    it('should scroll to bottom when new logs arrive', async () => {
      const { rerender } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);

      rerender(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);

      await waitFor(() => {
        expect(screen.getByText('Thought: Checking inventory levels')).toBeInTheDocument();
      });
    });

    it('should keep log content stable across re-renders', async () => {
      const { rerender } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      rerender(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);

      await waitFor(() => {
        expect(screen.getByText('Task completed successfully')).toBeInTheDocument();
      });
    });
  });

  // Edge cases
  describe('Edge Cases', () => {
    it('should render with empty logs array', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should handle very long log messages', () => {
      const longLog = 'A'.repeat(1000);
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[entry(longLog)]} status="idle" />);
      expect(screen.getByText(/A{100}/)).toBeInTheDocument();
    });

    it('should handle special characters in logs', () => {
      const specialLogs = [
        entry('Thought: Test <script>alert("test")</script>'),
        entry('Error: "quoted" \'single\''),
        entry('Special chars: @#$%^&*()'),
      ];
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={specialLogs} status="idle" />);
      expect(screen.getByText(/thought.*test.*script/i)).toBeInTheDocument();
    });

    it('should handle empty agent name', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="" logs={mockLogs} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should handle agentId prop', () => {
      const { container } = renderWithProviders(<AgentTerminal agentId="agent-123" agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should fall back to Idle badge for unknown statuses', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="some-new-status" />);
      expect(screen.getByText('Idle')).toBeInTheDocument();
    });
  });

  // Visual structure tests
  describe('Visual Structure', () => {
    it('should have a header with agent identity and status', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
      expect(screen.getByText('TestAgent')).toBeInTheDocument();
      expect(screen.getByText('Running')).toBeInTheDocument();
    });

    it('should have log area with scroll', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });
  });
});
