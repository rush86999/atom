/**
 * AgentRequestPrompt Component Tests
 *
 * Tests verify that AgentRequestPrompt component renders correctly
 * with user-centric queries, accessibility trees, and WebSocket integration.
 *
 * Focus: React Testing Library best practices, user behavior testing,
 * accessibility tree validation for AI agent consumption.
 */

import React from 'react';

// Note: fetch is already mocked in tests/setup.ts with proper Jest mock methods
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// Note: fetch is already mocked in tests/setup.ts with proper Jest mock methods
import '@testing-library/jest-dom';
import AgentRequestPrompt, { RequestData, RequestOption } from '../AgentRequestPrompt';

// Note: fetch is already mocked in tests/setup.ts with proper Jest mock methods

// Mock WebSocket hook - Simulates the old API used by the component
const mockSocket = {
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  send: jest.fn()
};

jest.mock('@/hooks/useWebSocket', () => ({
  __esModule: true,
  default: () => ({
    socket: mockSocket,
    connected: true,
    lastMessage: null,
    streamingContent: new Map(),
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
    sendMessage: jest.fn()
  })
}));

// Mock next-auth
jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: null, status: 'unauthenticated' })
}));

// Mock fetch for API calls

// Helper to create mock request data
const createMockRequestData = (overrides: Partial<RequestData> = {}): RequestData => ({
  request_id: 'test-request-123',
  agent_id: 'test-agent-456',
  agent_name: 'TestAgent',
  request_type: 'permission',
  urgency: 'medium',
  title: 'Test Request Title',
  explanation: 'This is a test request for permission to proceed with an operation.',
  context: {
    operation: 'Test operation',
    impact: 'Test impact',
    alternatives: ['Alternative 1', 'Alternative 2']
  },
  options: [
    {
      label: 'Approve',
      description: 'Allow the operation to proceed',
      consequences: 'The operation will execute with full permissions',
      action: 'approve'
    },
    {
      label: 'Deny',
      description: 'Block the operation',
      consequences: 'The operation will be cancelled',
      action: 'deny'
    },
    {
      label: 'Defer',
      description: 'Decide later',
      consequences: 'The request will remain pending',
      action: 'defer'
    }
  ],
  suggested_option: 0,
  expires_at: new Date(Date.now() + 300000).toISOString(), // 5 minutes from now
  governance: {
    requires_signature: true,
    audit_log_required: true,
    revocable: true
  },
  ...overrides
});

// Helper to simulate WebSocket message
const simulateWebSocketMessage = (requestData: RequestData) => {
  const messageHandler = mockSocket.addEventListener.mock.calls.find(
    call => call[0] === 'message'
  );

  if (messageHandler && messageHandler[1]) {
    const messageEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'agent:request',
        data: requestData
      })
    });
    messageHandler[1](messageEvent);
  }
};

describe('AgentRequestPrompt Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    (mockSocket.send as jest.Mock).mockClear();
    (mockSocket.addEventListener as jest.Mock).mockClear();
    (mockSocket.removeEventListener as jest.Mock).mockClear();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  // ============================================================================
  // Rendering Tests (10 tests)
  // ============================================================================

  test('should render null when no request data', () => {
    const { container } = render(
      <AgentRequestPrompt
        userId="test-user"
        className=""
      />
    );

    // Component should be null when no request data received via WebSocket
    expect(container.firstChild).toBeNull();
  });

  test('should render when WebSocket message is received', async () => {
    const mockData = createMockRequestData();

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    // Simulate WebSocket message
    simulateWebSocketMessage(mockData);

    // Wait for state update
    await waitFor(() => {
      expect(container.querySelector('.agent-request-prompt')).toBeInTheDocument();
    });
  });

  test('should render header with agent name', async () => {
    const mockData = createMockRequestData({
      agent_name: 'FinanceAgent'
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('FinanceAgent')).toBeInTheDocument();
    });
  });

  test('should render urgency badge with icon', async () => {
    const mockData = createMockRequestData({ urgency: 'high' });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/high/i)).toBeInTheDocument();
    });
  });

  test('should render expiration countdown timer', async () => {
    const mockData = createMockRequestData({
      expires_at: new Date(Date.now() + 120000).toISOString()
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      // Timer should be displayed (e.g., "2m 0s")
      const timerElement = container.querySelector('.font-mono');
      expect(timerElement).toBeInTheDocument();
    });
  });

  test('should handle expired state with disabled controls', async () => {
    const mockData = createMockRequestData({
      expires_at: new Date(Date.now() - 1000).toISOString()
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/expired/i)).toBeInTheDocument();
    });
  });

  test('should render explanation section', async () => {
    const explanation = 'This is a custom explanation for the request';
    const mockData = createMockRequestData({ explanation });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(explanation)).toBeInTheDocument();
    });
  });

  test('should render context with operation and impact', async () => {
    const mockData = createMockRequestData({
      context: {
        operation: 'Execute payment transfer',
        impact: 'Funds will be transferred from account A to account B',
        alternatives: ['Wire transfer', 'ACH transfer']
      }
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/execute payment transfer/i)).toBeInTheDocument();
      expect(screen.getByText(/funds will be transferred/i)).toBeInTheDocument();
    });
  });

  test('should render suggested option with badge', async () => {
    const mockData = createMockRequestData({
      suggested_option: 1,
      options: [
        {
          label: 'Option 1',
          description: 'First option',
          consequences: 'Consequence 1',
          action: 'action1'
        },
        {
          label: 'Suggested Option',
          description: 'This is suggested',
          consequences: 'Good outcome',
          action: 'action2'
        }
      ]
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Suggested')).toBeInTheDocument();
    });
  });

  test('should render governance footer with audit notice', async () => {
    const mockData = createMockRequestData({
      governance: {
        requires_signature: true,
        audit_log_required: true,
        revocable: true
      }
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/audit log/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // User Interaction Tests (15 tests)
  // ============================================================================

  test('should select option when clicked', async () => {
    const mockData = createMockRequestData();

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    // Click the first option
    const approveButton = screen.getByText('Approve').closest('button');
    fireEvent.click(approveButton!);

    await waitFor(() => {
      // Checkmark should appear
      const checkmarks = screen.container.querySelectorAll('text-blue-600');
      expect(checkmarks.length).toBeGreaterThan(0);
    });
  });

  test('should show checkmark on selected option', async () => {
    const mockData = createMockRequestData();

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Deny')).toBeInTheDocument();
    });

    const denyButton = screen.getByText('Deny').closest('button');
    fireEvent.click(denyButton!);

    await waitFor(() => {
      expect(screen.getByText('✓')).toBeInTheDocument();
    });
  });

  test('should call onResponse callback when submitting', async () => {
    const mockData = createMockRequestData();
    const onResponse = jest.fn();

    (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true }), { status: 200 })
    );

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
        onResponse={onResponse}
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    // Select and submit
    const approveButton = screen.getByText('Approve').closest('button');
    fireEvent.click(approveButton!);

    await waitFor(() => {
      expect(screen.getByText('Submit Response')).toBeInTheDocument();
    });

    const submitButton = screen.getByText('Submit Response');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(onResponse).toHaveBeenCalledWith('test-request-123', expect.any(Object));
    });
  });

  test('should send WebSocket message on submit', async () => {
    const mockData = createMockRequestData();

    (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true }), { status: 200 })
    );

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    const approveButton = screen.getByText('Approve').closest('button');
    fireEvent.click(approveButton!);

    await waitFor(() => {
      expect(screen.getByText('Submit Response')).toBeInTheDocument();
    });

    const submitButton = screen.getByText('Submit Response');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockSocket.send).toHaveBeenCalledWith(
        expect.stringContaining('agent:request_response')
      );
    });
  });

  test('should call REST API on submit', async () => {
    const mockData = createMockRequestData();

    (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
      new Response(JSON.stringify({ success: true }), { status: 200 })
    );

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    const approveButton = screen.getByText('Approve').closest('button');
    fireEvent.click(approveButton!);

    const submitButton = await screen.findByText('Submit Response');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent-guidance/request/'),
        expect.objectContaining({
          method: 'POST'
        })
      );
    });
  });

  test('should disable controls when expired', async () => {
    const mockData = createMockRequestData({
      expires_at: new Date(Date.now() - 1000).toISOString()
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const disabledButtons = screen.container.querySelectorAll('button:disabled');
      expect(disabledButtons.length).toBeGreaterThan(0);
    });
  });

  test('should disable controls during submission', async () => {
    const mockData = createMockRequestData();

    let resolveFetch: (value: Response) => void;
    const fetchPromise = new Promise<Response>((resolve) => {
      resolveFetch = resolve!;
    });

    (global.fetch as jest.MockedFunction<typeof fetch>).mockReturnValueOnce(fetchPromise);

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    const approveButton = screen.getByText('Approve').closest('button');
    fireEvent.click(approveButton!);

    const submitButton = await screen.findByText('Submit Response');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Responding...')).toBeInTheDocument();
    });
  });

  test('should support keyboard navigation with Tab', async () => {
    const mockData = createMockRequestData();

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    // Tab key should navigate between elements
    const firstButton = screen.getByText('Approve').closest('button');
    expect(firstButton).toBeInTheDocument();

    // Buttons should be keyboard accessible
    const allButtons = screen.container.querySelectorAll('button');
    expect(allButtons.length).toBeGreaterThan(0);
  });

  test('should allow re-selecting same option', async () => {
    const mockData = createMockRequestData();

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    const approveButton = screen.getByText('Approve').closest('button');
    fireEvent.click(approveButton!);
    fireEvent.click(approveButton!); // Click again

    // Should handle re-selection gracefully
    await waitFor(() => {
      expect(screen.getByText('✓')).toBeInTheDocument();
    });
  });

  test('should update user decision in accessibility tree', async () => {
    const mockData = createMockRequestData();

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-user-decision', 'pending');
    });

    const approveButton = screen.getByText('Approve').closest('button');
    fireEvent.click(approveButton!);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-user-decision', 'selected');
    });
  });

  test('should handle API errors gracefully', async () => {
    const mockData = createMockRequestData();

    (global.fetch as jest.MockedFunction<typeof fetch>).mockRejectedValueOnce(
      new Error('Network error')
    );

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    const approveButton = screen.getByText('Approve').closest('button');
    fireEvent.click(approveButton!);

    const submitButton = await screen.findByText('Submit Response');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });

  test('should handle WebSocket send failure gracefully', async () => {
    const mockData = createMockRequestData();
    mockSocket.send = jest.fn(() => {
      throw new Error('WebSocket send failed');
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    // Should handle error without crashing
    const approveButton = screen.getByText('Approve').closest('button');
    expect(() => fireEvent.click(approveButton!)).not.toThrow();
  });

  test('should allow multiple option selections before submit', async () => {
    const mockData = createMockRequestData();

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    // Select first option
    const approveButton = screen.getByText('Approve').closest('button');
    fireEvent.click(approveButton!);

    await waitFor(() => {
      expect(screen.getByText('✓')).toBeInTheDocument();
    });

    // Change to second option
    const denyButton = screen.getByText('Deny').closest('button');
    fireEvent.click(denyButton!);

    // Should update selection
    await waitFor(() => {
      expect(screen.queryAllByText('✓')).toHaveLength(1);
    });
  });

  test('should display correct submit button text', async () => {
    const mockData = createMockRequestData();

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    // Before selection, no submit button
    expect(screen.queryByText('Submit Response')).not.toBeInTheDocument();

    // After selection
    const approveButton = screen.getByText('Approve').closest('button');
    fireEvent.click(approveButton!);

    await waitFor(() => {
      expect(screen.getByText('Submit Response')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Accessibility Tree Tests (10 tests)
  // ============================================================================

  test('should render hidden accessibility div with role="log"', async () => {
    const mockData = createMockRequestData();

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toBeInTheDocument();
    });
  });

  test('should have aria-live="polite" attribute', async () => {
    const mockData = createMockRequestData();

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('aria-live', 'polite');
    });
  });

  test('should have aria-label="Agent request prompt"', async () => {
    const mockData = createMockRequestData();

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('aria-label', 'Agent request prompt');
    });
  });

  test('should have display:none style', async () => {
    const mockData = createMockRequestData();

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveStyle({ display: 'none' });
    });
  });

  test('should have data-canvas-state="agent_request_prompt"', async () => {
    const mockData = createMockRequestData();

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-canvas-state', 'agent_request_prompt');
    });
  });

  test('should have data-request-id attribute', async () => {
    const mockData = createMockRequestData();

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-request-id', 'test-request-123');
    });
  });

  test('should have data-request-type attribute', async () => {
    const mockData = createMockRequestData({ request_type: 'permission' });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-request-type', 'permission');
    });
  });

  test('should have data-urgency attribute', async () => {
    const mockData = createMockRequestData({ urgency: 'blocking' });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-urgency', 'blocking');
    });
  });

  test('should have data-options-count attribute', async () => {
    const mockData = createMockRequestData({
      options: [
        { label: 'A', description: 'D', consequences: 'C', action: 'a' },
        { label: 'B', description: 'D', consequences: 'C', action: 'b' },
        { label: 'C', description: 'D', consequences: 'C', action: 'c' }
      ]
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-options-count', '3');
    });
  });

  test('should serialize full request state as JSON', async () => {
    const mockData = createMockRequestData();

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      const textContent = accessibilityDiv?.textContent || '';

      // Should be valid JSON
      const parsedState = JSON.parse(textContent);
      expect(parsedState).toHaveProperty('request_id', 'test-request-123');
      expect(parsedState).toHaveProperty('agent_id', 'test-agent-456');
      expect(parsedState).toHaveProperty('request_type', 'permission');
      expect(parsedState).toHaveProperty('urgency', 'medium');
      expect(parsedState).toHaveProperty('options');
      expect(parsedState.options).toHaveLength(3);
    });
  });

  // ============================================================================
  // Edge Cases Tests (10 tests)
  // ============================================================================

  test('should handle empty options array', async () => {
    const mockData = createMockRequestData({
      options: []
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-options-count', '0');
    });
  });

  test('should handle missing suggested_option', async () => {
    const mockData = createMockRequestData({
      suggested_option: undefined as any
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.agent-request-prompt')).toBeInTheDocument();
    });
  });

  test('should handle no expiration (no timer)', async () => {
    const mockData = createMockRequestData({
      expires_at: undefined
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.agent-request-prompt')).toBeInTheDocument();
    });
  });

  test('should handle empty context object', async () => {
    const mockData = createMockRequestData({
      context: {
        operation: '',
        impact: '',
        alternatives: []
      }
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.agent-request-prompt')).toBeInTheDocument();
    });
  });

  test('should handle missing alternatives in context', async () => {
    const mockData = createMockRequestData({
      context: {
        operation: 'Test',
        impact: 'Impact'
      }
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.agent-request-prompt')).toBeInTheDocument();
    });
  });

  test('should handle very long option labels', async () => {
    const longLabel = 'A'.repeat(500);
    const mockData = createMockRequestData({
      options: [
        {
          label: longLabel,
          description: 'Test',
          consequences: 'Test',
          action: 'test'
        }
      ]
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.agent-request-prompt')).toBeInTheDocument();
    });
  });

  test('should handle very long explanation', async () => {
    const longExplanation = 'B'.repeat(1000);
    const mockData = createMockRequestData({
      explanation: longExplanation
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.agent-request-prompt')).toBeInTheDocument();
    });
  });

  test('should handle API 404 error', async () => {
    const mockData = createMockRequestData();

    (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
      new Response('Not found', { status: 404 })
    );

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    const submitButton = await screen.findByText('Submit Response');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });

  test('should handle API 500 error', async () => {
    const mockData = createMockRequestData();

    (global.fetch as jest.MockedFunction<typeof fetch>).mockResolvedValueOnce(
      new Response('Internal server error', { status: 500 })
    );

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument();
    });

    const submitButton = await screen.findByText('Submit Response');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });

  test('should filter by requestId if specified', async () => {
    const mockData1 = createMockRequestData({ request_id: 'request-1' });
    const mockData2 = createMockRequestData({ request_id: 'request-2' });

    const { container } = render(
      <AgentRequestPrompt
        requestId="request-1"
        userId="test-user"
      />
    );

    // Send first message (should be received)
    simulateWebSocketMessage(mockData1);

    await waitFor(() => {
      expect(container.querySelector('.agent-request-prompt')).toBeInTheDocument();
    });

    // Send second message (should be ignored due to requestId filter)
    simulateWebSocketMessage(mockData2);

    // Should still have request-1 data
    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-request-id', 'request-1');
    });
  });

  // ============================================================================
  // WebSocket Integration Tests (5 tests)
  // ============================================================================

  test('should subscribe to agent:request messages', () => {
    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    expect(mockSocket.addEventListener).toHaveBeenCalledWith(
      'message',
      expect.any(Function)
    );
  });

  test('should pre-select suggested option', async () => {
    const mockData = createMockRequestData({
      suggested_option: 2
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-suggested-option', '2');
    });
  });

  test('should set up expiration timer', async () => {
    const mockData = createMockRequestData({
      expires_at: new Date(Date.now() + 60000).toISOString()
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.agent-request-prompt')).toBeInTheDocument();
    });

    // Timer should be visible
    expect(screen.getByText(/1m 0s/i)).toBeInTheDocument();
  });

  test('should countdown timer every second', async () => {
    const mockData = createMockRequestData({
      expires_at: new Date(Date.now() + 10000).toISOString() // 10 seconds
    });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/10s/i)).toBeInTheDocument();
    });

    // Advance timer by 1 second
    jest.advanceTimersByTime(1000);

    await waitFor(() => {
      expect(screen.getByText(/9s/i)).toBeInTheDocument();
    });
  });

  test('should clean up event listeners on unmount', () => {
    const { unmount } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    expect(mockSocket.addEventListener).toHaveBeenCalled();

    unmount();

    expect(mockSocket.removeEventListener).toHaveBeenCalledWith(
      'message',
      expect.any(Function)
    );
  });

  // ============================================================================
  // Urgency Tests (4 tests)
  // ============================================================================

  test('should display low urgency styling', async () => {
    const mockData = createMockRequestData({ urgency: 'low' });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/low/i)).toBeInTheDocument();
    });
  });

  test('should display medium urgency styling', async () => {
    const mockData = createMockRequestData({ urgency: 'medium' });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/medium/i)).toBeInTheDocument();
    });
  });

  test('should display high urgency styling', async () => {
    const mockData = createMockRequestData({ urgency: 'high' });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/high/i)).toBeInTheDocument();
    });
  });

  test('should display blocking urgency styling', async () => {
    const mockData = createMockRequestData({ urgency: 'blocking' });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/blocking/i)).toBeInTheDocument();
      expect(container.querySelector('.border-red-500')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Request Type Tests (4 tests)
  // ============================================================================

  test('should handle permission request type', async () => {
    const mockData = createMockRequestData({ request_type: 'permission' });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-request-type', 'permission');
    });
  });

  test('should handle input request type', async () => {
    const mockData = createMockRequestData({ request_type: 'input' });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-request-type', 'input');
    });
  });

  test('should handle decision request type', async () => {
    const mockData = createMockRequestData({ request_type: 'decision' });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-request-type', 'decision');
    });
  });

  test('should handle confirmation request type', async () => {
    const mockData = createMockRequestData({ request_type: 'confirmation' });

    const { container } = render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="log"]');
      expect(accessibilityDiv).toHaveAttribute('data-request-type', 'confirmation');
    });
  });

  // ============================================================================
  // Governance Tests (3 tests)
  // ============================================================================

  test('should display revocation notice when revocable', async () => {
    const mockData = createMockRequestData({
      governance: {
        requires_signature: false,
        audit_log_required: false,
        revocable: true
      }
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/revoke/i)).toBeInTheDocument();
    });
  });

  test('should display signature notice', async () => {
    const mockData = createMockRequestData({
      governance: {
        requires_signature: true,
        audit_log_required: false,
        revocable: false
      }
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/signature/i)).toBeInTheDocument();
    });
  });

  test('should display audit log notice', async () => {
    const mockData = createMockRequestData({
      governance: {
        requires_signature: false,
        audit_log_required: true,
        revocable: false
      }
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/audit log/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Timer Format Tests (3 tests)
  // ============================================================================

  test('should format seconds as "Xs"', async () => {
    const mockData = createMockRequestData({
      expires_at: new Date(Date.now() + 30000).toISOString()
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/30s/i)).toBeInTheDocument();
    });
  });

  test('should format minutes as "Xm Ys"', async () => {
    const mockData = createMockRequestData({
      expires_at: new Date(Date.now() + 90000).toISOString()
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/1m 30s/i)).toBeInTheDocument();
    });
  });

  test('should format hours as "Xh Ym"', async () => {
    const mockData = createMockRequestData({
      expires_at: new Date(Date.now() + 3660000).toISOString()
    });

    render(
      <AgentRequestPrompt
        requestId="test-request-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/1h 1m/i)).toBeInTheDocument();
    });
  });
});
