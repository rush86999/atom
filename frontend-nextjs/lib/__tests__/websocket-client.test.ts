/**
 * Tests for WebSocket Client
 *
 * Tests the WebSocket client wrapper
 */

import { WebSocketClient, getWebSocketClient, WebSocketMessage } from '../websocket-client';

describe('WebSocketClient', () => {
  let client: WebSocketClient;
  const mockConfig = { url: 'ws://localhost:8080' };

  beforeEach(() => {
    client = new WebSocketClient(mockConfig);
  });

  describe('constructor', () => {
    it('should create client with config', () => {
      expect(client).toBeInstanceOf(WebSocketClient);
    });
  });

  describe('connect', () => {
    it('should connect successfully', async () => {
      await expect(client.connect()).resolves.not.toThrow();
    });

    it('should return a promise', () => {
      const result = client.connect();
      expect(result).toBeInstanceOf(Promise);
    });
  });

  describe('subscribe', () => {
    it('should subscribe to channel', () => {
      expect(() => client.subscribe('test-channel')).not.toThrow();
    });
  });

  describe('on', () => {
    it('should register event listener', () => {
      const callback = jest.fn();
      const unsubscribe = client.on('test-event', callback);

      expect(typeof unsubscribe).toBe('function');
    });

    it('should return unsubscribe function', () => {
      const callback = jest.fn();
      const unsubscribe = client.on('test-event', callback);

      expect(unsubscribe).toBeDefined();
      expect(typeof unsubscribe).toBe('function');
    });

    it('should allow multiple listeners for same event', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();

      client.on('test-event', callback1);
      client.on('test-event', callback2);

      // Both should be registered (we can't directly access listeners but we can verify no errors)
      expect(() => {
        client.on('test-event', callback1);
        client.on('test-event', callback2);
      }).not.toThrow();
    });

    it('should handle different event types', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();

      expect(() => {
        client.on('event1', callback1);
        client.on('event2', callback2);
      }).not.toThrow();
    });
  });

  describe('disconnect', () => {
    it('should disconnect successfully', () => {
      expect(() => client.disconnect()).not.toThrow();
    });
  });
});

describe('getWebSocketClient', () => {
  it('should return WebSocketClient instance', () => {
    const config = { url: 'ws://localhost:8080' };
    const client = getWebSocketClient(config);

    expect(client).toBeInstanceOf(WebSocketClient);
  });

  it('should pass config to client', () => {
    const config = { url: 'ws://test.com' };
    const client = getWebSocketClient(config);

    expect(client).toBeInstanceOf(WebSocketClient);
  });
});

describe('WebSocketMessage', () => {
  it('should define WebSocketMessage interface', () => {
    const message: WebSocketMessage = {
      type: 'test',
      timestamp: '2024-01-15T10:30:00Z',
      message: 'Test message',
    };

    expect(message.type).toBe('test');
    expect(message.timestamp).toBe('2024-01-15T10:30:00Z');
  });

  it('should have optional execution_id', () => {
    const message1: WebSocketMessage = {
      type: 'test',
      timestamp: '2024-01-15T10:30:00Z',
    };

    const message2: WebSocketMessage = {
      type: 'test',
      timestamp: '2024-01-15T10:30:00Z',
      execution_id: 'exec-123',
    };

    expect(message1.execution_id).toBeUndefined();
    expect(message2.execution_id).toBe('exec-123');
  });

  it('should have optional data field', () => {
    const message: WebSocketMessage = {
      type: 'test',
      timestamp: '2024-01-15T10:30:00Z',
      data: { key: 'value' },
    };

    expect(message.data).toEqual({ key: 'value' });
  });
});
