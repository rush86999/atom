/**
 * Device Socket Service Tests
 *
 * Tests for the Socket.IO device service:
 * - Connection lifecycle (auth token, device id, connect/register, disconnect)
 * - Reconnect limits (max attempts -> disconnect)
 * - Heartbeat (interval, probe response, cleanup on disconnect)
 * - Message routing (command dispatch, malformed messages)
 * - Command handlers (camera, location, notification, execute, unknown)
 * - Result delivery (immediate when connected, queued + flushed on reconnect)
 */

import { io } from 'socket.io-client';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { deviceSocketService } from '../../services/deviceSocket';
import { resetAllMocks } from '../helpers/mockExpoModules';

// Captured Socket.IO event handlers keyed by event name
const eventHandlers = new Map<string, (data: any) => void>();

const mockSocket = {
  on: jest.fn((event: string, cb: (data: any) => void) => {
    eventHandlers.set(event, cb);
  }),
  emit: jest.fn(),
  disconnect: jest.fn(),
  connected: false,
};

jest.mock('socket.io-client', () => ({
  io: jest.fn(() => mockSocket),
}));

// deviceSocket does `import * as Notifications from 'expo-notifications'` —
// babel's wildcard interop snapshots the module at import time, so any
// property added later (e.g. via Object.assign) is invisible to the service.
// The factory must include AndroidNotificationPriority from the start.
jest.mock('expo-notifications', () => {
  const mockNotifications = {
    requestPermissionsAsync: jest.fn().mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
      expires: 'never',
      ios: { allowsAlert: true, allowsBadge: true, allowsSound: true },
      android: {},
    }),
    getPermissionsAsync: jest.fn().mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
      expires: 'never',
    }),
    getBadgeCountAsync: jest.fn().mockResolvedValue(0),
    setBadgeCountAsync: jest.fn().mockResolvedValue(undefined),
    scheduleNotificationAsync: jest.fn().mockResolvedValue('notification-id-123'),
    cancelScheduledNotificationAsync: jest.fn().mockResolvedValue(undefined),
    cancelAllScheduledNotificationsAsync: jest.fn().mockResolvedValue(undefined),
    getAllScheduledNotificationsAsync: jest.fn().mockResolvedValue([]),
    getExpoPushTokenAsync: jest.fn().mockResolvedValue({
      type: 'expo',
      data: 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]',
    }),
    presentNotificationAsync: jest.fn().mockResolvedValue(undefined),
    dismissNotificationAsync: jest.fn().mockResolvedValue(undefined),
    dismissAllNotificationsAsync: jest.fn().mockResolvedValue(undefined),
    getAllNotificationsAsync: jest.fn().mockResolvedValue([]),
    // Capture the handler so tests can invoke it (mock call history is wiped
    // by clearAllMocks between tests).
    setNotificationHandler: jest.fn((handler: any) => {
      (global as any).__notificationHandler = handler;
    }),
    setNotificationChannelAsync: jest.fn().mockResolvedValue(undefined),
    addNotificationReceivedListener: jest.fn().mockReturnValue({ remove: jest.fn() }),
    addNotificationResponseReceivedListener: jest.fn().mockReturnValue({ remove: jest.fn() }),
    removeNotificationSubscription: jest.fn(),
    AndroidNotificationPriority: { HIGH: 'high', DEFAULT: 'default', LOW: 'low' },
    AndroidImportance: { HIGH: 'high', DEFAULT: 'default', LOW: 'low' },
    NotificationContentInput: jest.fn(),
    NotificationRequestInput: jest.fn(),
  };
  return {
    ...mockNotifications,
    Notifications: mockNotifications,
    Notification: class MockNotification {},
    default: mockNotifications,
  };
});

const mockIo = io as jest.MockedFunction<typeof io>;
const mockSecureStore = () => require('expo-secure-store');
const mockNotifications = () => require('expo-notifications');
const mockCamera = () => require('expo-camera');
const mockLocation = () => require('expo-location');
const mockFileSystem = () => require('expo-file-system');

const flushMicrotasks = async () => {
  for (let i = 0; i < 10; i++) {
    await Promise.resolve();
  }
};

const fire = (event: string, data?: any) => {
  const handler = eventHandlers.get(event);
  if (!handler) {
    throw new Error(`No handler registered for event "${event}"`);
  }
  return handler(data);
};

// The 'message' handler dispatches asynchronously (handleMessage is not
// awaited by the socket callback) — fire the event, then drain microtasks so
// command handlers and their result emissions complete before assertions.
const fireMessage = async (message: any) => {
  fire('message', message);
  await flushMicrotasks();
};

const command = (command: string, params: Record<string, any> = {}, commandId = 'cmd-1') => ({
  type: 'command',
  command_id: commandId,
  command,
  params,
  timestamp: new Date().toISOString(),
});

describe('deviceSocketService', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    eventHandlers.clear();

    // Reset ALL expo module mocks to their defaults — implementations set in
    // one test (denied permissions, rejected captures, …) otherwise leak
    // into the next test.
    resetAllMocks();

    (global as any).__resetAsyncStorageMock?.();
    (global as any).__resetSecureStoreMock?.();

    // Reset private singleton state first — disconnect() emits on the mock
    // socket, so clear the mocks' call history AFTERwards.
    deviceSocketService.disconnect();
    (deviceSocketService as any).reconnectAttempts = 0;
    (deviceSocketService as any).pendingResults = [];

    mockSocket.on.mockClear();
    mockSocket.emit.mockClear();
    mockSocket.disconnect.mockClear();
    mockSocket.connected = false;

    // Default mocks
    mockIo.mockClear();
    mockIo.mockReturnValue(mockSocket as any);
    // R82: deviceSocket reads the canonical 'atom_access_token' key
    // (legacy 'auth_token' is never written since the #6 storage fix).
    await mockSecureStore().setItemAsync('atom_access_token', 'test-token');

    // expo-file-system mock (jest.setup) lacks copyAsync; the service imports
    // it as default, which shares the module object, so this is visible.
    Object.assign(mockFileSystem(), { copyAsync: jest.fn().mockResolvedValue(undefined) });
  });

  // ========================================================================
  // Connection Tests
  // ========================================================================

  describe('Connection', () => {
    test('should configure the notification handler on startup', async () => {
      const handler = (global as any).__notificationHandler;
      expect(handler).toBeDefined();

      const behavior = await handler.handleNotification();
      expect(behavior).toEqual({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      });
    });

    test('should refuse to connect when the auth token is unavailable', async () => {
      await mockSecureStore().deleteItemAsync('atom_access_token');

      const result = await deviceSocketService.connect();

      expect(result).toBe(false);
      expect(mockIo).not.toHaveBeenCalled();
    });

    test('should fail safely when token retrieval throws', async () => {
      mockSecureStore().getItemAsync.mockRejectedValueOnce(new Error('keychain error'));

      const result = await deviceSocketService.connect();

      expect(result).toBe(false);
      expect(mockIo).not.toHaveBeenCalled();
    });

    test('should connect with the auth token in the query', async () => {
      const result = await deviceSocketService.connect();

      expect(result).toBe(true);
      expect(mockIo).toHaveBeenCalledWith(
        'http://localhost:8000',
        expect.objectContaining({
          query: { token: 'test-token' },
          transports: ['websocket'],
          reconnection: true,
          reconnectionAttempts: 5,
        })
      );
    });

    test('should generate and persist a device id on first connect', async () => {
      expect(await AsyncStorage.getItem('device_node_id')).toBeNull();

      await deviceSocketService.connect();

      const deviceId = await AsyncStorage.getItem('device_node_id');
      expect(deviceId).toMatch(/^mobile_/);
    });

    test('should reuse an existing device id', async () => {
      await AsyncStorage.setItem('device_node_id', 'device-123');

      await deviceSocketService.connect();

      expect(await AsyncStorage.getItem('device_node_id')).toBe('device-123');
    });

    test('should register the device when connected', async () => {
      await deviceSocketService.connect();

      fire('connect');

      expect(deviceSocketService.connected()).toBe(true);
      expect(mockSocket.emit).toHaveBeenCalledWith(
        'message',
        expect.objectContaining({
          type: 'register',
          device_node_id: expect.stringMatching(/^mobile_/),
        })
      );
      const register = mockSocket.emit.mock.calls[0][1];
      expect(register.device_info.node_type).toBe('mobile');
      expect(register.device_info.capabilities).toEqual(
        expect.arrayContaining(['camera', 'location', 'notification'])
      );
    });

    test('should disconnect and clean up the socket', async () => {
      await deviceSocketService.connect();
      fire('connect');
      fire('registered', { device_node_id: 'd1' });

      deviceSocketService.disconnect();

      expect(mockSocket.disconnect).toHaveBeenCalled();
      expect(deviceSocketService.connected()).toBe(false);
    });
  });

  // ========================================================================
  // Reconnection Tests
  // ========================================================================

  describe('Reconnection', () => {
    test('should stop reconnecting and disconnect after max attempts', async () => {
      await deviceSocketService.connect();

      // 5 consecutive connection errors -> service gives up
      for (let i = 0; i < 5; i++) {
        fire('connect_error', new Error('boom'));
      }

      expect(mockSocket.disconnect).toHaveBeenCalled();
      expect(deviceSocketService.connected()).toBe(false);
    });

    test('should keep trying before the attempt limit is reached', async () => {
      await deviceSocketService.connect();

      fire('connect_error', new Error('boom'));

      expect(mockSocket.disconnect).not.toHaveBeenCalled();
    });

    test('should mark disconnected and stop heartbeat on socket disconnect', async () => {
      await deviceSocketService.connect();
      fire('connect');
      fire('registered', { device_node_id: 'd1' });

      fire('disconnect', 'transport close');

      expect(deviceSocketService.connected()).toBe(false);
      // Heartbeat interval is cleared — no further heartbeats
      const heartbeatEmits = mockSocket.emit.mock.calls.filter(
        (call) => call[1] && call[1].type === 'heartbeat'
      ).length;
      jest.advanceTimersByTime(90 * 1000);
      expect(
        mockSocket.emit.mock.calls.filter((call) => call[1] && call[1].type === 'heartbeat').length
      ).toBe(heartbeatEmits);
    });
  });

  // ========================================================================
  // Heartbeat Tests
  // ========================================================================

  describe('Heartbeat', () => {
    test('should send a heartbeat every 30 seconds after registration', async () => {
      await deviceSocketService.connect();
      fire('connect');
      fire('registered', { device_node_id: 'd1' });

      jest.advanceTimersByTime(30 * 1000);

      expect(mockSocket.emit).toHaveBeenCalledWith(
        'message',
        expect.objectContaining({ type: 'heartbeat' })
      );
    });

    test('should restart the heartbeat interval on re-registration', async () => {
      await deviceSocketService.connect();
      fire('connect');
      fire('registered', { device_node_id: 'd1' });
      // Re-registration replaces the existing interval without leaking it
      fire('registered', { device_node_id: 'd1' });

      jest.advanceTimersByTime(30 * 1000);

      expect(
        mockSocket.emit.mock.calls.filter((call) => call[1] && call[1].type === 'heartbeat')
      ).toHaveLength(1);
    });

    test('should respond to a heartbeat probe immediately', async () => {
      await deviceSocketService.connect();
      fire('connect');

      mockSocket.emit.mockClear();
      fire('heartbeat_probe', {});

      expect(mockSocket.emit).toHaveBeenCalledWith(
        'message',
        expect.objectContaining({ type: 'heartbeat' })
      );
    });

    test('should not emit heartbeats while disconnected', async () => {
      await deviceSocketService.connect();
      // No 'connect' event -> isConnected stays false

      jest.advanceTimersByTime(60 * 1000);

      expect(
        mockSocket.emit.mock.calls.filter((call) => call[1] && call[1].type === 'heartbeat')
      ).toHaveLength(0);
    });
  });

  // ========================================================================
  // Message Routing Tests
  // ========================================================================

  describe('Message Routing', () => {
    test('should handle welcome "connected" messages without crashing', async () => {
      await deviceSocketService.connect();
      fire('connect');

      await fireMessage({ type: 'connected', text: 'welcome' });
      expect(deviceSocketService.connected()).toBe(true);
    });

    test('should tolerate malformed messages without throwing', async () => {
      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(null);
      await fireMessage({});
      await fireMessage('not-an-object');

      expect(deviceSocketService.connected()).toBe(true);
    });

    test('should warn on unknown message types', async () => {
      const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
      await deviceSocketService.connect();
      fire('connect');

      await fireMessage({ type: 'mystery' });

      expect(warn).toHaveBeenCalled();
      warn.mockRestore();
    });
  });

  // ========================================================================
  // Command Handling Tests
  // ========================================================================

  describe('Command Handling', () => {
    test('should execute camera_snap and send the photo result', async () => {
      mockCamera().takePictureAsync.mockResolvedValue({
        uri: 'file:///photo.jpg',
        base64: 'aGVsbG8=',
        width: 1920,
        height: 1080,
      });

      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('camera_snap', { quality: 0.5 }));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({
        type: 'result',
        command_id: 'cmd-1',
        success: true,
        data: { base64_data: 'aGVsbG8=', width: 1920, height: 1080 },
      });
    });

    test('should reject camera_snap when permission is denied', async () => {
      mockCamera().requestCameraPermissionsAsync.mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('camera_snap'));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({
        type: 'result',
        success: false,
        error: 'Camera permission not granted',
      });
    });

    test('should report camera capture failures', async () => {
      mockCamera().takePictureAsync.mockRejectedValue(new Error('camera busy'));

      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('camera_snap'));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({ type: 'result', success: false, error: 'camera busy' });
    });

    test('should save the photo when save_path is provided', async () => {
      mockCamera().takePictureAsync.mockResolvedValue({
        uri: 'file:///photo.jpg',
        base64: 'aGVsbG8=',
        width: 100,
        height: 100,
      });

      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('camera_snap', { save_path: '/tmp/out.jpg' }));

      expect(mockFileSystem().copyAsync).toHaveBeenCalledWith({
        from: 'file:///photo.jpg',
        to: '/tmp/out.jpg',
      });
      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result.file_path).toBe('/tmp/out.jpg');
    });

    test('should return coordinates for get_location', async () => {
      mockLocation().getCurrentPositionAsync.mockResolvedValue({
        coords: {
          latitude: 37.7749,
          longitude: -122.4194,
          altitude: 10,
          accuracy: 5,
          heading: 90,
          speed: 1.5,
        },
        timestamp: Date.now(),
      });

      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('get_location'));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({
        type: 'result',
        success: true,
        data: { latitude: 37.7749, longitude: -122.4194, accuracy: 5 },
      });
    });

    test('should reject get_location when permission is denied', async () => {
      mockLocation().requestForegroundPermissionsAsync.mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('get_location'));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({ type: 'result', success: false });
      expect(result.error).toContain('Location permission');
    });

    test('should report non-Error location failures with the fallback message', async () => {
      mockLocation().getCurrentPositionAsync.mockRejectedValue('gps-unavailable');

      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('get_location'));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({
        type: 'result',
        success: false,
        error: 'Failed to get location',
      });
    });

    test('should send a notification when permission is granted', async () => {
      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('send_notification', { title: 'Hi', body: 'There' }));

      expect(mockNotifications().scheduleNotificationAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          content: expect.objectContaining({ title: 'Hi', body: 'There' }),
          trigger: null,
        })
      );
      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({ type: 'result', success: true });
    });

    test('should reject send_notification when permission is denied', async () => {
      mockNotifications().requestPermissionsAsync.mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('send_notification'));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({ type: 'result', success: false });
      expect(result.error).toContain('Notification permission');
    });

    test('should report non-Error notification failures with the fallback message', async () => {
      mockNotifications().scheduleNotificationAsync.mockRejectedValue('push-disabled');

      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('send_notification'));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({
        type: 'result',
        success: false,
        error: 'Failed to send notification',
      });
    });

    test('should always reject execute_command on mobile', async () => {
      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('execute_command', { command: 'rm -rf /' }));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({
        type: 'result',
        success: false,
        error: 'Command execution not supported on mobile devices',
      });
    });

    test('should reject screen recording commands', async () => {
      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('screen_record_start'));
      const startResult = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(startResult.success).toBe(false);

      await fireMessage(command('screen_record_stop'));
      const stopResult = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(stopResult.success).toBe(false);
    });

    test('should return an error result for unknown commands', async () => {
      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('definitely_not_real'));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({
        type: 'result',
        command_id: 'cmd-1',
        success: false,
        error: 'Unknown command: definitely_not_real',
      });
    });

    test('should send an error result when a handler throws', async () => {
      mockCamera().requestCameraPermissionsAsync.mockRejectedValue(new Error('native crash'));

      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('camera_snap'));

      const result = mockSocket.emit.mock.calls.at(-1)?.[1];
      expect(result).toMatchObject({ type: 'result', success: false, error: 'native crash' });
    });
  });

  // ========================================================================
  // Result Delivery Tests
  // ========================================================================

  describe('Result Delivery', () => {
    test('should queue results while disconnected and flush them after registration', async () => {
      mockCamera().takePictureAsync.mockResolvedValue({
        uri: 'file:///photo.jpg',
        base64: 'aGVsbG8=',
        width: 100,
        height: 100,
      });

      await deviceSocketService.connect();
      // NOTE: 'connect' is never fired -> isConnected stays false

      await fireMessage(command('camera_snap'));

      // Command executed but result is queued, not dropped
      expect(mockSocket.emit).not.toHaveBeenCalledWith(
        'message',
        expect.objectContaining({ type: 'result', command_id: 'cmd-1' })
      );

      // Reconnect + register flushes the queued result
      fire('connect');
      fire('registered', { device_node_id: 'd1' });

      expect(mockSocket.emit).toHaveBeenCalledWith(
        'message',
        expect.objectContaining({ type: 'result', command_id: 'cmd-1', success: true })
      );
    });

    test('should emit results immediately when connected', async () => {
      await deviceSocketService.connect();
      fire('connect');

      await fireMessage(command('unknown_thing'));

      expect(mockSocket.emit).toHaveBeenCalledWith(
        'message',
        expect.objectContaining({ type: 'result', command_id: 'cmd-1' })
      );
    });

    test('should cap the number of queued results while disconnected', async () => {
      mockCamera().takePictureAsync.mockResolvedValue({
        uri: 'file:///photo.jpg',
        base64: 'aGVsbG8=',
        width: 100,
        height: 100,
      });

      await deviceSocketService.connect();
      // 'connect' never fires -> isConnected stays false, results queue up

      for (let i = 0; i < 60; i++) {
        await fireMessage(command('camera_snap', {}, `cmd-${i}`));
      }

      // Queue is bounded — the newest 50 are kept
      const queued = (deviceSocketService as any).pendingResults as any[];
      expect(queued.length).toBe(50);
      expect(queued[0].command_id).toBe('cmd-10');
      expect(queued[queued.length - 1].command_id).toBe('cmd-59');

      // Reconnecting flushes exactly the retained results
      fire('connect');
      fire('registered', { device_node_id: 'd1' });
      expect((deviceSocketService as any).pendingResults.length).toBe(0);
      const resultEmits = mockSocket.emit.mock.calls.filter(
        (call) => call[1] && call[1].type === 'result'
      );
      expect(resultEmits).toHaveLength(50);
    });
  });
});
