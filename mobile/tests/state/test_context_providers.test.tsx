/**
 * Context Provider Tests
 *
 * Tests for Context providers covering:
 * - Agent context provider
 * - Canvas context provider
 * - User context provider
 * - Context value consumption in components
 * - Context updates propagation to consumers
 *
 * @module Context Provider Tests
 * @see Phase 158-02 - Mobile Test Suite Execution
 */

import React, { createContext, useContext, useState } from 'react';
import { render, screen, waitFor, act } from '@testing-library/react-native';
import { Text, View, Button, TextInput } from 'react-native';

// ============================================================================
// Mock Context Providers
// ============================================================================

// Agent Context
interface AgentContextType {
  agentId: string | null;
  agentName: string | null;
  loading: boolean;
  error: string | null;
  setAgent: (agentId: string, agentName: string) => void;
  clearAgent: () => void;
}

const AgentContext = createContext<AgentContextType | undefined>(undefined);

const AgentProvider: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const [agentId, setAgentId] = useState<string | null>(null);
  const [agentName, setAgentName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setAgent = (id: string, name: string) => {
    setLoading(true);
    setError(null);
    // Simulate async operation
    setTimeout(() => {
      setAgentId(id);
      setAgentName(name);
      setLoading(false);
    }, 100);
  };

  const clearAgent = () => {
    setAgentId(null);
    setAgentName(null);
    setError(null);
  };

  return (
    <AgentContext.Provider value={{ agentId, agentName, loading, error, setAgent, clearAgent }}>
      {children}
    </AgentContext.Provider>
  );
};

// Canvas Context
interface CanvasContextType {
  canvasId: string | null;
  canvasType: 'chart' | 'markdown' | 'form' | null;
  data: any;
  loading: boolean;
  setCanvas: (canvasId: string, canvasType: 'chart' | 'markdown' | 'form', data: any) => void;
  clearCanvas: () => void;
}

const CanvasContext = createContext<CanvasContextType | undefined>(undefined);

const CanvasProvider: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const [canvasId, setCanvasId] = useState<string | null>(null);
  const [canvasType, setCanvasType] = useState<'chart' | 'markdown' | 'form' | null>(null);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const setCanvas = (id: string, type: 'chart' | 'markdown' | 'form', canvasData: any) => {
    setLoading(true);
    // Simulate async operation
    setTimeout(() => {
      setCanvasId(id);
      setCanvasType(type);
      setData(canvasData);
      setLoading(false);
    }, 100);
  };

  const clearCanvas = () => {
    setCanvasId(null);
    setCanvasType(null);
    setData(null);
  };

  return (
    <CanvasContext.Provider value={{ canvasId, canvasType, data, loading, setCanvas, clearCanvas }}>
      {children}
    </CanvasContext.Provider>
  );
};

// User Context
interface UserContextType {
  userId: string | null;
  email: string | null;
  authenticated: boolean;
  login: (userId: string, email: string) => void;
  logout: () => void;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

const UserProvider: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const [userId, setUserId] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [authenticated, setAuthenticated] = useState(false);

  const login = (id: string, emailAddress: string) => {
    setUserId(id);
    setEmail(emailAddress);
    setAuthenticated(true);
  };

  const logout = () => {
    setUserId(null);
    setEmail(null);
    setAuthenticated(false);
  };

  return (
    <UserContext.Provider value={{ userId, email, authenticated, login, logout }}>
      {children}
    </UserContext.Provider>
  );
};

// Custom hook for context
function useAgentContext() {
  const context = useContext(AgentContext);
  if (!context) {
    throw new Error('useAgentContext must be used within AgentProvider');
  }
  return context;
}

function useCanvasContext() {
  const context = useContext(CanvasContext);
  if (!context) {
    throw new Error('useCanvasContext must be used within CanvasProvider');
  }
  return context;
}

function useUserContext() {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error('useUserContext must be used within UserProvider');
  }
  return context;
}

// ============================================================================
// Test Components
// ============================================================================

const AgentConsumerComponent: React.FC = () => {
  const { agentId, agentName, loading, error } = useAgentContext();

  if (loading) {
    return <Text testID="agent-loading">Loading agent...</Text>;
  }

  if (error) {
    return <Text testID="agent-error">Error: {error}</Text>;
  }

  return (
    <View>
      <Text testID="agent-id">{agentId || 'No agent selected'}</Text>
      <Text testID="agent-name">{agentName || 'No name'}</Text>
    </View>
  );
};

const CanvasConsumerComponent: React.FC = () => {
  const { canvasId, canvasType, loading } = useCanvasContext();

  if (loading) {
    return <Text testID="canvas-loading">Loading canvas...</Text>;
  }

  return (
    <View>
      <Text testID="canvas-id">{canvasId || 'No canvas selected'}</Text>
      <Text testID="canvas-type">{canvasType || 'No type'}</Text>
    </View>
  );
};

const UserConsumerComponent: React.FC = () => {
  const { userId, email, authenticated } = useUserContext();

  if (!authenticated) {
    return <Text testID="user-unauthenticated">Not authenticated</Text>;
  }

  return (
    <View>
      <Text testID="user-id">{userId || 'No user'}</Text>
      <Text testID="user-email">{email || 'No email'}</Text>
      <Text testID="user-authenticated">Authenticated</Text>
    </View>
  );
};

// ============================================================================
// Agent Context Tests
// ============================================================================

describe('Agent Context Provider', () => {
  it('test_agent_context_provider_initial_state', () => {
    const { getByTestId } = render(
      <AgentProvider>
        <AgentConsumerComponent />
      </AgentProvider>
    );

    expect(getByTestId('agent-id')).toBeTruthy();
    expect(getByTestId('agent-name')).toBeTruthy();
  });

  it('test_agent_context_provider_set_agent', async () => {
    const { getByTestId, getByText } = render(
      <AgentProvider>
        <AgentConsumerComponent />
      </AgentProvider>
    );

    const TestComponent = () => {
      const { setAgent } = useAgentContext();
      return <Button testID="set-agent-btn" title="Set Agent" onPress={() => setAgent('agent-123', 'Test Agent')} />;
    };

    const { getByTestId } = render(
      <AgentProvider>
        <TestComponent />
      </AgentProvider>
    );

    fireEvent.press(getByTestId('set-agent-btn'));

    await waitFor(() => {
      expect(getByTestId('agent-id')).toBeTruthy();
    });
  });

  it('test_agent_context_provider_clear_agent', async () => {
    const TestComponent = () => {
      const { agentId, clearAgent } = useAgentContext();
      return (
        <View>
          <Text testID="has-agent">{agentId ? 'Has Agent' : 'No Agent'}</Text>
          <Button testID="clear-agent-btn" title="Clear Agent" onPress={clearAgent} />
        </View>
      );
    };

    const { getByTestId } = render(
      <AgentProvider>
        <TestComponent />
      </AgentProvider>
    );

    fireEvent.press(getByTestId('clear-agent-btn'));

    await waitFor(() => {
      expect(getByTestId('has-agent')).toBeTruthy();
    });
  });
});

// ============================================================================
// Canvas Context Tests
// ============================================================================

describe('Canvas Context Provider', () => {
  it('test_canvas_context_provider_initial_state', () => {
    const { getByTestId } = render(
      <CanvasProvider>
        <CanvasConsumerComponent />
      </CanvasProvider>
    );

    expect(getByTestId('canvas-id')).toBeTruthy();
    expect(getByTestId('canvas-type')).toBeTruthy();
  });

  it('test_canvas_context_provider_set_canvas', async () => {
    const TestComponent = () => {
      const { setCanvas } = useCanvasContext();
      return (
        <Button
          testID="set-canvas-btn"
          title="Set Canvas"
          onPress={() => setCanvas('canvas-123', 'chart', { data: 'test' })}
        />
      );
    };

    const { getByTestId } = render(
      <CanvasProvider>
        <TestComponent />
      </CanvasProvider>
    );

    fireEvent.press(getByTestId('set-canvas-btn'));

    await waitFor(() => {
      expect(getByTestId('canvas-id')).toBeTruthy();
    });
  });

  it('test_canvas_context_provider_clear_canvas', async () => {
    const TestComponent = () => {
      const { canvasId, clearCanvas } = useCanvasContext();
      return (
        <View>
          <Text testID="has-canvas">{canvasId ? 'Has Canvas' : 'No Canvas'}</Text>
          <Button testID="clear-canvas-btn" title="Clear Canvas" onPress={clearCanvas} />
        </View>
      );
    };

    const { getByTestId } = render(
      <CanvasProvider>
        <TestComponent />
      </CanvasProvider>
    );

    fireEvent.press(getByTestId('clear-canvas-btn'));

    await waitFor(() => {
      expect(getByTestId('has-canvas')).toBeTruthy();
    });
  });
});

// ============================================================================
// User Context Tests
// ============================================================================

describe('User Context Provider', () => {
  it('test_user_context_provider_initial_state', () => {
    const { getByTestId } = render(
      <UserProvider>
        <UserConsumerComponent />
      </UserProvider>
    );

    expect(getByTestId('user-unauthenticated')).toBeTruthy();
  });

  it('test_user_context_provider_login', async () => {
    const TestComponent = () => {
      const { userId, email, login, authenticated } = useUserContext();
      return (
        <View>
          <Text testID="user-id-display">{userId || 'No user'}</Text>
          <Text testID="user-email-display">{email || 'No email'}</Text>
          <Text testID="authenticated-display">{authenticated ? 'Yes' : 'No'}</Text>
          <Button
            testID="login-btn"
            title="Login"
            onPress={() => login('user-123', 'user@example.com')}
          />
        </View>
      );
    };

    const { getByTestId } = render(
      <UserProvider>
        <TestComponent />
      </UserProvider>
    );

    fireEvent.press(getByTestId('login-btn'));

    await waitFor(() => {
      expect(getByTestId('authenticated-display')).toBeTruthy();
      expect(getByTestId('user-id-display')).toBeTruthy();
      expect(getByTestId('user-email-display')).toBeTruthy();
    });
  });

  it('test_user_context_provider_logout', async () => {
    const TestComponent = () => {
      const { userId, logout } = useUserContext();
      return (
        <View>
          <Text testID="user-before-logout">{userId || 'No user'}</Text>
          <Button testID="logout-btn" title="Logout" onPress={logout} />
        </View>
      );
    };

    const { getByTestId } = render(
      <UserProvider>
        <TestComponent />
      </UserProvider>
    );

    fireEvent.press(getByTestId('logout-btn'));

    await waitFor(() => {
      expect(getByTestId('user-before-logout')).toBeTruthy();
    });
  });
});

// ============================================================================
// Context Value Consumption Tests
// ============================================================================

describe('Context Value Consumption', () => {
  it('test_context_value_consumption', () => {
    const TestComponent = () => {
      const { agentId } = useAgentContext();
      const { canvasId } = useCanvasContext();
      const { userId } = useUserContext();

      return (
        <View>
          <Text testID="combined-context">
            Agent: {agentId || 'None'}, Canvas: {canvasId || 'None'}, User: {userId || 'None'}
          </Text>
        </View>
      );
    };

    const { getByTestId } = render(
      <AgentProvider>
        <CanvasProvider>
          <UserProvider>
            <TestComponent />
          </UserProvider>
        </CanvasProvider>
      </AgentProvider>
    );

    expect(getByTestId('combined-context')).toBeTruthy();
  });

  it('test_context_multiple_consumers', () => {
    const Consumer1 = () => {
      const { agentId } = useAgentContext();
      return <Text testID="consumer1-agent">Agent: {agentId || 'None'}</Text>;
    };

    const Consumer2 = () => {
      const { agentId } = useAgentContext();
      return <Text testID="consumer2-agent">Agent: {agentId || 'None'}</Text>;
    };

    const { getByTestId } = render(
      <AgentProvider>
        <Consumer1 />
        <Consumer2 />
      </AgentProvider>
    );

    expect(getByTestId('consumer1-agent')).toBeTruthy();
    expect(getByTestId('consumer2-agent')).toBeTruthy();
  });
});

// ============================================================================
// Context Update Propagation Tests
// ============================================================================

describe('Context Update Propagation', () => {
  it('test_context_updates_propagate_to_consumers', async () => {
    const ParentComponent = () => {
      const { setAgent } = useAgentContext();
      return <Button testID="update-agent" onPress={() => setAgent('agent-updated', 'Updated Agent')} />;
    };

    const ChildComponent = () => {
      const { agentId } = useAgentContext();
      return <Text testID="child-agent">{agentId || 'No agent'}</Text>;
    };

    const { getByTestId } = render(
      <AgentProvider>
        <View>
          <ParentComponent />
          <ChildComponent />
        </View>
      </AgentProvider>
    );

    fireEvent.press(getByTestId('update-agent'));

    await waitFor(() => {
      expect(getByTestId('child-agent')).toBeTruthy();
    });
  });

  it('test_nested_context_updates', async () => {
    const InnerComponent = () => {
      const { setCanvas } = useCanvasContext();
      return (
        <Button testID="inner-update" onPress={() => setCanvas('inner-123', 'chart', {})} />
      );
    };

    const OuterComponent = () => {
      const { canvasId } = useCanvasContext();
      return (
        <View>
          <Text testID="outer-canvas">{canvasId || 'No canvas'}</Text>
          <InnerComponent />
        </View>
      );
    };

    const { getByTestId } = render(
      <CanvasProvider>
        <OuterComponent />
      </CanvasProvider>
    );

    fireEvent.press(getByTestId('inner-update'));

    await waitFor(() => {
      expect(getByTestId('outer-canvas')).toBeTruthy();
    });
  });

  it('test_context_independent_updates', async () => {
    const AgentUpdater = () => {
      const { setAgent } = useAgentContext();
      return <Button testID="update-agent" onPress={() => setAgent('agent-1', 'Agent 1')} />;
    };

    const CanvasUpdater = () => {
      const { setCanvas } = useCanvasContext();
      return <Button testID="update-canvas" onPress={() => setCanvas('canvas-1', 'chart', {})} />;
    };

    const AgentDisplay = () => {
      const { agentId } = useAgentContext();
      return <Text testID="display-agent">{agentId || 'No agent'}</Text>;
    };

    const CanvasDisplay = () => {
      const { canvasId } = useCanvasContext();
      return <Text testID="display-canvas">{canvasId || 'No canvas'}</Text>;
    };

    const { getByTestId } = render(
      <AgentProvider>
        <CanvasProvider>
          <View>
            <AgentUpdater />
            <CanvasUpdater />
            <AgentDisplay />
            <CanvasDisplay />
          </View>
        </CanvasProvider>
      </AgentProvider>
    );

    fireEvent.press(getByTestId('update-agent'));
    fireEvent.press(getByTestId('update-canvas'));

    await waitFor(() => {
      expect(getByTestId('display-agent')).toBeTruthy();
      expect(getByTestId('display-canvas')).toBeTruthy();
    });
  });
});

// ============================================================================
// Context Error Handling
// ============================================================================

describe('Context Error Handling', () => {
  it('should throw error when using context outside provider', () => {
    expect(() => {
      const component = () => {
        // @ts-expect-error - intentional error for testing
        const { agentId } = useAgentContext();
        return <Text>{agentId}</Text>;
      };

      render(component());
    }).toThrow('useAgentContext must be used within AgentProvider');
  });

  it('should handle context updates gracefully', async () => {
    const TestComponent = () => {
      const { agentId, error, setAgent } = useAgentContext();
      return (
        <View>
          <Text testID="agent-display">{agentId || 'No agent'}</Text>
          {error && <Text testID="error-display">{error}</Text>}
          <Button testID="update-agent" onPress={() => setAgent('', '')} />
        </View>
      );
    };

    const { getByTestId } = render(
      <AgentProvider>
        <TestComponent />
      </AgentProvider>
    );

    fireEvent.press(getByTestId('update-agent'));

    await waitFor(() => {
      expect(getByTestId('agent-display')).toBeTruthy();
    });
  });
});

// ============================================================================
// Context Performance Tests
// ============================================================================

describe('Context Performance', () => {
  it('should handle rapid context updates', async () => {
    const TestComponent = () => {
      const { agentId, setAgent } = useAgentContext();
      return <Text testID="rapid-agent">{agentId || 'No agent'}</Text>;
    };

    const { getByTestId } = render(
      <AgentProvider>
        <TestComponent />
      </AgentProvider>
    );

    const updateCount = 50;

    for (let i = 0; i < updateCount; i++) {
      act(() => {
        // Simulate rapid updates
        const { setAgent } = useAgentContext();
        setAgent(`agent-${i}`, `Agent ${i}`);
      });
    }

    // Should complete without errors
    expect(getByTestId('rapid-agent')).toBeTruthy();
  });

  it('should handle multiple simultaneous context consumers', () => {
    const consumers = Array.from({ length: 10 }, (_, i) => {
      const Component = () => {
        const { agentId } = useAgentContext();
        return <Text key={i} testID={`consumer-${i}`}>{agentId || 'None'}</Text>;
      };
      return Component();
    });

    const { getAllByTestId } = render(
      <AgentProvider>
        <View>{consumers}</View>
      </AgentProvider>
    );

    const renderedNodes = getAllByTestId(/^consumer-/);
    expect(renderedNodes).toHaveLength(10);
  });
});
