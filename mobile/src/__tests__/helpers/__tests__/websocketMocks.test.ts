/**
 * websocketMocks Unit Tests
 *
 * Exercises every export of the Socket.IO mock helper library:
 * class lifecycle (connect/disconnect/emit/on/off/once), registry
 * functions, simulation helpers, and the jest factory.
 */

import {
  createMockSocket,
  getMockSocket,
  getAllMockSockets,
  resetMockSockets,
  simulateConnection,
  simulateDisconnection,
  simulateEvent,
  getEmittedEvents,
  getAllEmittedEvents,
  clearEmittedEvents,
  simulateReconnectAttempt,
  simulateReconnect,
  simulateReconnectFailed,
  simulateConnectionError,
  createSocketIOClientMock,
  setupWebSocketMocks,
  cleanupWebSocketMocks,
} from '../websocketMocks';

describe('createMockSocket', () => {
  beforeEach(() => {
    resetMockSockets();
  });

  it('creates a socket with unique id and registers it', () => {
    const socket = createMockSocket('ws://localhost:8000');
    expect(socket.id).toMatch(/^mock_socket_\d+$/);
    expect(socket.url).toBe('ws://localhost:8000');
    expect(socket.opts).toEqual({});
    expect(socket.connected).toBe(true);
    expect(getMockSocket(socket.id)).toBe(socket);
  });

  it('auto-connects by default', () => {
    const socket = createMockSocket('ws://localhost:8000');
    expect(socket.connected).toBe(true);
  });

  it('does not auto-connect when autoConnect is false', () => {
    const socket = createMockSocket('ws://localhost:8000', { autoConnect: false });
    expect(socket.connected).toBe(false);
  });

  it('preserves custom opts including connectDelay', () => {
    const socket = createMockSocket('ws://localhost:8000', { connectDelay: 10, auth: { token: 'x' } });
    expect(socket.opts.auth).toEqual({ token: 'x' });
    expect(socket.opts.connectDelay).toBe(10);
  });

  it('generates unique ids for each socket', () => {
    const a = createMockSocket('ws://a');
    const b = createMockSocket('ws://b');
    expect(a.id).not.toBe(b.id);
  });
});

describe('MockSocket lifecycle', () => {
  it('connect fires the connect event after connectDelay', () => {
    jest.useFakeTimers();
    const socket = createMockSocket('ws://localhost:8000', { autoConnect: false, connectDelay: 50 });
    const handler = jest.fn();
    socket.on('connect', handler);

    socket.connect();
    expect(socket.connected).toBe(true);
    expect(handler).not.toHaveBeenCalled();

    jest.advanceTimersByTime(50);
    expect(handler).toHaveBeenCalledWith(socket.id);
    jest.useRealTimers();
  });

  it('connect is a no-op when already connected', () => {
    const socket = createMockSocket('ws://localhost:8000');
    const handler = jest.fn();
    socket.on('connect', handler);
    socket.connect();
    expect(handler).not.toHaveBeenCalled();
  });

  it('disconnect clears connect timeout and fires disconnect event', () => {
    jest.useFakeTimers();
    const socket = createMockSocket('ws://localhost:8000', { autoConnect: false, connectDelay: 100 });
    const connectHandler = jest.fn();
    const disconnectHandler = jest.fn();
    socket.on('connect', connectHandler);
    socket.on('disconnect', disconnectHandler);
    socket.connect();
    socket.disconnect('bye');
    expect(socket.connected).toBe(false);
    expect(disconnectHandler).toHaveBeenCalledWith('bye');
    jest.advanceTimersByTime(200);
    expect(connectHandler).not.toHaveBeenCalled();
    jest.useRealTimers();
  });

  it('disconnect is a no-op when not connected', () => {
    const socket = createMockSocket('ws://localhost:8000', { autoConnect: false });
    const handler = jest.fn();
    socket.on('disconnect', handler);
    socket.disconnect();
    expect(handler).not.toHaveBeenCalled();
  });

  it('disconnect uses the default reason', () => {
    const socket = createMockSocket('ws://localhost:8000');
    const handler = jest.fn();
    socket.on('disconnect', handler);
    socket.disconnect();
    expect(handler).toHaveBeenCalledWith('client disconnect');
  });

  it('emit records single and multi-arg payloads', () => {
    const socket = createMockSocket('ws://localhost:8000');
    socket.emit('message', { text: 'hi' });
    socket.emit('join', 'room-1', 'room-2');

    expect(getEmittedEvents(socket.id)).toEqual([
      { event: 'message', data: { text: 'hi' } },
      { event: 'join', data: ['room-1', 'room-2'] },
    ]);
  });

  it('ping triggers pong after 10ms', () => {
    jest.useFakeTimers();
    const socket = createMockSocket('ws://localhost:8000');
    const handler = jest.fn();
    socket.on('pong', handler);

    socket.emit('ping');
    jest.advanceTimersByTime(10);
    expect(handler).toHaveBeenCalled();
    jest.useRealTimers();
  });

  it('on registers handlers and off removes specific or all handlers', () => {
    const socket = createMockSocket('ws://localhost:8000');
    const h1 = jest.fn();
    const h2 = jest.fn();
    socket.on('event', h1);
    socket.on('event', h2);
    expect(socket.eventHandlers.get('event')).toHaveLength(2);

    socket.off('event', h1);
    expect(socket.eventHandlers.get('event')).toHaveLength(1);

    socket.off('event', h1);
    expect(socket.eventHandlers.get('event')).toHaveLength(1);

    socket.off('event');
    expect(socket.eventHandlers.has('event')).toBe(false);
  });

  it('off with unknown event is a no-op', () => {
    const socket = createMockSocket('ws://localhost:8000');
    expect(() => socket.off('nope')).not.toThrow();
    expect(() => socket.off('nope', jest.fn())).not.toThrow();
  });

  it('once registers a handler that unregisters after firing', () => {
    const socket = createMockSocket('ws://localhost:8000');
    const handler = jest.fn();
    socket.once('tick', handler);

    simulateEvent(socket.id, 'tick', 1);
    simulateEvent(socket.id, 'tick', 2);

    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(1);
    expect(socket.eventHandlers.has('tick')).toBe(false);
  });

  it('_triggerEvent guards against missing handlers and handler exceptions', () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const socket = createMockSocket('ws://localhost:8000', { autoConnect: false });
    const errHandler = jest.fn(() => {
      throw new Error('boom');
    });
    socket.on('crash', errHandler);

    // Direct invocation exercises the class-private handler loop's catch
    (socket as any)._triggerEvent('crash');
    expect(errHandler).toHaveBeenCalled();
    expect(errorSpy).toHaveBeenCalled();
    errorSpy.mockRestore();
  });
});

describe('Registry functions', () => {
  beforeEach(() => {
    resetMockSockets();
  });

  it('getAllMockSockets returns all registered sockets', () => {
    createMockSocket('ws://a');
    createMockSocket('ws://b');
    expect(getAllMockSockets()).toHaveLength(2);
  });

  it('getMockSocket returns undefined for unknown id', () => {
    expect(getMockSocket('missing')).toBeUndefined();
  });

  it('resetMockSockets disconnects connected sockets and clears registry', () => {
    const socket = createMockSocket('ws://a');
    const handler = jest.fn();
    socket.on('disconnect', handler);

    resetMockSockets();

    expect(handler).toHaveBeenCalledWith('test cleanup');
    expect(getAllMockSockets()).toHaveLength(0);
    expect(getMockSocket(socket.id)).toBeUndefined();
  });

  it('resetMockSockets restarts the id counter', () => {
    createMockSocket('ws://a');
    resetMockSockets();
    const fresh = createMockSocket('ws://b');
    expect(fresh.id).toBe('mock_socket_1');
  });
});

describe('Simulation helpers', () => {
  beforeEach(() => {
    resetMockSockets();
  });

  it('simulateConnection connects a disconnected socket', () => {
    const socket = createMockSocket('ws://a', { autoConnect: false });
    simulateConnection(socket.id);
    expect(socket.connected).toBe(true);
  });

  it('simulateConnection is idempotent when already connected', () => {
    const socket = createMockSocket('ws://a');
    simulateConnection(socket.id);
    expect(socket.connected).toBe(true);
  });

  it('simulateConnection throws for unknown socket', () => {
    expect(() => simulateConnection('missing')).toThrow('Socket not found: missing');
  });

  it('simulateDisconnection disconnects with given reason', () => {
    const socket = createMockSocket('ws://a');
    simulateDisconnection(socket.id, 'server closed');
    expect(socket.connected).toBe(false);
  });

  it('simulateDisconnection is a no-op when disconnected and throws for unknown', () => {
    const socket = createMockSocket('ws://a', { autoConnect: false });
    expect(() => simulateDisconnection(socket.id)).not.toThrow();
    expect(() => simulateDisconnection('missing')).toThrow('Socket not found: missing');
  });

  it('simulateEvent delivers data to handlers and warns without handlers', () => {
    const socket = createMockSocket('ws://a');
    const handler = jest.fn();
    socket.on('data', handler);
    simulateEvent(socket.id, 'data', { ok: true });
    expect(handler).toHaveBeenCalledWith({ ok: true });

    const warn = jest.spyOn(console, 'warn').mockImplementation(() => {});
    simulateEvent(socket.id, 'nothing-listens', 1);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  it('simulateEvent catches handler errors and throws for unknown socket', () => {
    const socket = createMockSocket('ws://a');
    socket.on('boom', () => {
      throw new Error('handler failure');
    });
    expect(() => simulateEvent(socket.id, 'boom')).not.toThrow();
    expect(() => simulateEvent('missing', 'x')).toThrow('Socket not found: missing');
  });

  it('getAllEmittedEvents aggregates across sockets', () => {
    const a = createMockSocket('ws://a');
    const b = createMockSocket('ws://b');
    a.emit('one', 1);
    b.emit('two', 2);

    expect(getAllEmittedEvents()).toEqual([
      { socketId: a.id, event: 'one', data: 1 },
      { socketId: b.id, event: 'two', data: 2 },
    ]);
  });

  it('clearEmittedEvents empties a socket history and throws for unknown', () => {
    const socket = createMockSocket('ws://a');
    socket.emit('one', 1);
    clearEmittedEvents(socket.id);
    expect(getEmittedEvents(socket.id)).toEqual([]);
    expect(() => clearEmittedEvents('missing')).toThrow('Socket not found: missing');
    expect(() => getEmittedEvents('missing')).toThrow('Socket not found: missing');
  });

  it('simulateReconnectAttempt forwards the attempt number', () => {
    const socket = createMockSocket('ws://a');
    const handler = jest.fn();
    socket.on('reconnect_attempt', handler);
    simulateReconnectAttempt(socket.id, 3);
    expect(handler).toHaveBeenCalledWith(3);
  });

  it('simulateReconnect marks connected and emits reconnect', () => {
    const socket = createMockSocket('ws://a', { autoConnect: false });
    const handler = jest.fn();
    socket.on('reconnect', handler);
    simulateReconnect(socket.id, 2);
    expect(socket.connected).toBe(true);
    expect(handler).toHaveBeenCalledWith(2);
    expect(() => simulateReconnect('missing', 1)).toThrow('Socket not found: missing');
  });

  it('simulateReconnectFailed marks disconnected and emits reconnect_failed', () => {
    const socket = createMockSocket('ws://a');
    const handler = jest.fn();
    socket.on('reconnect_failed', handler);
    simulateReconnectFailed(socket.id);
    expect(socket.connected).toBe(false);
    expect(handler).toHaveBeenCalled();
    expect(() => simulateReconnectFailed('missing')).toThrow('Socket not found: missing');
  });

  it('simulateConnectionError emits connect_error with string or Error payload', () => {
    const socket = createMockSocket('ws://a');
    const handler = jest.fn();
    socket.on('connect_error', handler);

    simulateConnectionError(socket.id, 'boom');
    expect(socket.connected).toBe(false);
    expect(handler).toHaveBeenCalledWith(expect.any(Error));

    simulateConnectionError(socket.id, new Error('real error'));
    expect(handler).toHaveBeenLastCalledWith(expect.any(Error));
    expect(() => simulateConnectionError('missing', 'x')).toThrow('Socket not found: missing');
  });
});

describe('Jest integration helpers', () => {
  it('createSocketIOClientMock returns a jest.fn that builds mock sockets', () => {
    const factory = createSocketIOClientMock();
    const socket = factory('ws://localhost:8000', { auth: { token: 't' } });

    expect(factory).toHaveBeenCalledWith('ws://localhost:8000', { auth: { token: 't' } });
    expect(socket.url).toBe('ws://localhost:8000');
    expect(socket.connected).toBe(true);
    expect(getMockSocket(socket.id)).toBe(socket);
  });

  it('setupWebSocketMocks and cleanupWebSocketMocks reset the registry', () => {
    createMockSocket('ws://a');
    setupWebSocketMocks();
    expect(getAllMockSockets()).toHaveLength(0);

    createMockSocket('ws://b');
    cleanupWebSocketMocks();
    expect(getAllMockSockets()).toHaveLength(0);
  });
});
