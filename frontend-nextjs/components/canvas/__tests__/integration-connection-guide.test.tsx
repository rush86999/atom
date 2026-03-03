/**
 * IntegrationConnectionGuide Component Tests
 *
 * Tests verify that IntegrationConnectionGuide component renders
 * OAuth flow stages, permissions, browser session preview, and
 * agent guidance correctly.
 *
 * Focus: 5-stage progress tracking, permission expansion/collapse,
 * browser session preview, completion callbacks, WebSocket updates.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import IntegrationConnectionGuide, {
  Permission,
  ConnectionStatus,
  BrowserSession,
  IntegrationGuideData
} from '../IntegrationConnectionGuide';

// Mock WebSocket hook
const mockSocket = {
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  send: jest.fn()
};

let wsMessageHandler: ((event: MessageEvent) => void) | null = null;

jest.mock('@/hooks/useWebSocket', () => ({
  __esModule: true,
  default: () => ({
    socket: mockSocket,
    connected: true,
    lastMessage: null
  })
}));

// Helper function to create mock guide data
const createMockGuideData = (overrides: Partial<IntegrationGuideData> = {}): IntegrationGuideData => ({
  integration_id: 'test-integration-123',
  integration_name: 'Slack',
  stage: 'initiating',
  agent_guidance: {
    current_step_title: 'Initializing connection',
    explanation: 'Starting the OAuth flow for Slack integration',
    why_needed: 'Slack integration requires OAuth to access your workspace',
    whats_next: 'You will be redirected to Slack authorization page'
  },
  permissions: [],
  connection_status: {
    state: 'connecting',
    retry_available: false
  },
  ...overrides
});

// Helper to simulate WebSocket message
const simulateWebSocketMessage = (data: IntegrationGuideData) => {
  if (wsMessageHandler) {
    wsMessageHandler({
      data: JSON.stringify({
        type: 'canvas:update',
        data: {
          component: 'integration_connection_guide',
          data: data
        }
      })
    } as MessageEvent);
  }
};

describe('IntegrationConnectionGuide', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    wsMessageHandler = null;

    // Capture message handler when addEventListener is called
    (mockSocket.addEventListener as jest.Mock).mockImplementation((event, handler) => {
      if (event === 'message') {
        wsMessageHandler = handler as (event: MessageEvent) => void;
      }
    });
  });

  afterEach(() => {
    wsMessageHandler = null;
  });

  // ============================================================================
  // Rendering Tests (8 tests)
  // ============================================================================

  test('should render loading state (skeleton) initially', () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    // Check for skeleton loading indicator
    const skeleton = document.querySelector('.animate-pulse');
    expect(skeleton).toBeInTheDocument();
  });

  test('should render integration name in header', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    // Simulate WebSocket message with data
    simulateWebSocketMessage(createMockGuideData({ integration_name: 'Google Workspace' }));

    await waitFor(() => {
      expect(screen.getByText(/Connect Google Workspace/i)).toBeInTheDocument();
    });
  });

  test('should render progress steps (5 stages)', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'initiating' }));

    await waitFor(() => {
      expect(screen.getByText(/Initiating/i)).toBeInTheDocument();
      expect(screen.getByText(/Authorizing/i)).toBeInTheDocument();
      expect(screen.getByText(/Callback/i)).toBeInTheDocument();
      expect(screen.getByText(/Verifying/i)).toBeInTheDocument();
      expect(screen.getByText(/Complete/i)).toBeInTheDocument();
    });
  });

  test('should render stage icons', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'initiating' }));

    await waitFor(() => {
      const icons = container.querySelectorAll('button[class*="rounded-full"], div[class*="rounded-full"]');
      expect(icons.length).toBeGreaterThanOrEqual(5);
    });
  });

  test('should render agent guidance section', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      agent_guidance: {
        current_step_title: 'Test Step',
        explanation: 'Test explanation',
        why_needed: 'Test reason',
        whats_next: 'Test next'
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/Test Step/i)).toBeInTheDocument();
      expect(screen.getByText(/Test explanation/i)).toBeInTheDocument();
    });
  });

  test('should render permissions list when provided', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'read:messages', why_needed: 'To read your messages', risk_level: 'low' },
        { scope: 'write:messages', why_needed: 'To send messages', risk_level: 'medium' }
      ]
    }));

    await waitFor(() => {
      expect(screen.getByText(/Permissions Requested/i)).toBeInTheDocument();
      expect(screen.getByText(/read:messages/i)).toBeInTheDocument();
      expect(screen.getByText(/write:messages/i)).toBeInTheDocument();
    });
  });

  test('should render browser session preview', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      stage: 'authorizing',
      browser_session: {
        session_id: 'browser-session-123',
        url: 'https://slack.com/oauth/authorize',
        user_can_see: true
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/Browser Session/i)).toBeInTheDocument();
      expect(screen.getByText(/Open Authorization Page/i)).toBeInTheDocument();
    });
  });

  test('should render connection status', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      connection_status: {
        state: 'connecting',
        retry_available: false
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/Connection Status/i)).toBeInTheDocument();
      expect(screen.getByText(/connecting/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Progress Stage Tests (10 tests)
  // ============================================================================

  test('should show initiating stage as active', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'initiating' }));

    await waitFor(() => {
      const activeSteps = container.querySelectorAll('.bg-blue-600.text-white');
      expect(activeSteps.length).toBeGreaterThan(0);
    });
  });

  test('should show authorizing stage as active', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'authorizing' }));

    await waitFor(() => {
      expect(screen.getByText(/Authorizing/i)).toBeInTheDocument();
    });
  });

  test('should show callback stage as active', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'callback' }));

    await waitFor(() => {
      expect(screen.getByText(/Callback/i)).toBeInTheDocument();
    });
  });

  test('should show verifying stage as active', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'verifying' }));

    await waitFor(() => {
      expect(screen.getByText(/Verifying/i)).toBeInTheDocument();
    });
  });

  test('should show complete stage with all steps complete', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'complete' }));

    await waitFor(() => {
      expect(screen.getByText(/Complete/i)).toBeInTheDocument();
      expect(screen.getByText(/Integration Complete/i)).toBeInTheDocument();
    });
  });

  test('should show completed steps with checkmark', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'verifying' }));

    await waitFor(() => {
      const checkmarks = container.querySelectorAll('.bg-green-500.text-white');
      expect(checkmarks.length).toBeGreaterThan(0);
    });
  });

  test('should highlight active step in blue', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'callback' }));

    await waitFor(() => {
      const activeElements = container.querySelectorAll('.bg-blue-600');
      expect(activeElements.length).toBeGreaterThan(0);
    });
  });

  test('should gray out pending steps', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'initiating' }));

    await waitFor(() => {
      const pendingSteps = container.querySelectorAll('.bg-gray-200');
      expect(pendingSteps.length).toBeGreaterThan(0);
    });
  });

  test('should fill progress line between steps', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'verifying' }));

    await waitFor(() => {
      const progressLines = container.querySelectorAll('.bg-green-500');
      expect(progressLines.length).toBeGreaterThan(0);
    });
  });

  test('should update UI on stage transition', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'initiating' }));

    await waitFor(() => {
      expect(screen.getByText(/Initiating/i)).toBeInTheDocument();
    });

    simulateWebSocketMessage(createMockGuideData({ stage: 'authorizing' }));

    await waitFor(() => {
      expect(screen.getByText(/Authorizing/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Agent Guidance Tests (5 tests)
  // ============================================================================

  test('should render current step title', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      agent_guidance: {
        current_step_title: 'Current: Authorize Slack',
        explanation: 'Test explanation',
        why_needed: 'Test reason',
        whats_next: 'Test next'
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/Current: Authorize Slack/i)).toBeInTheDocument();
    });
  });

  test('should render explanation text', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      agent_guidance: {
        current_step_title: 'Test Step',
        explanation: 'This is a detailed explanation of the current step',
        why_needed: 'Test reason',
        whats_next: 'Test next'
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/This is a detailed explanation of the current step/i)).toBeInTheDocument();
    });
  });

  test('should render Why this is needed section', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      agent_guidance: {
        current_step_title: 'Test Step',
        explanation: 'Test explanation',
        why_needed: 'OAuth is required for secure access',
        whats_next: 'Test next'
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/Why this is needed/i)).toBeInTheDocument();
      expect(screen.getByText(/OAuth is required for secure access/i)).toBeInTheDocument();
    });
  });

  test('should render What\'s next section', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      agent_guidance: {
        current_step_title: 'Test Step',
        explanation: 'Test explanation',
        why_needed: 'Test reason',
        whats_next: 'You will be redirected to authorization page'
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/What's next/i)).toBeInTheDocument();
      expect(screen.getByText(/You will be redirected to authorization page/i)).toBeInTheDocument();
    });
  });

  test('should update guidance on WebSocket message', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      agent_guidance: {
        current_step_title: 'Initial Step',
        explanation: 'Initial explanation',
        why_needed: 'Initial reason',
        whats_next: 'Initial next'
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/Initial Step/i)).toBeInTheDocument();
    });

    simulateWebSocketMessage(createMockGuideData({
      agent_guidance: {
        current_step_title: 'Updated Step',
        explanation: 'Updated explanation',
        why_needed: 'Updated reason',
        whats_next: 'Updated next'
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/Updated Step/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Permissions Tests (6 tests)
  // ============================================================================

  test('should render permission list', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'read:channels', why_needed: 'To read channels', risk_level: 'low' },
        { scope: 'write:channels', why_needed: 'To write channels', risk_level: 'medium' },
        { scope: 'admin:workspace', why_needed: 'To manage workspace', risk_level: 'high' }
      ]
    }));

    await waitFor(() => {
      expect(screen.getByText(/read:channels/i)).toBeInTheDocument();
      expect(screen.getByText(/write:channels/i)).toBeInTheDocument();
      expect(screen.getByText(/admin:workspace/i)).toBeInTheDocument();
    });
  });

  test('should show permission scope', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'custom:scope:name', why_needed: 'Test', risk_level: 'low' }
      ]
    }));

    await waitFor(() => {
      expect(screen.getByText(/custom:scope:name/i)).toBeInTheDocument();
    });
  });

  test('should show risk level badge', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'test:scope', why_needed: 'Test', risk_level: 'low' },
        { scope: 'test:scope2', why_needed: 'Test2', risk_level: 'medium' },
        { scope: 'test:scope3', why_needed: 'Test3', risk_level: 'high' }
      ]
    }));

    await waitFor(() => {
      expect(screen.getByText(/LOW/i)).toBeInTheDocument();
      expect(screen.getByText(/MEDIUM/i)).toBeInTheDocument();
      expect(screen.getByText(/HIGH/i)).toBeInTheDocument();
    });
  });

  test('should show red badge for high risk', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'admin:all', why_needed: 'Full admin access', risk_level: 'high' }
      ]
    }));

    await waitFor(() => {
      const highRiskBadge = container.querySelector('.bg-red-100');
      expect(highRiskBadge).toBeInTheDocument();
    });
  });

  test('should show yellow badge for medium risk', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'write:messages', why_needed: 'Send messages', risk_level: 'medium' }
      ]
    }));

    await waitFor(() => {
      const mediumRiskBadge = container.querySelector('.bg-yellow-100');
      expect(mediumRiskBadge).toBeInTheDocument();
    });
  });

  test('should show green badge for low risk', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'read:profile', why_needed: 'Read profile', risk_level: 'low' }
      ]
    }));

    await waitFor(() => {
      const lowRiskBadge = container.querySelector('.bg-green-100');
      expect(lowRiskBadge).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Permissions Expansion Tests (4 tests)
  // ============================================================================

  test('should expand permission when clicked', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'read:messages', why_needed: 'This permission allows reading your messages', risk_level: 'low' }
      ]
    }));

    await waitFor(() => {
      expect(screen.getByText(/read:messages/i)).toBeInTheDocument();
    });

    // Click permission button
    const permissionButton = screen.getByText(/read:messages/i).closest('button');
    if (permissionButton) {
      fireEvent.click(permissionButton);
    }

    await waitFor(() => {
      expect(screen.getByText(/This permission allows reading your messages/i)).toBeInTheDocument();
    });
  });

  test('should show why_needed text when expanded', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'write:files', why_needed: 'Required to upload files to your workspace', risk_level: 'medium' }
      ]
    }));

    await waitFor(() => {
      expect(screen.getByText(/write:files/i)).toBeInTheDocument();
    });

    const permissionButton = screen.getByText(/write:files/i).closest('button');
    if (permissionButton) {
      fireEvent.click(permissionButton);
    }

    await waitFor(() => {
      expect(screen.getByText(/Required to upload files to your workspace/i)).toBeInTheDocument();
    });
  });

  test('should collapse when clicked again', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'read:channels', why_needed: 'To read channels', risk_level: 'low' }
      ]
    }));

    await waitFor(() => {
      expect(screen.getByText(/read:channels/i)).toBeInTheDocument();
    });

    const permissionButton = screen.getByText(/read:channels/i).closest('button');
    if (permissionButton) {
      // First click - expand
      fireEvent.click(permissionButton);
    }

    await waitFor(() => {
      expect(screen.getByText(/To read channels/i)).toBeInTheDocument();
    });

    if (permissionButton) {
      // Second click - collapse
      fireEvent.click(permissionButton);
    }

    await waitFor(() => {
      expect(screen.queryByText(/To read channels/i)).not.toBeInTheDocument();
    });
  });

  test('should allow multiple permissions expanded independently', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'read:messages', why_needed: 'Read messages explanation', risk_level: 'low' },
        { scope: 'write:messages', why_needed: 'Write messages explanation', risk_level: 'medium' },
        { scope: 'admin:workspace', why_needed: 'Admin workspace explanation', risk_level: 'high' }
      ]
    }));

    await waitFor(() => {
      expect(screen.getByText(/read:messages/i)).toBeInTheDocument();
    });

    // Click first permission
    const firstPermissionButton = screen.getByText(/read:messages/i).closest('button');
    if (firstPermissionButton) {
      fireEvent.click(firstPermissionButton);
    }

    await waitFor(() => {
      expect(screen.getByText(/Read messages explanation/i)).toBeInTheDocument();
    });

    // Click second permission
    const secondPermissionButton = screen.getByText(/write:messages/i).closest('button');
    if (secondPermissionButton) {
      fireEvent.click(secondPermissionButton);
    }

    await waitFor(() => {
      expect(screen.getByText(/Write messages explanation/i)).toBeInTheDocument();
    });

    // Both should be visible
    expect(screen.getByText(/Read messages explanation/i)).toBeInTheDocument();
    expect(screen.getByText(/Write messages explanation/i)).toBeInTheDocument();
  });

  // ============================================================================
  // Browser Session Tests (4 tests)
  // ============================================================================

  test('should render browser session preview in authorizing stage', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      stage: 'authorizing',
      browser_session: {
        session_id: 'session-123',
        url: 'https://slack.com/oauth',
        user_can_see: true
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/Browser Session/i)).toBeInTheDocument();
    });
  });

  test('should show You can see badge when user_can_see true', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      stage: 'authorizing',
      browser_session: {
        session_id: 'session-123',
        url: 'https://slack.com/oauth',
        user_can_see: true
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/You can see/i)).toBeInTheDocument();
    });
  });

  test('should show Agent controlled badge when user_can_see false', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      stage: 'authorizing',
      browser_session: {
        session_id: 'session-123',
        url: 'https://slack.com/oauth',
        user_can_see: false
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/Agent controlled/i)).toBeInTheDocument();
    });
  });

  test('should render Open Authorization Page button with URL', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      stage: 'authorizing',
      browser_session: {
        session_id: 'session-123',
        url: 'https://slack.com/oauth/authorize?client_id=123',
        user_can_see: true
      }
    }));

    await waitFor(() => {
      const link = screen.getByText(/Open Authorization Page/i).closest('a');
      expect(link).toHaveAttribute('href', 'https://slack.com/oauth/authorize?client_id=123');
    });
  });

  // ============================================================================
  // Connection Status Tests (4 tests)
  // ============================================================================

  test('should show connection status text', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      connection_status: {
        state: 'connecting',
        retry_available: false
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/connecting/i)).toBeInTheDocument();
    });
  });

  test('should show error status in red', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      connection_status: {
        state: 'error',
        error: 'Connection failed: Invalid credentials',
        retry_available: true
      }
    }));

    await waitFor(() => {
      const errorText = container.querySelector('.text-red-600');
      expect(errorText).toBeInTheDocument();
      expect(errorText?.textContent).toContain('Connection failed: Invalid credentials');
    });
  });

  test('should show complete status in green', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      stage: 'complete',
      connection_status: {
        state: 'connected',
        retry_available: false
      }
    }));

    await waitFor(() => {
      const completeText = container.querySelector('.text-green-600');
      expect(completeText).toBeInTheDocument();
    });
  });

  test('should show retry button when retry_available true', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      connection_status: {
        state: 'error',
        error: 'Connection timeout',
        retry_available: true
      }
    }));

    await waitFor(() => {
      expect(screen.getByText(/Retry Connection/i)).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Completion Tests (4 tests)
  // ============================================================================

  test('should render completion message when stage complete', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      stage: 'complete',
      integration_name: 'Slack'
    }));

    await waitFor(() => {
      expect(screen.getByText(/Integration Complete/i)).toBeInTheDocument();
    });
  });

  test('should show integration name in completion message', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      stage: 'complete',
      integration_name: 'Google Workspace'
    }));

    await waitFor(() => {
      expect(screen.getByText(/Google Workspace has been successfully connected/i)).toBeInTheDocument();
    });
  });

  test('should call onComplete callback when complete', async () => {
    const onComplete = jest.fn();

    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
        onComplete={onComplete}
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      stage: 'complete',
      integration_id: 'integration-123'
    }));

    await waitFor(() => {
      expect(onComplete).toHaveBeenCalledWith('integration-123');
    });
  });

  test('should style completion message in green', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      stage: 'complete',
      integration_name: 'Slack'
    }));

    await waitFor(() => {
      const completionDiv = container.querySelector('.bg-green-50');
      expect(completionDiv).toBeInTheDocument();
    });
  });

  // ============================================================================
  // Accessibility Tests (4 tests)
  // ============================================================================

  test('should have accessibility tree in loading state', () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    const accessibilityTree = document.querySelector('[role="log"]');
    expect(accessibilityTree).toBeInTheDocument();
  });

  test('should have accessibility tree in active state', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'initiating' }));

    await waitFor(() => {
      const accessibilityTree = document.querySelector('[role="log"]');
      expect(accessibilityTree).toBeInTheDocument();
    });
  });

  test('should include stage in JSON state', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'verifying' }));

    await waitFor(() => {
      const accessibilityTree = document.querySelector('[role="log"]');
      expect(accessibilityTree).toHaveAttribute('data-stage', 'verifying');
    });
  });

  test('should include permissions_count in JSON state', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({
      permissions: [
        { scope: 'read:messages', why_needed: 'Test', risk_level: 'low' },
        { scope: 'write:messages', why_needed: 'Test', risk_level: 'medium' }
      ]
    }));

    await waitFor(() => {
      const accessibilityTree = document.querySelector('[role="log"]');
      expect(accessibilityTree).toHaveAttribute('data-permissions-count', '2');
    });
  });

  // ============================================================================
  // WebSocket Tests (4 tests)
  // ============================================================================

  test('should subscribe to canvas:update messages', () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    expect(mockSocket.addEventListener).toHaveBeenCalledWith('message', expect.any(Function));
  });

  test('should filter by integrationId if specified', async () => {
    render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="integration-abc"
      />
    );

    // Send message for different integration (should be filtered)
    simulateWebSocketMessage(createMockGuideData({ integration_id: 'integration-xyz' }));

    // Send message for matching integration
    simulateWebSocketMessage(createMockGuideData({ integration_id: 'integration-abc' }));

    await waitFor(() => {
      expect(screen.getByText(/Initiating/i)).toBeInTheDocument();
    });
  });

  test('should update stage on WebSocket message', async () => {
    const { container } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    simulateWebSocketMessage(createMockGuideData({ stage: 'initiating' }));

    await waitFor(() => {
      const accessibilityTree = container.querySelector('[role="log"]');
      expect(accessibilityTree).toHaveAttribute('data-stage', 'initiating');
    });
  });

  test('should clean up event listeners on unmount', () => {
    const { unmount } = render(
      <IntegrationConnectionGuide
        userId="test-user"
        integrationId="test-integration"
      />
    );

    unmount();

    expect(mockSocket.removeEventListener).toHaveBeenCalledWith('message', expect.any(Function));
  });
});
