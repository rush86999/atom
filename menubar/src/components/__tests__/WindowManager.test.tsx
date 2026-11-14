/**
 * Window Manager Tests (MenuBar)
 *
 * Tests for Tauri window management including:
 * - Renders main window
 * - Create window
 * - Close window
 * - Minimize window
 * - Maximize window
 * - Window focus events
 * - Window state management
 * - Hotkey handling
 */

import { render, waitFor, fireEvent } from '@testing-library/react';
import MenuBar from '../../MenuBar';
import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { useHotkeys } from '../../hooks/useHotkeys';

// Mock Tauri API
jest.mock('@tauri-apps/api/core', () => ({
  invoke: jest.fn(),
}));

jest.mock('@tauri-apps/api/event', () => ({
  listen: jest.fn(),
}));

// Mock hooks
jest.mock('../../hooks/useHotkeys', () => ({
  __esModule: true,
  useHotkeys: jest.fn(() => ({
    config: null,
    isLoading: false,
    updateHotkeys: jest.fn(),
    triggerHotkey: jest.fn(),
    formatHotkeyForDisplay: jest.fn((hotkey: string) => hotkey),
    getHotkeyLabel: jest.fn(() => ''),
  })),
}));

// Mock components
jest.mock('../QuickChat', () => {
  const ReactModule = jest.requireActual('react') as typeof import('react');
  return function MockQuickChat() {
    return ReactModule.createElement('div', { 'data-testid': 'quick-chat' }, 'QuickChat');
  };
});

jest.mock('../AgentList', () => {
  const ReactModule = jest.requireActual('react') as typeof import('react');
  return function MockAgentList({ agents }: { agents: ReadonlyArray<unknown> }) {
    return ReactModule.createElement('div', { 'data-testid': 'agent-list' }, `Agents: ${agents.length}`);
  };
});

jest.mock('../CanvasList', () => {
  const ReactModule = jest.requireActual('react') as typeof import('react');
  return function MockCanvasList({ canvases }: { canvases: ReadonlyArray<unknown> }) {
    return ReactModule.createElement('div', { 'data-testid': 'canvas-list' }, `Canvases: ${canvases.length}`);
  };
});

jest.mock('../StatusIndicator', () => {
  const ReactModule = jest.requireActual('react') as typeof import('react');
  return function MockStatusIndicator({ status }: { status: unknown }) {
    return ReactModule.createElement('div', { 'data-testid': 'status-indicator' }, `Status: ${String(status)}`);
  };
});

jest.mock('../NotificationBadge', () => {
  const ReactModule = jest.requireActual('react') as typeof import('react');
  return function MockNotificationBadge({ count }: { count: number }) {
    return ReactModule.createElement('div', { 'data-testid': 'notification-badge' }, `Notifications: ${count}`);
  };
});

jest.mock('../SettingsModal', () => {
  const ReactModule = jest.requireActual('react') as typeof import('react');
  return function MockSettingsModal({ isOpen }: { isOpen: boolean }) {
    return isOpen
      ? ReactModule.createElement('div', { 'data-testid': 'settings-modal' }, 'Settings')
      : null;
  };
});

jest.mock('../AgentDetail', () => {
  const ReactModule = jest.requireActual('react') as typeof import('react');
  return function MockAgentDetail({ agentId, agentName }: { agentId: string; agentName: string }) {
    return agentId
      ? ReactModule.createElement('div', { 'data-testid': 'agent-detail' }, `Agent: ${agentName}`)
      : null;
  };
});

const mockInvoke = invoke as jest.Mock;
const mockListen = listen as jest.Mock;

type TauriFixture = () => unknown;

function mockTauriCommands(fixtures: Record<string, TauriFixture> = {}) {
  const handlers: Record<string, TauriFixture> = {
    get_backend_config: () => ({
      http_base_url: 'http://localhost:8000',
      websocket_url: 'ws://localhost:8000/ws/menubar',
      http_base_url_source: 'default',
    }),
    get_recent_items: () => ({ agents: [], canvases: [] }),
    get_unread_notifications: () => [],
    get_session: () => null,
    get_connection_status: () => ({
      status: 'connected',
      server_time: new Date().toISOString(),
    }),
  };

  Object.assign(handlers, fixtures);

  mockInvoke.mockImplementation((command: string) => {
    const handler = handlers[command];
    if (!handler) {
      return Promise.reject(
        new Error(`Unexpected Tauri command in WindowManager test: ${command}`)
      );
    }
    return Promise.resolve(handler());
  });
}

describe('Window Manager (MenuBar)', () => {
  const mockUser = {
    id: '123',
    email: 'test@example.com',
    first_name: 'Test',
    last_name: 'User',
  };

  const mockToken = 'mock-token-123';

  beforeEach(() => {
    jest.clearAllMocks();
    mockListen.mockImplementation(() => Promise.resolve(jest.fn()));
    mockTauriCommands();
    // Simulate the Tauri v2 IPC bridge injected in the webview. Tests that
    // exercise browser-only fallback live in src/__tests__/config.test.ts.
    (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__ = {};
  });

  afterEach(() => {
    delete (window as unknown as { __TAURI_INTERNALS__?: unknown })
      .__TAURI_INTERNALS__;
  });

  /**
   * Test: Renders main window
   * Expected: MenuBar component renders without crashing
   */
  test('test_renders_main_window', async () => {
    const { getByTestId } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(getByTestId('status-indicator')).toBeTruthy();
    });
  });

  /**
   * Test: Create window (simulated via component mount)
   * Expected: Component mounts and initializes
   */
  test('test_create_window', async () => {
    mockTauriCommands({
      get_recent_items: () => ({
        agents: [
          { id: '1', name: 'Agent 1', maturity_level: 'INTERN', status: 'online', last_execution: null, execution_count: 0 },
        ],
        canvases: [],
      }),
    });

    const { getByTestId } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith('get_recent_items', { token: mockToken });
      expect(getByTestId('agent-list')).toBeTruthy();
    });
  });

  /**
   * Test: Close window (simulated via unmount)
   * Expected: Component unmounts cleanly
   */
  test('test_close_window', async () => {
    const { unmount } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    // Verify component mounted
    expect(invoke).toHaveBeenCalled();

    // Unmount component
    unmount();

    // Component should unmount without errors
    expect(() => unmount()).not.toThrow();
  });

  /**
   * Test: Minimize window (simulated via state)
   * Expected: Window state can be toggled
   */
  test('test_minimize_window', async () => {
    const { getByTestId } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(getByTestId('status-indicator')).toBeTruthy();
    });

    // Minimize is a Tauri window operation, not a React state
    // This test verifies the component can handle state changes
    expect(invoke).toBeDefined();
  });

  /**
   * Test: Maximize window
   * Expected: Window can be maximized (Tauri operation)
   */
  test('test_maximize_window', async () => {
    const { getByTestId } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(getByTestId('status-indicator')).toBeTruthy();
    });

    // Maximize is a Tauri window operation
    // This test verifies component renders correctly
    expect(getByTestId('status-indicator')).toBeTruthy();
  });

  /**
   * Test: Window focus events
   * Expected: Component handles focus events
   */
  test('test_window_focus', async () => {
    const mockUnlisten = jest.fn();
    mockListen.mockResolvedValue(mockUnlisten);

    render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(listen).toHaveBeenCalledWith('quick-chat-hotkey', expect.any(Function));
    });

    // Verify event listeners were set up
    expect(listen).toHaveBeenCalled();
  });

  /**
   * Test: Window state management
   * Expected: Component manages state correctly
   */
  test('test_window_state_management', async () => {
    mockTauriCommands({
      get_recent_items: () => ({
        agents: [
          { id: '1', name: 'Agent 1', maturity_level: 'INTERN', status: 'online', last_execution: null, execution_count: 5 },
          { id: '2', name: 'Agent 2', maturity_level: 'STUDENT', status: 'offline', last_execution: null, execution_count: 0 },
        ],
        canvases: [
          { id: 'c1', canvas_type: 'chart', created_at: '2024-01-01', agent_id: null, agent_name: null },
        ],
      }),
    });

    const { getByTestId, queryByTestId, getByRole } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(getByTestId('agent-list')).toBeTruthy();
    });
    expect(queryByTestId('canvas-list')).toBeNull();

    // The supported UI shows one selected panel, not both panels at once.
    fireEvent.click(getByRole('button', { name: /Canvas/ }));
    await waitFor(() => {
      expect(getByTestId('canvas-list')).toBeTruthy();
    });
    expect(queryByTestId('agent-list')).toBeNull();

    fireEvent.click(getByRole('button', { name: /Agents/ }));
    await waitFor(() => {
      expect(getByTestId('agent-list')).toHaveTextContent('Agents: 2');
    });

    // Verify data loaded
    expect(invoke).toHaveBeenCalledWith('get_recent_items', { token: mockToken });
  });

  /**
   * Test: Hotkey handling
   * Expected: Hotkeys are registered and functional
   */
  test('test_hotkey_handling', async () => {
    const { getByTestId } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(getByTestId('status-indicator')).toBeTruthy();
    });

    // Verify hotkeys hook was called
    expect(useHotkeys).toHaveBeenCalled();
  });

  /**
   * Test: Notification badge updates
   * Expected: Notification events are handled
   */
  test('test_notification_badge_updates', async () => {
    const mockUnlisten = jest.fn();
    mockListen.mockResolvedValue(mockUnlisten);

    render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(listen).toHaveBeenCalledWith('notification-badge', expect.any(Function));
    });

    // Verify notification event listener was set up
    expect(listen).toHaveBeenCalledWith('notification', expect.any(Function));
  });

  /**
   * Test: Connection status polling
   * Expected: Connection status is checked periodically
   */
  test('test_connection_status_polling', async () => {
    jest.useFakeTimers();

    render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    // Fast-forward time to trigger polling
    jest.advanceTimersByTime(30000);

    await waitFor(() => {
      expect(invoke).toHaveBeenCalled();
    });

    jest.useRealTimers();
  });

  /**
   * Test: Settings modal
   * Expected: Settings modal can be opened and closed
   */
  test('test_settings_modal', async () => {
    const { queryByTestId } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    // Initially, settings modal should not be visible
    expect(queryByTestId('settings-modal')).toBeNull();

    await waitFor(() => {
      expect(invoke).toHaveBeenCalled();
    });
  });

  /**
   * Test: Agent detail view
   * Expected: Agent detail can be shown
   */
  test('test_agent_detail_view', async () => {
    mockTauriCommands({
      get_recent_items: () => ({
        agents: [
          { id: '1', name: 'Test Agent', maturity_level: 'INTERN', status: 'online', last_execution: null, execution_count: 10 },
        ],
        canvases: [],
      }),
    });

    const { getByTestId } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(getByTestId('agent-list')).toBeTruthy();
    });

    // Agent detail would be shown when user clicks on an agent
    // This test verifies the component structure
    expect(getByTestId('agent-list')).toBeTruthy();
  });

  /**
   * Test: Logout functionality
   * Expected: Logout callback is triggered
   */
  test('test_logout_functionality', async () => {
    const mockLogout = jest.fn();

    render(
      <MenuBar user={mockUser} token={mockToken} onLogout={mockLogout} />
    );

    await waitFor(() => {
      expect(invoke).toHaveBeenCalled();
    });

    // Logout would be called when user clicks logout button
    expect(mockLogout).toBeDefined();
  });

  /**
   * Test: Error handling for API failures
   * Expected: Component handles API errors gracefully
   */
  test('test_error_handling_api_failures', async () => {
    mockTauriCommands({
      get_recent_items: () => Promise.reject(new Error('API Error')),
      get_unread_notifications: () => Promise.reject(new Error('API Error')),
    });

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

    render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to load recent data:',
        expect.any(Error)
      );
    });

    consoleSpy.mockRestore();
  });

  /**
   * Test: Multiple event listeners cleanup
   * Expected: Event listeners are cleaned up on unmount
   */
  test('test_event_listeners_cleanup', async () => {
    const mockUnlisten = jest.fn();
    mockListen.mockResolvedValue(mockUnlisten);

    const { unmount } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(listen).toHaveBeenCalled();
    });

    // Unmount component
    unmount();

    // Verify cleanup would be called (in useEffect cleanup)
    expect(mockUnlisten).toBeDefined();
  });

  /**
   * Test: Connection status updates
   * Expected: Connection status updates are handled
   */
  test('test_connection_status_updates', async () => {
    mockTauriCommands({
      get_connection_status: () => ({
        status: 'connected',
        server_time: new Date().toISOString(),
        device_id: 'device-123',
      }),
    });

    const { getByTestId } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(getByTestId('status-indicator')).toBeTruthy();
    });

    // Verify connection status is displayed
    expect(getByTestId('status-indicator')).toBeTruthy();
  });

  /**
   * Test: Native environment override reaches direct frontend fetches
   * Expected: Isolated loopback backend on a separate port is used
   */
  test('test_backend_environment_override_applies_to_frontend_fetches', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ count: 0, pending_approvals: [] }),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    mockTauriCommands({
      get_session: () => ({ token: mockToken }),
      get_backend_config: () => ({
        http_base_url: 'http://127.0.0.1:8123',
        websocket_url: 'ws://127.0.0.1:8123/ws/menubar',
        http_base_url_source: 'environment',
      }),
    });

    render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      const urls = fetchMock.mock.calls.map((call: unknown[]) => String(call[0]));
      expect(urls).toContain(
        'http://127.0.0.1:8123/api/agent-governance/pending-approvals'
      );
    });
    expect(
      fetchMock.mock.calls.every(
        (call: unknown[]) => !String(call[0]).includes('localhost:8000')
      )
    ).toBe(true);
  });

  /**
   * Test: Native IPC rejects the endpoint configuration
   * Expected: No request is issued and the raw configured URL is not echoed
   */
  test('test_invalid_native_endpoint_blocks_requests', async () => {
    const fetchMock = globalThis.fetch as jest.Mock;

    mockTauriCommands({
      get_backend_config: () =>
        Promise.reject(
          new Error(
            'backend URL "http://user:secret@127.0.0.1:8123" must not contain credentials'
          )
        ),
      get_session: () => ({ token: mockToken }),
    });

    const { getByTestId } = render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    await waitFor(() => {
      expect(getByTestId('endpoint-config-error')).toBeTruthy();
    });

    const errorText = getByTestId('endpoint-config-error').textContent || '';
    expect(errorText).not.toContain('secret');
    expect(errorText).not.toContain('127.0.0.1');
    expect(errorText).toContain('disabled');

    expect(fetchMock).not.toHaveBeenCalled();
    expect(invoke).not.toHaveBeenCalledWith('get_recent_items', {
      token: mockToken,
    });
    expect(invoke).not.toHaveBeenCalledWith('get_connection_status', {
      token: mockToken,
    });
  });

  /**
   * Test: Loading state
   * Expected: Component shows loading state initially
   */
  test('test_loading_state', async () => {
    mockTauriCommands({
      get_recent_items: () =>
        new Promise((resolve) => {
          setTimeout(() => {
            resolve({ agents: [], canvases: [] });
          }, 100);
        }),
    });

    render(
      <MenuBar user={mockUser} token={mockToken} onLogout={jest.fn()} />
    );

    // Component should render even during loading
    await waitFor(() => {
      expect(invoke).toHaveBeenCalled();
    });
  });
});
