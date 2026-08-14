/**
 * test-helpers Unit Tests
 *
 * Tests for the reusable mocking utilities in hooks/test-helpers.ts:
 * createMockWebSocket, createMockSpeechRecognition, createMockSpeechSynthesis,
 * setupFakeTimers/cleanupFakeTimers, mockFetchResponse/mockFetchError, and
 * createMockEventListeners.
 */

import {
  createMockWebSocket,
  createMockSpeechRecognition,
  createMockSpeechSynthesis,
  setupFakeTimers,
  cleanupFakeTimers,
  mockFetchResponse,
  mockFetchError,
  createMockEventListeners,
} from '../test-helpers';

describe('test-helpers.ts', () => {
  afterEach(() => {
    jest.useRealTimers();
  });

  describe('createMockWebSocket', () => {
    test('creates a mock with CONNECTING readyState by default', () => {
      const ws = createMockWebSocket();
      expect(ws.readyState).toBe(0);
      expect(ws.url).toBe('');
      expect(ws.protocol).toBe('');
      expect(ws.onopen).toBeNull();
      expect(ws.onmessage).toBeNull();
      expect(ws.onerror).toBeNull();
      expect(ws.onclose).toBeNull();
      expect(jest.isMockFunction(ws.send)).toBe(true);
      expect(jest.isMockFunction(ws.close)).toBe(true);
      expect(jest.isMockFunction(ws.addEventListener)).toBe(true);
      expect(jest.isMockFunction(ws.removeEventListener)).toBe(true);
    });

    test('respects custom options', () => {
      const ws = createMockWebSocket({ readyState: 1, delayOpen: true });
      expect(ws.readyState).toBe(1);
    });

    test('simulateOpen fires onopen and flips readyState to OPEN', () => {
      const ws = createMockWebSocket();
      const handler = jest.fn();
      ws.onopen = handler;

      ws.simulateOpen();

      expect(ws.readyState).toBe(WebSocket.OPEN);
      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler.mock.calls[0][0]).toBeInstanceOf(Event);
    });

    test('simulateOpen is a no-op when onopen is not set', () => {
      const ws = createMockWebSocket();
      expect(() => ws.simulateOpen()).not.toThrow();
    });

    test('simulateMessage delivers a parsed message event', () => {
      const ws = createMockWebSocket();
      const handler = jest.fn();
      ws.onmessage = handler;

      ws.simulateMessage({ type: 'ping' });

      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler.mock.calls[0][0].data).toBe('{"type":"ping"}');
    });

    test('simulateMessage passes raw strings through unchanged', () => {
      const ws = createMockWebSocket();
      const handler = jest.fn();
      ws.onmessage = handler;

      ws.simulateMessage('raw payload');

      expect(handler.mock.calls[0][0].data).toBe('raw payload');
    });

    test('simulateMessage is a no-op when onmessage is not set', () => {
      const ws = createMockWebSocket();
      expect(() => ws.simulateMessage('x')).not.toThrow();
    });

    test('simulateClose fires onclose with the given code and reason', () => {
      const ws = createMockWebSocket();
      const handler = jest.fn();
      ws.onclose = handler;

      ws.simulateClose(1001, 'Going away');

      expect(ws.readyState).toBe(WebSocket.CLOSED);
      expect(handler).toHaveBeenCalledTimes(1);
      const event = handler.mock.calls[0][0];
      expect(event.code).toBe(1001);
      expect(event.reason).toBe('Going away');
    });

    test('simulateClose defaults to 1000 / Normal closure', () => {
      const ws = createMockWebSocket();
      const handler = jest.fn();
      ws.onclose = handler;

      ws.simulateClose();

      const event = handler.mock.calls[0][0];
      expect(event.code).toBe(1000);
      expect(event.reason).toBe('Normal closure');
    });

    test('simulateError fires onerror with the provided event', () => {
      const ws = createMockWebSocket();
      const handler = jest.fn();
      ws.onerror = handler;

      ws.simulateError();

      expect(handler).toHaveBeenCalledTimes(1);
    });

    test('simulateError is a no-op when onerror is not set', () => {
      const ws = createMockWebSocket();
      expect(() => ws.simulateError()).not.toThrow();
    });
  });

  describe('createMockSpeechRecognition', () => {
    test('creates a mock with default properties and spies', () => {
      const rec = createMockSpeechRecognition();
      expect(rec.continuous).toBe(false);
      expect(rec.interimResults).toBe(false);
      expect(rec.lang).toBe('en-US');
      expect(rec.maxAlternatives).toBe(1);
      expect(jest.isMockFunction(rec.start)).toBe(true);
      expect(jest.isMockFunction(rec.stop)).toBe(true);
      expect(jest.isMockFunction(rec.abort)).toBe(true);
      expect(rec.onresult).toBeNull();
      expect(rec.onerror).toBeNull();
      expect(rec.onend).toBeNull();
      expect(rec.onstart).toBeNull();
    });

    test('triggerResult fires onresult with transcript and isFinal', () => {
      const rec = createMockSpeechRecognition();
      const handler = jest.fn();
      rec.onresult = handler;

      rec.triggerResult('Hello world');

      expect(handler).toHaveBeenCalledTimes(1);
      const event = handler.mock.calls[0][0];
      expect(event.results[0][0].transcript).toBe('Hello world');
      expect(event.results[0][0].confidence).toBe(0.95);
      expect(event.results[0].isFinal).toBe(true);
      expect(event.resultIndex).toBe(0);
    });

    test('triggerResult supports non-final results', () => {
      const rec = createMockSpeechRecognition();
      const handler = jest.fn();
      rec.onresult = handler;

      rec.triggerResult('partial', false);

      expect(handler.mock.calls[0][0].results[0].isFinal).toBe(false);
    });

    test('triggerError passes error strings and Error objects', () => {
      const rec = createMockSpeechRecognition();
      const handler = jest.fn();
      rec.onerror = handler;

      rec.triggerError('no-speech');
      expect(handler.mock.calls[0][0].error).toBe('no-speech');

      rec.triggerError(new Error('audio-capture'));
      expect(handler.mock.calls[1][0].error).toBe('audio-capture');
      expect(handler.mock.calls[1][0].message).toBe('audio-capture');
    });

    test('triggerEnd and triggerStart fire their handlers', () => {
      const rec = createMockSpeechRecognition();
      const endHandler = jest.fn();
      const startHandler = jest.fn();
      rec.onend = endHandler;
      rec.onstart = startHandler;

      rec.triggerEnd();
      rec.triggerStart();

      expect(endHandler).toHaveBeenCalledTimes(1);
      expect(startHandler).toHaveBeenCalledTimes(1);
    });
  });

  describe('createMockSpeechSynthesis', () => {
    test('creates a mock with spies', () => {
      const synth = createMockSpeechSynthesis();
      expect(jest.isMockFunction(synth.speak)).toBe(true);
      expect(jest.isMockFunction(synth.cancel)).toBe(true);
      expect(jest.isMockFunction(synth.pause)).toBe(true);
      expect(jest.isMockFunction(synth.resume)).toBe(true);
      expect(synth.getVoices()).toEqual([]);
    });

    test('triggerVoicesChanged dispatches a voiceschanged event on window', () => {
      const synth = createMockSpeechSynthesis();
      const handler = jest.fn();
      window.addEventListener('voiceschanged', handler);

      synth.triggerVoicesChanged();

      expect(handler).toHaveBeenCalledTimes(1);
      window.removeEventListener('voiceschanged', handler);
    });
  });

  describe('setupFakeTimers / cleanupFakeTimers', () => {
    test('setupFakeTimers enables fake timers and cleanup restores them', () => {
      const realSetTimeout = setTimeout;
      setupFakeTimers();
      expect(setTimeout).not.toBe(realSetTimeout);

      cleanupFakeTimers();
      expect(setTimeout).toBe(realSetTimeout);
    });
  });

  describe('mockFetchResponse / mockFetchError', () => {
    test('mockFetchResponse resolves ok with json/text of the payload', async () => {
      const mock = mockFetchResponse({ id: 1, name: 'Test' });
      const res = await mock('/api/test');

      expect(mock).toHaveBeenCalledWith('/api/test');
      expect(res.ok).toBe(true);
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({ id: 1, name: 'Test' });
      expect(await res.text()).toBe('{"id":1,"name":"Test"}');
    });

    test('mockFetchResponse supports error responses', async () => {
      const mock = mockFetchResponse({ error: 'bad' }, false);
      const res = await mock('/api/test');

      expect(res.ok).toBe(false);
      expect(res.status).toBe(400);
    });

    test('mockFetchError rejects with the given error', async () => {
      const error = new Error('Network error');
      const mock = mockFetchError(error);

      await expect(mock('/api/test')).rejects.toBe(error);
    });
  });

  describe('createMockEventListeners', () => {
    test('registers listeners and triggers them with events', () => {
      const eventSpies = createMockEventListeners();
      const handler = jest.fn();

      window.addEventListener('mousedown', handler);
      eventSpies.trigger('mousedown');

      expect(handler).toHaveBeenCalledTimes(1);
      expect(handler.mock.calls[0][0]).toBeInstanceOf(Event);
      eventSpies.cleanup();
    });

    test('removeEventListener removes the handler from the registry', () => {
      const eventSpies = createMockEventListeners();
      const handler = jest.fn();

      window.addEventListener('mousedown', handler);
      window.removeEventListener('mousedown', handler);
      eventSpies.trigger('mousedown');

      expect(handler).not.toHaveBeenCalled();
      eventSpies.cleanup();
    });

    test('cleanup restores the real add/removeEventListener', () => {
      const eventSpies = createMockEventListeners();

      eventSpies.cleanup();

      const handler = jest.fn();
      window.addEventListener('custom-test', handler);
      window.dispatchEvent(new Event('custom-test'));
      expect(handler).toHaveBeenCalledTimes(1);
      window.removeEventListener('custom-test', handler);
    });
  });
});
