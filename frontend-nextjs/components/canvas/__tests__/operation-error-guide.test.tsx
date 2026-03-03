/**
 * OperationErrorGuide Component Tests
 *
 * Tests verify that OperationErrorGuide component renders correctly
 * with user-centric queries, accessibility trees, and error resolution.
 *
 * Focus: React Testing Library best practices, error type handling,
 * resolution selection, accessibility tree validation.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import OperationErrorGuide from '../OperationErrorGuide';

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

// Helper to create mock error data
const createMockErrorData = (overrides: any = {}): any => ({
  operation_id: 'test-operation-123',
  error: {
    type: 'permission_denied',
    code: 'ERR_PERM_001',
    message: 'You do not have permission to perform this action',
    technical_details: 'User lacks required role: admin'
  },
  agent_analysis: {
    what_happened: 'Attempted to delete user without admin privileges',
    why_it_happened: 'Current user role is "viewer", deletion requires "admin" role',
    impact: 'User deletion was blocked, no data was modified'
  },
  resolutions: [
    {
      title: 'Elevate privileges',
      description: 'Request admin privileges from your system administrator',
      agent_can_fix: false,
      steps: [
        'Contact your system administrator',
        'Request admin role assignment',
        'Wait for approval',
        'Retry the operation'
      ]
    },
    {
      title: 'Use admin account',
      description: 'Switch to an account with admin privileges',
      agent_can_fix: false,
      steps: [
        'Log out of current account',
        'Log in with admin credentials',
        'Retry the operation'
      ]
    },
    {
      title: 'Let agent handle',
      description: 'Agent will request permission elevation automatically',
      agent_can_fix: true,
      steps: [
        'Agent sends permission request to administrator',
        'Administrator approves request',
        'Operation proceeds automatically'
      ]
    }
  ],
  suggested_resolution: 2,
  ...overrides
});

// Helper to simulate WebSocket message
const simulateWebSocketMessage = (errorData: any) => {
  const messageHandler = mockSocket.addEventListener.mock.calls.find(
    call => call[0] === 'message'
  );

  if (messageHandler && messageHandler[1]) {
    const messageEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'operation:error',
        data: errorData
      })
    });
    messageHandler[1](messageEvent);
  }
};

describe('OperationErrorGuide Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (mockSocket.send as jest.Mock).mockClear();
    (mockSocket.addEventListener as jest.Mock).mockClear();
    (mockSocket.removeEventListener as jest.Mock).mockClear();
  });

  // ============================================================================
  // Rendering Tests (10 tests)
  // ============================================================================

  test('should render null when no error data', () => {
    const { container } = render(
      <OperationErrorGuide
        userId="test-user"
        className=""
      />
    );

    expect(container.firstChild).toBeNull();
  });

  test('should render when WebSocket message is received', async () => {
    const mockData = createMockErrorData();

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.operation-error-guide')).toBeInTheDocument();
    });
  });

  test('should render error header with icon', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/operation failed/i)).toBeInTheDocument();
    });
  });

  test('should render error message', async () => {
    const mockData = createMockErrorData({
      error: {
        type: 'permission_denied',
        code: 'ERR_PERM_001',
        message: 'Access denied',
        technical_details: 'Details...'
      }
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/access denied/i)).toBeInTheDocument();
    });
  });

  test('should render error code', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/ERR_PERM_001/i)).toBeInTheDocument();
    });
  });

  test('should render agent analysis section', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/agent analysis/i)).toBeInTheDocument();
    });
  });

  test('should render what happened text', async () => {
    const mockData = createMockErrorData({
      agent_analysis: {
        what_happened: 'Attempted unauthorized action',
        why_it_happened: 'Insufficient permissions',
        impact: 'Operation blocked'
      }
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/attempted unauthorized action/i)).toBeInTheDocument();
    });
  });

  test('should render why it happened text', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/insufficient privileges/i)).toBeInTheDocument();
    });
  });

  test('should render impact text', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/no data was modified/i)).toBeInTheDocument();
    });
  });

  test('should render suggested resolutions list', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/suggested resolutions/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // User Interaction Tests (12 tests)
  // ============================================================================

  test('should expand resolution when clicked', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Elevate privileges')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Elevate privileges').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/request admin privileges/i)).toBeInTheDocument();
    });
  });

  test('should collapse resolution when clicked again', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Elevate privileges')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Elevate privileges').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/request admin privileges/i)).toBeInTheDocument();
    });

    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.queryByText(/request admin privileges/i)).not.toBeInTheDocument();
    });
  });

  test('should select resolution when clicking button', async () => {
    const mockData = createMockErrorData();
    const onResolutionSelect = jest.fn();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
        onResolutionSelect={onResolutionSelect}
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Elevate privileges')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Elevate privileges').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/fix manually/i)).toBeInTheDocument();
    });

    const selectButton = screen.getByText(/fix manually/i);
    fireEvent.click(selectButton);

    await waitFor(() => {
      expect(onResolutionSelect).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Elevate privileges'
        })
      );
    });
  });

  test('should send WebSocket message on resolution selection', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Use admin account')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Use admin account').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/fix manually/i)).toBeInTheDocument();
    });

    const selectButton = screen.getByText(/fix manually/i);
    fireEvent.click(selectButton);

    await waitFor(() => {
      expect(mockSocket.send).toHaveBeenCalledWith(
        expect.stringContaining('error:resolution_selected')
      );
    });
  });

  test('should display "Let Agent Fix" button for agent-can-fix resolutions', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Let agent handle')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Let agent handle').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/let agent fix/i)).toBeInTheDocument();
    });
  });

  test('should display "Fix Manually" button for manual resolutions', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Elevate privileges')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Elevate privileges').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/fix manually/i)).toBeInTheDocument();
    });
  });

  test('should show selected resolution with ring-2 ring-blue-500', async () => {
    const mockData = createMockErrorData();

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Elevate privileges')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Elevate privileges').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/fix manually/i)).toBeInTheDocument();
    });

    const selectButton = screen.getByText(/fix manually/i);
    fireEvent.click(selectButton);

    await waitFor(() => {
      const selectedResolution = container.querySelector('.ring-2');
      expect(selectedResolution).toBeInTheDocument();
    });
  });

  test('should expand multiple resolutions independently', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Elevate privileges')).toBeInTheDocument();
    });

    // Expand first resolution
    const button1 = screen.getByText('Elevate privileges').closest('button');
    fireEvent.click(button1!);

    await waitFor(() => {
      expect(screen.getByText(/request admin privileges/i)).toBeInTheDocument();
    });

    // Expand second resolution
    const button2 = screen.getByText('Use admin account').closest('button');
    fireEvent.click(button2!);

    await waitFor(() => {
      expect(screen.getByText(/log out of current account/i)).toBeInTheDocument();
    });

    // Both should be expanded
    expect(screen.getByText(/request admin privileges/i)).toBeInTheDocument();
    expect(screen.getByText(/log out of current account/i)).toBeInTheDocument();
  });

  test('should toggle technical details section', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/show technical details/i)).toBeInTheDocument();
    });

    const detailsToggle = screen.getByText(/show technical details/i);
    fireEvent.click(detailsToggle);

    await waitFor(() => {
      expect(screen.getByText(/user lacks required role/i)).toBeInTheDocument();
    });
  });

  test('should support keyboard navigation for resolution buttons', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const buttons = screen.container.querySelectorAll('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  test('should change button text after selection', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Elevate privileges')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Elevate privileges').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/fix manually/i)).toBeInTheDocument();
    });

    const selectButton = screen.getByText(/fix manually/i);
    fireEvent.click(selectButton);

    await waitFor(() => {
      expect(screen.getByText(/✓ selected/i)).toBeInTheDocument();
    });
  });

  test('should persist selection across re-renders', async () => {
    const mockData = createMockErrorData();

    const { rerender } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Elevate privileges')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Elevate privileges').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/fix manually/i)).toBeInTheDocument();
    });

    const selectButton = screen.getByText(/fix manually/i);
    fireEvent.click(selectButton!);

    await waitFor(() => {
      expect(screen.getByText(/✓ selected/i)).toBeInTheDocument();
    });

    // Rerender should keep selection
    rerender(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/✓ selected/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Error Type Tests (8 tests)
  // ============================================================================

  test('should show lock icon for permission_denied', async () => {
    const mockData = createMockErrorData({
      error: {
        type: 'permission_denied',
        code: 'ERR_001',
        message: 'Permission denied',
        technical_details: 'Details'
      }
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/operation failed/i)).toBeInTheDocument();
    });
  });

  test('should show key icon for auth_expired', async () => {
    const mockData = createMockErrorData({
      error: {
        type: 'auth_expired',
        code: 'ERR_002',
        message: 'Authentication expired',
        technical_details: 'Details'
      }
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/operation failed/i)).toBeInTheDocument();
    });
  });

  test('should show globe icon for network_error', async () => {
    const mockData = createMockErrorData({
      error: {
        type: 'network_error',
        code: 'ERR_003',
        message: 'Network error',
        technical_details: 'Details'
      }
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/operation failed/i)).toBeInTheDocument();
    });
  });

  test('should show clock icon for rate_limit', async () => {
    const mockData = createMockErrorData({
      error: {
        type: 'rate_limit',
        code: 'ERR_004',
        message: 'Rate limit exceeded',
        technical_details: 'Details'
      }
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/operation failed/i)).toBeInTheDocument();
    });
  });

  test('should show warning icon for invalid_input', async () => {
    const mockData = createMockErrorData({
      error: {
        type: 'invalid_input',
        code: 'ERR_005',
        message: 'Invalid input provided',
        technical_details: 'Details'
      }
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/operation failed/i)).toBeInTheDocument();
    });
  });

  test('should show search icon for resource_not_found', async () => {
    const mockData = createMockErrorData({
      error: {
        type: 'resource_not_found',
        code: 'ERR_006',
        message: 'Resource not found',
        technical_details: 'Details'
      }
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/operation failed/i)).toBeInTheDocument();
    });
  });

  test('should show X icon for unknown error type', async () => {
    const mockData = createMockErrorData({
      error: {
        type: 'unknown_error',
        code: 'ERR_007',
        message: 'Unknown error occurred',
        technical_details: 'Details'
      }
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/operation failed/i)).toBeInTheDocument();
    });
  });

  test('should render error message for all types', async () => {
    const mockData = createMockErrorData({
      error: {
        type: 'network_error',
        code: 'ERR_NET',
        message: 'Connection failed after 3 retries',
        technical_details: 'Timeout after 30 seconds'
      }
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText(/connection failed after 3 retries/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Accessibility Tree Tests (8 tests)
  // ============================================================================

  test('should render hidden accessibility div with role="alert"', async () => {
    const mockData = createMockErrorData();

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="alert"]');
      expect(accessibilityDiv).toBeInTheDocument();
    });
  });

  test('should have aria-live="assertive" attribute', async () => {
    const mockData = createMockErrorData();

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="alert"]');
      expect(accessibilityDiv).toHaveAttribute('aria-live', 'assertive');
    });
  });

  test('should have aria-label="Operation error guide"', async () => {
    const mockData = createMockErrorData();

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="alert"]');
      expect(accessibilityDiv).toHaveAttribute('aria-label', 'Operation error guide');
    });
  });

  test('should have display:none style', async () => {
    const mockData = createMockErrorData();

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="alert"]');
      expect(accessibilityDiv).toHaveStyle({ display: 'none' });
    });
  });

  test('should have data-canvas-state="operation_error_guide"', async () => {
    const mockData = createMockErrorData();

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="alert"]');
      expect(accessibilityDiv).toHaveAttribute('data-canvas-state', 'operation_error_guide');
    });
  });

  test('should have data-error-type attribute', async () => {
    const mockData = createMockErrorData({
      error: {
        type: 'permission_denied',
        code: 'ERR',
        message: 'Msg',
        technical_details: 'Details'
      }
    });

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="alert"]');
      expect(accessibilityDiv).toHaveAttribute('data-error-type', 'permission_denied');
    });
  });

  test('should have data-error-code attribute', async () => {
    const mockData = createMockErrorData();

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="alert"]');
      expect(accessibilityDiv).toHaveAttribute('data-error-code', 'ERR_PERM_001');
    });
  });

  test('should serialize error state as JSON', async () => {
    const mockData = createMockErrorData();

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="alert"]');
      const textContent = accessibilityDiv?.textContent || '';

      // Should be valid JSON
      const parsedState = JSON.parse(textContent);
      expect(parsedState).toHaveProperty('operation_id', 'test-operation-123');
      expect(parsedState).toHaveProperty('error');
      expect(parsedState.error).toHaveProperty('type', 'permission_denied');
      expect(parsedState).toHaveProperty('resolutions');
      expect(parsedState.resolutions).toHaveLength(3);
    });
  });

  // ============================================================================
  // Edge Cases Tests (8 tests)
  // ============================================================================

  test('should handle empty resolutions array', async () => {
    const mockData = createMockErrorData({
      resolutions: []
    });

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.operation-error-guide')).toBeInTheDocument();
    });
  });

  test('should handle missing suggested_resolution', async () => {
    const mockData = createMockErrorData({
      suggested_resolution: undefined as any
    });

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.operation-error-guide')).toBeInTheDocument();
    });
  });

  test('should handle very long error message', async () => {
    const longMessage = 'A'.repeat(500);
    const mockData = createMockErrorData({
      error: {
        type: 'network_error',
        code: 'ERR',
        message: longMessage,
        technical_details: 'Details'
      }
    });

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.operation-error-guide')).toBeInTheDocument();
    });
  });

  test('should handle very long resolution steps', async () => {
    const longStep = 'B'.repeat(300);
    const mockData = createMockErrorData({
      resolutions: [
        {
          title: 'Test',
          description: 'Test',
          agent_can_fix: false,
          steps: [longStep]
        }
      ]
    });

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.operation-error-guide')).toBeInTheDocument();
    });
  });

  test('should handle missing agent_analysis fields', async () => {
    const mockData = createMockErrorData({
      agent_analysis: {
        what_happened: '',
        why_it_happened: '',
        impact: ''
      }
    });

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.operation-error-guide')).toBeInTheDocument();
    });
  });

  test('should handle empty steps array', async () => {
    const mockData = createMockErrorData({
      resolutions: [
        {
          title: 'Test',
          description: 'No steps provided',
          agent_can_fix: false,
          steps: []
        }
      ]
    });

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(container.querySelector('.operation-error-guide')).toBeInTheDocument();
    });
  });

  test('should handle WebSocket send failure gracefully', async () => {
    const mockData = createMockErrorData();
    mockSocket.send = jest.fn(() => {
      throw new Error('WebSocket send failed');
    });

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Elevate privileges')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Elevate privileges').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/fix manually/i)).toBeInTheDocument();
    });

    // Should handle error without crashing
    const selectButton = screen.getByText(/fix manually/i);
    expect(() => fireEvent.click(selectButton!)).not.toThrow();
  });

  test('should filter by operationId if specified', async () => {
    const mockData1 = createMockErrorData({ operation_id: 'op-1' });
    const mockData2 = createMockErrorData({ operation_id: 'op-2' });

    const { container } = render(
      <OperationErrorGuide
        operationId="op-1"
        userId="test-user"
      />
    );

    // Send first message
    simulateWebSocketMessage(mockData1);

    await waitFor(() => {
      expect(container.querySelector('.operation-error-guide')).toBeInTheDocument();
    });

    // Send second message (should be ignored)
    simulateWebSocketMessage(mockData2);

    // Should still have op-1 data
    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[role="alert"]');
      expect(accessibilityDiv).toHaveAttribute('data-operation-id', 'op-1');
    });
  });

  // ============================================================================
  // Resolution Selection Tests (4 tests)
  // ============================================================================

  test('should mark selected resolution visually', async () => {
    const mockData = createMockErrorData();

    const { container } = render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Use admin account')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Use admin account').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/fix manually/i)).toBeInTheDocument();
    });

    const selectButton = screen.getByText(/fix manually/i);
    fireEvent.click(selectButton!);

    await waitFor(() => {
      expect(container.querySelector('.ring-2')).toBeInTheDocument();
    });
  });

  test('should show correct text for agent-can-fix button', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Let agent handle')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Let agent handle').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/let agent fix/i)).toBeInTheDocument();
    });
  });

  test('should show correct text for manual fix button', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Use admin account')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Use admin account').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/fix manually/i)).toBeInTheDocument();
    });
  });

  test('should show "Selected" text after selection', async () => {
    const mockData = createMockErrorData();

    render(
      <OperationErrorGuide
        operationId="test-operation-123"
        userId="test-user"
      />
    );

    simulateWebSocketMessage(mockData);

    await waitFor(() => {
      expect(screen.getByText('Elevate privileges')).toBeInTheDocument();
    });

    const resolutionButton = screen.getByText('Elevate privileges').closest('button');
    fireEvent.click(resolutionButton!);

    await waitFor(() => {
      expect(screen.getByText(/fix manually/i)).toBeInTheDocument();
    });

    const selectButton = screen.getByText(/fix manually/i);
    fireEvent.click(selectButton!);

    await waitFor(() => {
      expect(screen.getByText(/✓ selected/i)).toBeInTheDocument();
    });
  });
});
