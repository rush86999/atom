import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock Agent Context
interface AgentContextType {
  agentId: string | null;
  agentName: string | null;
  maturity: 'STUDENT' | 'INTERN' | 'SUPERVISED' | 'AUTONOMOUS' | null;
  isConnected: boolean;
  setAgent: (id: string, name: string, maturity: string) => void;
  clearAgent: () => void;
}

const AgentContext = React.createContext<AgentContextType | null>(null);

// Mock Provider Component
const MockAgentProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [agentId, setAgentId] = React.useState<string | null>(null);
  const [agentName, setAgentName] = React.useState<string | null>(null);
  const [maturity, setMaturity] = React.useState<'STUDENT' | 'INTERN' | 'SUPERVISED' | 'AUTONOMOUS' | null>(null);
  const [isConnected, setIsConnected] = React.useState(false);

  const setAgent = (id: string, name: string, maturityLevel: string) => {
    setAgentId(id);
    setAgentName(name);
    setMaturity(maturityLevel as any);
    setIsConnected(true);
  };

  const clearAgent = () => {
    setAgentId(null);
    setAgentName(null);
    setMaturity(null);
    setIsConnected(false);
  };

  return (
    <AgentContext.Provider value={{ agentId, agentName, maturity, isConnected, setAgent, clearAgent }}>
      {children}
    </AgentContext.Provider>
  );
};

// Mock Consumer Component
const MockAgentConsumer: React.FC = () => {
  const context = React.useContext(AgentContext);

  if (!context) {
    return <div>No context</div>;
  }

  return (
    <div data-testid="agent-consumer">
      <div data-testid="agent-id">{context.agentId || 'No agent'}</div>
      <div data-testid="agent-name">{context.agentName || 'No name'}</div>
      <div data-testid="agent-maturity">{context.maturity || 'No maturity'}</div>
      <div data-testid="agent-connected">{context.isConnected ? 'Connected' : 'Disconnected'}</div>
      <button
        data-testid="set-agent-btn"
        onClick={() => context.setAgent('agent-123', 'Test Agent', 'AUTONOMOUS')}
      >
        Set Agent
      </button>
      <button data-testid="clear-agent-btn" onClick={context.clearAgent}>
        Clear Agent
      </button>
    </div>
  );
};

describe('AgentContext Tests', () => {
  describe('test_agent_context_initial_value', () => {
    it('should provide initial null values', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      expect(screen.getByTestId('agent-id')).toHaveTextContent('No agent');
      expect(screen.getByTestId('agent-name')).toHaveTextContent('No name');
      expect(screen.getByTestId('agent-maturity')).toHaveTextContent('No maturity');
      expect(screen.getByTestId('agent-connected')).toHaveTextContent('Disconnected');
    });

    it('should have all required context properties', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      expect(screen.getByTestId('agent-id')).toBeInTheDocument();
      expect(screen.getByTestId('agent-name')).toBeInTheDocument();
      expect(screen.getByTestId('agent-maturity')).toBeInTheDocument();
      expect(screen.getByTestId('agent-connected')).toBeInTheDocument();
      expect(screen.getByTestId('set-agent-btn')).toBeInTheDocument();
      expect(screen.getByTestId('clear-agent-btn')).toBeInTheDocument();
    });

    it('should start in disconnected state', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      expect(screen.getByTestId('agent-connected')).toHaveTextContent('Disconnected');
    });
  });

  describe('test_agent_context_update', () => {
    it('should update agent information', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      const setButton = screen.getByTestId('set-agent-btn');
      fireEvent.click(setButton);

      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');
      expect(screen.getByTestId('agent-name')).toHaveTextContent('Test Agent');
      expect(screen.getByTestId('agent-maturity')).toHaveTextContent('AUTONOMOUS');
      expect(screen.getByTestId('agent-connected')).toHaveTextContent('Connected');
    });

    it('should update connection status when agent is set', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      expect(screen.getByTestId('agent-connected')).toHaveTextContent('Disconnected');

      const setButton = screen.getByTestId('set-agent-btn');
      fireEvent.click(setButton);

      expect(screen.getByTestId('agent-connected')).toHaveTextContent('Connected');
    });

    it('should handle multiple agent updates', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      const setButton = screen.getByTestId('set-agent-btn');

      fireEvent.click(setButton);
      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');

      fireEvent.click(setButton);
      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');

      const idElement = screen.getByTestId('agent-id');
      expect(idElement.textContent).toBe('agent-123');
    });

    it('should update maturity level correctly', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      const setButton = screen.getByTestId('set-agent-btn');
      fireEvent.click(setButton);

      expect(screen.getByTestId('agent-maturity')).toHaveTextContent('AUTONOMOUS');
    });

    it('should clear agent information', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      const setButton = screen.getByTestId('set-agent-btn');
      fireEvent.click(setButton);

      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');

      const clearButton = screen.getByTestId('clear-agent-btn');
      fireEvent.click(clearButton);

      expect(screen.getByTestId('agent-id')).toHaveTextContent('No agent');
      expect(screen.getByTestId('agent-name')).toHaveTextContent('No name');
      expect(screen.getByTestId('agent-maturity')).toHaveTextContent('No maturity');
      expect(screen.getByTestId('agent-connected')).toHaveTextContent('Disconnected');
    });
  });

  describe('test_agent_context_provider', () => {
    it('should provide context to all children', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      const consumers = screen.getAllByTestId('agent-consumer');
      expect(consumers).toHaveLength(2);

      consumers.forEach((consumer) => {
        expect(consumer).toHaveTextContent('No agent');
      });
    });

    it('should share state across all consumers', () => {
      render(
        <MockAgentProvider>
          <div data-testid="consumer-1">
            <MockAgentConsumer />
          </div>
          <div data-testid="consumer-2">
            <MockAgentConsumer />
          </div>
        </MockAgentProvider>
      );

      const setButtons = screen.getAllByTestId('set-agent-btn');
      fireEvent.click(setButtons[0]);

      const agentIds = screen.getAllByTestId('agent-id');
      agentIds.forEach((idElement) => {
        expect(idElement).toHaveTextContent('agent-123');
      });
    });

    it('should handle nested providers', () => {
      render(
        <MockAgentProvider>
          <MockAgentProvider>
            <MockAgentConsumer />
          </MockAgentProvider>
        </MockAgentProvider>
      );

      const setButton = screen.getByTestId('set-agent-btn');
      fireEvent.click(setButton);

      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');
    });

    it('should update all consumers on state change', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
          <MockAgentConsumer />
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      const setButtons = screen.getAllByTestId('set-agent-btn');
      fireEvent.click(setButtons[0]);

      const agentIds = screen.getAllByTestId('agent-id');
      agentIds.forEach((idElement) => {
        expect(idElement).toHaveTextContent('agent-123');
      });
    });
  });

  describe('test_agent_context_consumption', () => {
    it('should allow components to consume context', () => {
      const TestComponent: React.FC = () => {
        const context = React.useContext(AgentContext);

        return (
          <div>
            {context ? (
              <div data-testid="has-context">Has Context</div>
            ) : (
              <div data-testid="no-context">No Context</div>
            )}
          </div>
        );
      };

      render(
        <MockAgentProvider>
          <TestComponent />
        </MockAgentProvider>
      );

      expect(screen.getByTestId('has-context')).toBeInTheDocument();
    });

    it('should return null when consuming outside provider', () => {
      const TestComponent: React.FC = () => {
        const context = React.useContext(AgentContext);

        return (
          <div>
            {context ? (
              <div data-testid="has-context">Has Context</div>
            ) : (
              <div data-testid="no-context">No Context</div>
            )}
          </div>
        );
      };

      render(<TestComponent />);

      expect(screen.getByTestId('no-context')).toBeInTheDocument();
    });

    it('should allow context mutations through setAgent', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      const setButton = screen.getByTestId('set-agent-btn');

      fireEvent.click(setButton);

      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');

      fireEvent.click(setButton);

      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');
    });

    it('should allow context mutations through clearAgent', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      const setButton = screen.getByTestId('set-agent-btn');
      fireEvent.click(setButton);

      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');

      const clearButton = screen.getByTestId('clear-agent-btn');
      fireEvent.click(clearButton);

      expect(screen.getByTestId('agent-id')).toHaveTextContent('No agent');
    });

    it('should handle multiple context consumers independently', () => {
      const CounterComponent: React.FC = () => {
        const context = React.useContext(AgentContext);
        const [clickCount, setClickCount] = React.useState(0);

        const handleClick = () => {
          setClickCount((prev) => prev + 1);
          if (context?.setAgent) {
            context.setAgent(`agent-${clickCount}`, `Agent ${clickCount}`, 'STUDENT');
          }
        };

        return (
          <div>
            <button onClick={handleClick}>Increment</button>
            <div data-testid="click-count">{clickCount}</div>
            <div data-testid="agent-id">{context?.agentId || 'No agent'}</div>
          </div>
        );
      };

      render(
        <MockAgentProvider>
          <CounterComponent />
        </MockAgentProvider>
      );

      const incrementButton = screen.getByText('Increment');
      fireEvent.click(incrementButton);

      expect(screen.getByTestId('click-count')).toHaveTextContent('1');
    });
  });

  describe('test_agent_context_edge_cases', () => {
    it('should handle context values changing rapidly', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      const setButton = screen.getByTestId('set-agent-btn');

      for (let i = 0; i < 10; i++) {
        fireEvent.click(setButton);
      }

      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');
    });

    it('should handle null agent ID gracefully', () => {
      render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      expect(screen.getByTestId('agent-id')).toHaveTextContent('No agent');
    });

    it('should handle all maturity levels', () => {
      const maturityLevels = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'] as const;

      maturityLevels.forEach((level) => {
        const { unmount } = render(
          <MockAgentProvider>
            <MockAgentConsumer />
          </MockAgentProvider>
        );

        const setButton = screen.getByTestId('set-agent-btn');
        fireEvent.click(setButton);

        expect(screen.getByTestId('agent-maturity')).toHaveTextContent('AUTONOMOUS');

        unmount();
      });
    });

    it('should maintain context integrity across re-renders', () => {
      const { rerender } = render(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      const setButton = screen.getByTestId('set-agent-btn');
      fireEvent.click(setButton);

      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');

      rerender(
        <MockAgentProvider>
          <MockAgentConsumer />
        </MockAgentProvider>
      );

      expect(screen.getByTestId('agent-id')).toHaveTextContent('agent-123');
    });
  });
});
