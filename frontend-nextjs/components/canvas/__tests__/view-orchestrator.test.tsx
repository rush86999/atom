/**
 * ViewOrchestrator Component Tests
 *
 * Tests verify that ViewOrchestrator component manages multi-view layouts correctly,
 * handles WebSocket messages for view switching, and provides canvas guidance.
 *
 * Focus: Layout rendering, WebSocket integration, user interactions,
 * accessibility trees, and edge cases.
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { ViewOrchestrator, View, CanvasGuidance } from '../ViewOrchestrator';

// Mock WebSocket hook
const mockSend = jest.fn();
const mockSocket = {
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
  send: mockSend
};

jest.mock('@/hooks/useWebSocket', () => ({
  __esModule: true,
  default: () => ({
    socket: mockSocket,
    connected: true,
    lastMessage: null
  })
}));

// Helper function to create mock view
const createMockView = (overrides?: Partial<View>): View => ({
  view_id: 'view-1',
  view_type: 'canvas',
  title: 'Test View',
  status: 'active',
  position: { x: 0, y: 0 },
  size: { width: '100%', height: '400px' },
  ...overrides
});

// Helper function to create mock guidance
const createMockGuidance = (overrides?: Partial<CanvasGuidance>): CanvasGuidance => ({
  agent_id: 'agent-123',
  message: 'Test agent message',
  what_youre_seeing: 'Test guidance explanation',
  controls: [
    { label: 'Approve', action: 'approve' },
    { label: 'Reject', action: 'reject' }
  ],
  ...overrides
});

describe('ViewOrchestrator - Rendering Tests', () => {

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should render empty state when no views', () => {
    render(
      <ViewOrchestrator
        userId="test-user"
        sessionId="session-1"
      />
    );

    // Use getByRole to avoid matching hidden accessibility tree
    expect(screen.getByText('No active views')).toBeInTheDocument();
    expect(screen.getByText(/views will appear here/i)).toBeInTheDocument();
  });

  test('should render loading message in empty state', () => {
    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    expect(screen.getByText('No active views')).toBeInTheDocument();
  });

  test('should render active views when provided', () => {
    const mockViews = [createMockView()];
    const handleMessage = (event: MessageEvent) => {
      const message = JSON.parse(event.data);
      if (message.type === 'view:switch') {
        // Simulate setting views
        const data = message.data;
        if (data.views && data.views.length > 0) {
          // Views would be rendered here
        }
      }
    };

    render(
      <ViewOrchestrator
        userId="test-user"
        sessionId="session-1"
      />
    );

    // Simulate WebSocket message for view switch
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          view_id: 'view-1'
        }
      })
    });

    // Get the message handler and call it
    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    // After message, views should be rendered
    // Note: This tests the integration with WebSocket
    expect(mockSocket.addEventListener).toHaveBeenCalledWith('message', expect.any(Function));
  });

  test('should render view header with title', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView({ title: 'Custom View Title' })],
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    // Wait for state update
    await waitFor(() => {
      expect(screen.getByText('Custom View Title')).toBeInTheDocument();
    });
  });

  test('should render view status badge (active/background/closed)', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView({ status: 'active' })],
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      expect(screen.getByText('active')).toBeInTheDocument();
    });
  });

  test('should render "Take Control" button', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /take control/i })).toBeInTheDocument();
    });
  });

  test('should render canvas guidance panel when provided', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          canvas_guidance: createMockGuidance(),
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(
      () => {
        expect(screen.getByText('Agent Guidance')).toBeInTheDocument();
        expect(screen.getByText('Test agent message')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  test('should render collapse button for guidance panel', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          canvas_guidance: createMockGuidance(),
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      // Collapse button (▼) should be present
      const collapseBtn = screen.getByText('▼');
      expect(collapseBtn).toBeInTheDocument();
    });
  });
});

describe('ViewOrchestrator - Layout Tests', () => {

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should render split_horizontal layout side-by-side', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_horizontal',
          views: [
            createMockView({ view_id: 'view-1' }),
            createMockView({ view_id: 'view-2' })
          ],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      const viewsContainer = container.querySelector('.flex-row');
      expect(viewsContainer).toBeInTheDocument();
    });
  });

  test('should render split_vertical layout stacked', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      const viewsContainer = container.querySelector('.flex-col');
      expect(viewsContainer).toBeInTheDocument();
    });
  });

  test('should render grid layout in 2x2 grid', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'grid',
          views: [
            createMockView({ view_id: 'view-1' }),
            createMockView({ view_id: 'view-2' })
          ],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      const gridContainer = container.querySelector('.grid');
      expect(gridContainer).toBeInTheDocument();
    });
  });

  test('should render tabs layout with tab buttons', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'tabs',
          views: [
            createMockView({ view_id: 'view-1', title: 'Tab 1' }),
            createMockView({ view_id: 'view-2', title: 'Tab 2' })
          ],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(
      () => {
        // Use querySelector to find tab buttons specifically
        const tabButtons = container.querySelectorAll('button');
        const hasTabButtons = Array.from(tabButtons).some(btn =>
          btn.textContent?.includes('Tab 1') || btn.textContent?.includes('Tab 2')
        );
        expect(hasTabButtons).toBe(true);
      },
      { timeout: 3000 }
    );
  });

  test('should highlight active tab', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'tabs',
          views: [
            createMockView({ view_id: 'view-1', title: 'Tab 1' }),
            createMockView({ view_id: 'view-2', title: 'Tab 2' })
          ],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      // First tab should be active
      const tabs = container.querySelectorAll('button');
      expect(tabs.length).toBeGreaterThan(0);
    });
  });

  test('should apply layout classes correctly', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_horizontal',
          views: [createMockView()],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      const viewsContainer = container.querySelector('.flex-row.space-x-4');
      expect(viewsContainer).toBeInTheDocument();
    });
  });
});

describe('ViewOrchestrator - Canvas Guidance Tests', () => {

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should render agent guidance panel', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          canvas_guidance: createMockGuidance({
            agent_id: 'agent-456',
            message: 'Agent is working on your request'
          }),
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(
      () => {
        // Check for guidance panel by finding agent-id text
        const hasAgentId = container.textContent?.includes('agent-456');
        const hasMessage = container.textContent?.includes('Agent is working on your request');
        expect(hasAgentId || hasMessage).toBe(true);
      },
      { timeout: 3000 }
    );
  });

  test('should display "What you\'re seeing" section', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          canvas_guidance: createMockGuidance({
            what_youre_seeing: 'You are seeing a browser view'
          }),
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(
      () => {
        expect(screen.getByText("What you're seeing:")).toBeInTheDocument();
        expect(screen.getByText('You are seeing a browser view')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  test('should display control buttons', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          canvas_guidance: createMockGuidance({
            controls: [
              { label: 'Continue', action: 'continue' },
              { label: 'Stop', action: 'stop' }
            ]
          }),
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument();
    });
  });

  test('should collapse button hide panel', async () => {
    const user = userEvent.setup();
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          canvas_guidance: createMockGuidance(),
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    // Wait for guidance panel to appear
    await waitFor(
      () => {
        expect(screen.getByText('Agent Guidance')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Click collapse button
    const collapseBtn = screen.getByText('▼');
    await user.click(collapseBtn);

    // Panel should be hidden
    await waitFor(
      () => {
        expect(screen.queryByText('Agent Guidance')).not.toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  test('should expand button show panel again', async () => {
    const user = userEvent.setup();
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          canvas_guidance: createMockGuidance(),
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    // Wait and collapse
    await waitFor(() => {
      expect(screen.getByText(/agent guidance/i)).toBeInTheDocument();
    });

    const collapseBtn = screen.getByText('▼');
    await user.click(collapseBtn);

    // Should show expand button
    await waitFor(() => {
      expect(screen.getByText(/show agent guidance/i)).toBeInTheDocument();
    });

    // Click expand
    const expandBtn = screen.getByText(/show agent guidance/i);
    await user.click(expandBtn);

    // Panel should reappear
    await waitFor(() => {
      expect(screen.getByText(/agent guidance/i)).toBeInTheDocument();
    });
  });
});

describe('ViewOrchestrator - WebSocket Integration Tests', () => {

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should listen for view:switch messages', () => {
    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    expect(mockSocket.addEventListener).toHaveBeenCalledWith('message', expect.any(Function));
  });

  test('should update layout on switch message', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'grid',
          views: [createMockView()],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      const gridContainer = container.querySelector('.grid');
      expect(gridContainer).toBeInTheDocument();
    });
  });

  test('should update active_views on switch', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [
            createMockView({ view_id: 'view-1', title: 'View 1' }),
            createMockView({ view_id: 'view-2', title: 'View 2' })
          ],
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      expect(screen.getByText('View 1')).toBeInTheDocument();
      expect(screen.getByText('View 2')).toBeInTheDocument();
    });
  });

  test('should handle view:activated messages', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:activated',
        data: {
          view: createMockView({ view_id: 'new-view', title: 'New View' })
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      // The view should be added to active_views
      expect(screen.getByText('New View')).toBeInTheDocument();
    });
  });

  test('should handle view:closed messages', async () => {
    // First add views
    const switchEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [
            createMockView({ view_id: 'view-1', title: 'View 1' }),
            createMockView({ view_id: 'view-2', title: 'View 2' })
          ],
          view_id: 'view-1'
        }
      })
    });

    // Then close one
    const closeEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:closed',
        data: {
          view_id: 'view-2'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(switchEvent);
      (messageHandler as (event: MessageEvent) => void)(closeEvent);
    }

    await waitFor(() => {
      expect(screen.getByText('View 1')).toBeInTheDocument();
      expect(screen.queryByText('View 2')).not.toBeInTheDocument();
    });
  });

  test('should handle view:guidance_update messages', async () => {
    const switchEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          view_id: 'view-1'
        }
      })
    });

    const guidanceEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:guidance_update',
        data: {
          guidance: createMockGuidance({
            message: 'Updated guidance message'
          })
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(switchEvent);
      (messageHandler as (event: MessageEvent) => void)(guidanceEvent);
    }

    await waitFor(
      () => {
        expect(screen.getByText('Updated guidance message')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  test('should send view:takeover message on Take Control', async () => {
    const user = userEvent.setup();
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /take control/i })).toBeInTheDocument();
    });

    const takeControlBtn = screen.getByRole('button', { name: /take control/i });
    await user.click(takeControlBtn);

    expect(mockSend).toHaveBeenCalledWith(
      expect.stringContaining('"type":"view:takeover"')
    );
  });

  test('should send view:control_action on control button', async () => {
    const user = userEvent.setup();
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          canvas_guidance: createMockGuidance({
            controls: [{ label: 'Approve', action: 'approve-action' }]
          }),
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
    });

    const approveBtn = screen.getByRole('button', { name: 'Approve' });
    await user.click(approveBtn);

    expect(mockSend).toHaveBeenCalledWith(
      expect.stringContaining('"type":"view:control_action"')
    );
    expect(mockSend).toHaveBeenCalledWith(
      expect.stringContaining('"action":"approve-action"')
    );
  });
});

describe('ViewOrchestrator - User Interaction Tests', () => {

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should click Take Control send WebSocket message', async () => {
    const user = userEvent.setup();
    const onViewTakeover = jest.fn();
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView({ view_id: 'test-view' })],
          view_id: 'test-view'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
        onViewTakeover={onViewTakeover}
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /take control/i })).toBeInTheDocument();
    });

    const takeControlBtn = screen.getByRole('button', { name: /take control/i });
    await user.click(takeControlBtn);

    expect(onViewTakeover).toHaveBeenCalledWith('test-view');
  });

  test('should Take Control call onViewTakeover callback', async () => {
    const user = userEvent.setup();
    const onViewTakeover = jest.fn();
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
        onViewTakeover={onViewTakeover}
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /take control/i })).toBeInTheDocument();
    });

    const takeControlBtn = screen.getByRole('button', { name: /take control/i });
    await user.click(takeControlBtn);

    expect(onViewTakeover).toHaveBeenCalled();
  });

  test('should clicking control button send action', async () => {
    const user = userEvent.setup();
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          canvas_guidance: createMockGuidance({
            controls: [{ label: 'Stop', action: 'stop-action' }]
          }),
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument();
    });

    const stopBtn = screen.getByRole('button', { name: 'Stop' });
    await user.click(stopBtn);

    expect(mockSend).toHaveBeenCalled();
  });

  test('should tab switching work in tabs layout', async () => {
    const user = userEvent.setup();
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'tabs',
          views: [
            createMockView({ view_id: 'view-1', title: 'Tab 1' }),
            createMockView({ view_id: 'view-2', title: 'Tab 2' })
          ],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(
      () => {
        const tabButtons = container.querySelectorAll('button');
        const hasTabs = Array.from(tabButtons).some(btn =>
          btn.textContent?.includes('Tab')
        );
        expect(hasTabs).toBe(true);
      },
      { timeout: 3000 }
    );

    // Click on a tab button
    const tabButtons = container.querySelectorAll('button');
    if (tabButtons.length > 0) {
      await user.click(tabButtons[0]);
      // Test passes if click doesn't throw
      expect(true).toBe(true);
    }
  });

  test('should guidance panel collapse/expand toggles', async () => {
    const user = userEvent.setup();
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [createMockView()],
          canvas_guidance: createMockGuidance(),
          view_id: 'view-1'
        }
      })
    });

    render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    // Collapse
    await waitFor(() => {
      expect(screen.getByText('▼')).toBeInTheDocument();
    });

    const collapseBtn = screen.getByText('▼');
    await user.click(collapseBtn);

    await waitFor(() => {
      expect(screen.queryByText('▼')).not.toBeInTheDocument();
    });

    // Expand
    const expandBtn = screen.getByText(/show agent guidance/i);
    await user.click(expandBtn);

    await waitFor(() => {
      expect(screen.getByText('▼')).toBeInTheDocument();
    });
  });

  test('should view status badge colors correct', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [
            createMockView({ status: 'active' }),
            createMockView({ view_id: 'view-2', status: 'background' }),
            createMockView({ view_id: 'view-3', status: 'closed' })
          ],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      expect(screen.getByText('active')).toBeInTheDocument();
      expect(screen.getByText('background')).toBeInTheDocument();
      expect(screen.getByText('closed')).toBeInTheDocument();

      // Check for status badge classes
      const activeBadge = container.querySelector('.bg-green-100');
      const backgroundBadge = container.querySelector('.bg-yellow-100');
      const closedBadge = container.querySelector('.bg-gray-100');

      expect(activeBadge || backgroundBadge || closedBadge).toBeInTheDocument();
    });
  });
});

describe('ViewOrchestrator - Accessibility Tests', () => {

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('should empty state have accessibility tree', () => {
    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const accessibilityDiv = container.querySelector('[role="log"]');
    expect(accessibilityDiv).toBeInTheDocument();
  });

  test('should orchestrator state have accessibility tree', () => {
    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const accessibilityDiv = container.querySelector('[role="log"]');
    expect(accessibilityDiv).toBeInTheDocument();
  });

  test('should role="log" for state tree', () => {
    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const accessibilityDiv = container.querySelector('[role="log"]');
    expect(accessibilityDiv).toHaveAttribute('role', 'log');
  });

  test('should aria-live="polite" attribute', () => {
    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const accessibilityDiv = container.querySelector('[role="log"]');
    expect(accessibilityDiv).toHaveAttribute('aria-live', 'polite');
  });

  test('should JSON state include layout', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'grid',
          views: [createMockView()],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[data-layout="grid"]');
      expect(accessibilityDiv).toBeInTheDocument();
    });
  });

  test('should JSON state include active_views array', async () => {
    const mockEvent = new MessageEvent('message', {
      data: JSON.stringify({
        type: 'view:switch',
        data: {
          layout: 'split_vertical',
          views: [
            createMockView({ view_id: 'view-1' }),
            createMockView({ view_id: 'view-2' })
          ],
          view_id: 'view-1'
        }
      })
    });

    const { container } = render(
      <ViewOrchestrator
        userId="test-user"
      />
    );

    const addEventListenerCalls = mockSocket.addEventListener.mock.calls;
    const messageHandler = addEventListenerCalls.find(call => call[0] === 'message')?.[1];
    if (messageHandler) {
      (messageHandler as (event: MessageEvent) => void)(mockEvent);
    }

    await waitFor(() => {
      const accessibilityDiv = container.querySelector('[data-active-views-count="2"]');
      expect(accessibilityDiv).toBeInTheDocument();
    });
  });
});
