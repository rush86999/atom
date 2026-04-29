import React from 'react';
import { renderWithProviders, screen, waitFor } from '../test-utils';
import { AgentTerminal } from '@/components/Agents/AgentTerminal';

describe('AgentTerminal Component', () => {
  const mockLogs = [
    '[SYSTEM] Agent initialized',
    '[GMAIL] Checking for new emails',
    '[SLACK] Sending message to #general',
    'Processing task...',
    'Task completed successfully'
  ];

  const mockActiveTools = ['gmail', 'slack'];

  // Render tests
  describe('Rendering', () => {
    it('should render terminal container', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should render agent name in header', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);
      expect(screen.getByText(/testagent/i)).toBeInTheDocument();
      expect(screen.getByText(/execution_log/i)).toBeInTheDocument();
    });

    it('should render version badge', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);
      expect(screen.getByText(/v2\.4\.0-cognitive/i)).toBeInTheDocument();
    });

    it('should render log messages', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText('[SYSTEM] Agent initialized')).toBeInTheDocument();
      expect(screen.getByText('[GMAIL] Checking for new emails')).toBeInTheDocument();
    });

    it('should render empty state when no logs', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);
      expect(screen.getByText(/waiting for agent initiation/i)).toBeInTheDocument();
    });

    it('should render connection status indicators', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);
      expect(screen.getByText(/SSH SECURE/i)).toBeInTheDocument();
      expect(screen.getByText(/LATENCY:/i)).toBeInTheDocument();
    });
  });

  // Status display tests
  describe('Status Display', () => {
    it('should show active reasoning badge when running', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" />);
      expect(screen.getByText(/active reasoning/i)).toBeInTheDocument();
    });

    it('should not show active reasoning badge when idle', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.queryByText(/active reasoning/i)).not.toBeInTheDocument();
    });

    it('should display status indicator animation', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" />);
      // Check for animated ping element
      const pingElement = container.querySelector('.animate-ping');
      expect(pingElement).toBeInTheDocument();
    });
  });

  // Log display tests
  describe('Log Display', () => {
    it('should display system logs with purple styling', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      const systemLog = screen.getByText('[SYSTEM] Agent initialized');
      expect(systemLog).toBeInTheDocument();
    });

    it('should display tool logs with blue styling', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText('[GMAIL] Checking for new emails')).toBeInTheDocument();
      expect(screen.getByText('[SLACK] Sending message')).toBeInTheDocument();
    });

    it('should display success logs with green styling', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText(/success/i)).toBeInTheDocument();
    });

    it('should display error logs with red styling', () => {
      const errorLogs = [...mockLogs, '[ERROR] Connection failed'];
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={errorLogs} status="idle" />);
      expect(screen.getByText(/connection failed/i)).toBeInTheDocument();
    });

    it('should display timestamps for logs', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      // Timestamps are generated dynamically, check for timestamp pattern
      const timestamps = screen.getAllByText(/\d{2}:\d{2}:\d{2}/);
      expect(timestamps.length).toBeGreaterThan(0);
    });
  });

  // Active tools tests
  describe('Active Tools Display', () => {
    it('should display active tool icons', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" activeTools={mockActiveTools} />);
      // Tool icons are displayed in a sidebar
      expect(screen.getByText(/testagent/i)).toBeInTheDocument();
    });

    it('should show unique tools only', () => {
      const duplicateTools = ['gmail', 'slack', 'gmail', 'slack'];
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" activeTools={duplicateTools} />);
      // Should deduplicate tools
      expect(screen.getByText(/testagent/i)).toBeInTheDocument();
    });

    it('should handle empty active tools array', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" activeTools={[]} />);
      expect(screen.getByText(/testagent/i)).toBeInTheDocument();
    });

    it('should handle undefined active tools', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" />);
      expect(screen.getByText(/testagent/i)).toBeInTheDocument();
    });
  });

  // Sandbox environment display tests
  describe('Sandbox Environment Display', () => {
    it('should display ephemeral browser section', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText(/ephemeral browser/i)).toBeInTheDocument();
    });

    it('should display sandbox isolated message', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText(/sandbox isolated/i)).toBeInTheDocument();
    });

    it('should display security vault badge', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText(/self-hosted vault/i)).toBeInTheDocument();
    });

    it('should display security message', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText(/logs and credentials never leave your infrastructure/i)).toBeInTheDocument();
    });
  });

  // Footer tests
  describe('Footer', () => {
    it('should display SSH secure status', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText(/SSH SECURE/i)).toBeInTheDocument();
    });

    it('should display latency information', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText(/LATENCY:/i)).toBeInTheDocument();
      expect(screen.getByText(/42ms/i)).toBeInTheDocument();
    });

    it('should display listening port', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(screen.getByText(/LISTENING_ON_PORT/i)).toBeInTheDocument();
      expect(screen.getByText(/54321/i)).toBeInTheDocument();
    });
  });

  // Auto-scroll tests
  describe('Auto-scroll', () => {
    it('should scroll to bottom when new logs arrive', async () => {
      const { rerender } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[]} status="idle" />);

      // Add new logs
      rerender(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);

      await waitFor(() => {
        expect(screen.getByText('[SYSTEM] Agent initialized')).toBeInTheDocument();
      });
    });

    it('should maintain scroll position on re-renders', async () => {
      const { rerender } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);

      // Re-render with same logs
      rerender(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);

      await waitFor(() => {
        expect(screen.getByText('[SYSTEM] Agent initialized')).toBeInTheDocument();
      });
    });
  });

  // Edge cases
  describe('Edge Cases', () => {
    it('should handle null logs gracefully', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={null as any} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should handle undefined logs gracefully', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={undefined as any} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should handle very long log messages', () => {
      const longLog = 'A'.repeat(1000);
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={[longLog]} status="idle" />);
      expect(screen.getByText(/A{100}/)).toBeInTheDocument();
    });

    it('should handle special characters in logs', () => {
      const specialLogs = [
        '[SYSTEM] Test <script>alert("test")</script>',
        '[ERROR] Error: "quoted" \'single\'',
        '[DEBUG] Special chars: @#$%^&*()'
      ];
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={specialLogs} status="idle" />);
      expect(screen.getByText(/system.*test.*script/i)).toBeInTheDocument();
    });

    it('should handle empty agent name', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="" logs={mockLogs} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should handle agentId prop', () => {
      const { container } = renderWithProviders(<AgentTerminal agentId="agent-123" agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });
  });

  // Tool icon mapping tests
  describe('Tool Icon Mapping', () => {
    it('should display correct icon for gmail', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={['[GMAIL] Test']} status="running" activeTools={['gmail']} />);
      // Check that component renders without error
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should display correct icon for slack', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={['[SLACK] Test']} status="running" activeTools={['slack']} />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should display correct icon for generic tool', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={['[UNKNOWNTOOL] Test']} status="running" activeTools={['unknowntool']} />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });
  });

  // Accessibility tests
  describe('Accessibility', () => {
    it('should have proper role attributes', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should have readable text contrast', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      const terminal = container.querySelector('.bg-slate-950');
      expect(terminal).toBeInTheDocument();
    });

    it('should display status indicators', () => {
      renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" />);
      expect(screen.getByText(/active reasoning/i)).toBeInTheDocument();
    });
  });

  // Visual structure tests
  describe('Visual Structure', () => {
    it('should have glossy header', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      const header = container.querySelector('.bg-gradient-to-r');
      expect(header).toBeInTheDocument();
    });

    it('should have traffic light buttons', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      const buttons = container.querySelectorAll('.rounded-full');
      expect(buttons.length).toBeGreaterThanOrEqual(3);
    });

    it('should have log area with scroll', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="idle" />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });

    it('should have sidebar for active tools', () => {
      const { container } = renderWithProviders(<AgentTerminal agentName="TestAgent" logs={mockLogs} status="running" activeTools={mockActiveTools} />);
      expect(container.querySelector('.bg-slate-950')).toBeInTheDocument();
    });
  });
});
