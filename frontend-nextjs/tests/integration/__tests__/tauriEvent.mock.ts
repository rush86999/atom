/**
 * Tauri Event System Mock
 *
 * Mock for @tauri-apps/api/event emit/listen patterns.
 * Simulates bidirectional event communication between Rust backend and frontend.
 *
 * Event Channels:
 * - satellite_stdout/stderr: Satellite process output (main.rs:471, 482)
 * - cli-stdout/stderr: CLI command output (main.rs:303, 313)
 * - folder-event: File system changes (main.rs:842)
 * - location-update: Location service updates (main.rs:1527-1582)
 * - notification-sent: Notification delivery confirmation (main.rs:1554)
 *
 * @module tauriEvent.mock
 */

import { mockIPC } from '@tauri-apps/api/mocks';

/**
 * Event tracking record
 */
interface EventTracker {
  eventName: string;
  payload: unknown;
  timestamp: number;
  handlers: Array<(payload: unknown) => void>;
}

/**
 * Global event log
 * Records all emitted events for testing verification
 */
const eventLog: EventTracker[] = [];

/**
 * Active event listeners
 * Maps event names to their registered handler functions
 */
const activeListeners: Map<string, Array<(payload: unknown) => void>> = new Map();

/**
 * Counter for generating unique listener IDs
 */
let listenerIdCounter = 0;

/**
 * Mock emit function
 * Simulates app.emit() from main.rs
 *
 * @param eventName - Name of the event to emit
 * @param payload - Event payload (any serializable data)
 * @returns Promise<void>
 *
 * @example
 * ```typescript
 * await mockEmit('cli-stdout', 'Output line');
 * await mockEmit('folder-event', { path: '/tmp/file.txt', operation: 'create' });
 * ```
 */
export async function mockEmit(eventName: string, payload: unknown): Promise<void> {
  const timestamp = Date.now();

  // Log the event
  eventLog.push({
    eventName,
    payload,
    timestamp,
    handlers: [],
  });

  // Call all registered handlers for this event
  const handlers = activeListeners.get(eventName) || [];
  handlers.forEach((handler) => {
    try {
      handler(payload);
    } catch (error) {
      console.error(`Handler error for event "${eventName}":`, error);
    }
  });

  // Simulate async behavior from actual Tauri emit
  return Promise.resolve();
}

/**
 * Mock listen function
 * Simulates app.listen() from Tauri API
 *
 * @param eventName - Name of the event to listen for
 * @param handler - Callback function to invoke when event is emitted
 * @returns Unlisten function for cleanup
 *
 * @example
 * ```typescript
 * const unlisten = await mockListen('cli-stdout', (payload) => {
 *   console.log('Received:', payload);
 * });
 *
 * // Later: cleanup
 * unlisten();
 * ```
 */
export async function mockListen(
  eventName: string,
  handler: (payload: unknown) => void
): Promise<() => void> {
  // Validate event name
  if (typeof eventName !== 'string' || eventName.length === 0) {
    throw new Error('Event name must be a non-empty string');
  }

  // Initialize handlers array if not exists
  if (!activeListeners.has(eventName)) {
    activeListeners.set(eventName, []);
  }

  // Add handler to listeners
  const handlers = activeListeners.get(eventName)!;
  handlers.push(handler);

  // Create unlisten function
  const unlisten = () => {
    const index = handlers.indexOf(handler);
    if (index !== -1) {
      handlers.splice(index, 1);
    }
  };

  // Simulate async behavior from actual Tauri listen
  return Promise.resolve(unlisten);
}

/**
 * Get event log
 * Returns array of all emitted events
 *
 * @returns Array of EventTracker records
 *
 * @example
 * ```typescript
 * const events = getEventLog();
 * const stdoutEvents = events.filter(e => e.eventName === 'cli-stdout');
 * ```
 */
export function getEventLog(): EventTracker[] {
  return [...eventLog];
}

/**
 * Clear event log
 * Removes all events from log for test isolation
 *
 * @example
 * ```typescript
 * beforeEach(() => {
 *   clearEventLog();
 * });
 * ```
 */
export function clearEventLog(): void {
  eventLog.length = 0;
}

/**
 * Get active listeners count
 * Returns number of registered handlers per event
 *
 * @returns Map of event names to listener counts
 *
 * @example
 * ```typescript
 * const listeners = getActiveListeners();
 * console.log(listeners.get('cli-stdout')); // e.g., 2
 * ```
 */
export function getActiveListeners(): Map<string, number> {
  const counts = new Map<string, number>();
  activeListeners.forEach((handlers, eventName) => {
    counts.set(eventName, handlers.length);
  });
  return counts;
}

/**
 * Cleanup all listeners
 * Unregisters all event handlers (memory leak prevention)
 *
 * @example
 * ```typescript
 * afterEach(() => {
 *   cleanupAllListeners();
 * });
 * ```
 */
export function cleanupAllListeners(): void {
  activeListeners.clear();
  listenerIdCounter = 0;
}

/**
 * Setup event mocks
 * Configures Tauri IPC mocks for event testing
 *
 * @example
 * ```typescript
 * beforeAll(() => {
 *   setupEventMocks();
 * });
 * ```
 */
export function setupEventMocks(): void {
  // Mock IPC for Tauri commands if needed
  mockIPC((cmd) => {
    // Default IPC handler
    return { success: true };
  });
}

/**
 * Cleanup event mocks
 * Clears all event state after tests
 *
 * @example
 * ```typescript
 * afterAll(() => {
 *   cleanupEventMocks();
 * });
 * ```
 */
export function cleanupEventMocks(): void {
  clearEventLog();
  cleanupAllListeners();
}

// ============================================================================
// Event Channel Mocks - Predefined channel patterns from main.rs
// ============================================================================

/**
 * Satellite CLI event names
 */
export const SATELLITE_EVENTS = {
  STDOUT: 'satellite_stdout',
  STDERR: 'satellite_stderr',
} as const;

/**
 * CLI command event names
 */
export const CLI_EVENTS = {
  STDOUT: 'cli-stdout',
  STDERR: 'cli-stderr',
} as const;

/**
 * Folder watching event names
 */
export const FOLDER_EVENTS = {
  EVENT: 'folder-event',
} as const;

/**
 * Device event names
 */
export const DEVICE_EVENTS = {
  LOCATION_UPDATE: 'location-update',
  NOTIFICATION_SENT: 'notification-sent',
} as const;

/**
 * Mock satellite stdout event
 * Simulates satellite process output line (main.rs:471)
 *
 * @param line - Output line from satellite process
 *
 * @example
 * ```typescript
 * await mockSatelliteStdout('Starting satellite node...');
 * ```
 */
export async function mockSatelliteStdout(line: string): Promise<void> {
  return mockEmit(SATELLITE_EVENTS.STDOUT, line);
}

/**
 * Mock satellite stderr event
 * Simulates satellite process error line (main.rs:482)
 *
 * @param line - Error line from satellite process
 */
export async function mockSatelliteStderr(line: string): Promise<void> {
  return mockEmit(SATELLITE_EVENTS.STDERR, line);
}

/**
 * Mock CLI stdout event
 * Simulates command output (main.rs:303)
 *
 * @param line - Output line from command
 */
export async function mockCliStdout(line: string): Promise<void> {
  return mockEmit(CLI_EVENTS.STDOUT, line);
}

/**
 * Mock CLI stderr event
 * Simulates command error output (main.rs:313)
 *
 * @param line - Error line from command
 */
export async function mockCliStderr(line: string): Promise<void> {
  return mockEmit(CLI_EVENTS.STDERR, line);
}

/**
 * Mock folder event
 * Simulates file system change (main.rs:842)
 *
 * @param path - Full path to affected file
 * @param operation - Operation type: 'create', 'modify', 'remove'
 *
 * @example
 * ```typescript
 * await mockFolderEvent('/tmp/test.txt', 'create');
 * ```
 */
export async function mockFolderEvent(
  path: string,
  operation: 'create' | 'modify' | 'remove'
): Promise<void> {
  return mockEmit(FOLDER_EVENTS.EVENT, { path, operation });
}

/**
 * Mock location update event
 * Simulates location service update (main.rs:1527-1582)
 *
 * @param latitude - Latitude coordinate
 * @param longitude - Longitude coordinate
 * @param accuracy - Accuracy in meters
 */
export async function mockLocationUpdate(
  latitude: number,
  longitude: number,
  accuracy: number
): Promise<void> {
  return mockEmit(DEVICE_EVENTS.LOCATION_UPDATE, {
    latitude,
    longitude,
    accuracy,
    timestamp: new Date().toISOString(),
  });
}

/**
 * Mock notification sent event
 * Simulates notification delivery confirmation (main.rs:1554)
 *
 * @param title - Notification title
 * @param body - Notification body
 * @param success - Whether notification was sent successfully
 */
export async function mockNotificationSent(
  title: string,
  body: string,
  success: boolean
): Promise<void> {
  return mockEmit(DEVICE_EVENTS.NOTIFICATION_SENT, {
    title,
    body,
    success,
    sentAt: new Date().toISOString(),
  });
}

// ============================================================================
// Test Helper Functions
// ============================================================================

/**
 * Assert event was emitted
 * Throws if event not found in log
 *
 * @param eventName - Event name to check
 * @param payload - Optional payload to match
 *
 * @example
 * ```typescript
 * assertEventEmitted('cli-stdout', 'Expected output');
 * ```
 */
export function assertEventEmitted(
  eventName: string,
  payload?: unknown
): void {
  const events = eventLog.filter((e) => e.eventName === eventName);

  if (events.length === 0) {
    throw new Error(`Event "${eventName}" was not emitted`);
  }

  if (payload !== undefined) {
    const matching = events.some((e) => e.payload === payload);
    if (!matching) {
      throw new Error(
        `Event "${eventName}" was emitted but payload did not match`
      );
    }
  }
}

/**
 * Get events by name
 * Filters event log for specific event
 *
 * @param eventName - Event name to filter
 * @returns Array of matching events
 */
export function getEventsByName(eventName: string): EventTracker[] {
  return eventLog.filter((e) => e.eventName === eventName);
}

/**
 * Wait for event
 * Returns promise that resolves when event is emitted
 *
 * @param eventName - Event name to wait for
 * @param timeout - Timeout in milliseconds (default: 5000)
 * @returns Promise that resolves with event payload
 *
 * @example
 * ```typescript
 * const payload = await waitForEvent('cli-stdout', 1000);
 * console.log('Received:', payload);
 * ```
 */
export function waitForEvent(
  eventName: string,
  timeout: number = 5000
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(() => {
      unlisten();
      reject(new Error(`Event "${eventName}" not received within ${timeout}ms`));
    }, timeout);

    const unlistenFn = mockListen(eventName, (payload) => {
      clearTimeout(timeoutId);
      resolve(payload);
    });

    const unlisten = () => {
      unlistenFn.then((fn) => fn());
    };
  });
}
