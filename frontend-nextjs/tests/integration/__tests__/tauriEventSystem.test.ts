/**
 * Tauri Event System Tests
 *
 * Tests for event emit/listen patterns, bidirectional communication,
 * event serialization, and handler lifecycle management.
 *
 * Test Suites:
 * - Emit Tests: Event emission functionality
 * - Listen Tests: Event listener registration and lifecycle
 * - Bidirectional Tests: Two-way event communication
 * - Serialization Tests: Data serialization and edge cases
 *
 * @module tauriEventSystem.test
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import {
  mockEmit,
  mockListen,
  getEventLog,
  clearEventLog,
  cleanupAllListeners,
  getActiveListeners,
  assertEventEmitted,
  getEventsByName,
  waitForEvent,
} from './tauriEvent.mock';

describe('Tauri Event Emit Tests', () => {
  beforeEach(() => {
    clearEventLog();
  });

  afterEach(() => {
    cleanupAllListeners();
  });

  /**
   * Test: Emit simple event with string payload
   * Verifies basic event emission is logged correctly
   */
  it('test_emit_simple_event', async () => {
    await mockEmit('test-event', 'hello world');

    const events = getEventLog();
    expect(events).toHaveLength(1);
    expect(events[0].eventName).toBe('test-event');
    expect(events[0].payload).toBe('hello world');
    expect(events[0].timestamp).toBeGreaterThan(0);
  });

  /**
   * Test: Emit complex object payload
   * Verifies JSON serialization of nested objects
   */
  it('test_emit_complex_object_payload', async () => {
    const complexPayload = {
      nested: {
        level1: {
          level2: {
            value: 42,
            text: 'deep',
          },
        },
      },
      array: [1, 2, 3, 'four'],
      boolean: true,
      null: null,
    };

    await mockEmit('complex-event', complexPayload);

    const events = getEventLog();
    expect(events).toHaveLength(1);
    expect(events[0].payload).toEqual(complexPayload);
  });

  /**
   * Test: Emit includes timestamp
   * Verifies events include timestamp for ordering
   */
  it('test_emit_with_timestamp', async () => {
    const before = Date.now();
    await mockEmit('timestamp-event', { data: 'test' });
    const after = Date.now();

    const events = getEventLog();
    expect(events[0].timestamp).toBeGreaterThanOrEqual(before);
    expect(events[0].timestamp).toBeLessThanOrEqual(after);
  });

  /**
   * Test: Emit to multiple listeners
   * Verifies single event calls all registered handlers
   */
  it('test_emit_multiple_listeners', async () => {
    const handler1Calls: unknown[] = [];
    const handler2Calls: unknown[] = [];

    await mockListen('multi-event', (payload) => {
      handler1Calls.push(payload);
    });

    await mockListen('multi-event', (payload) => {
      handler2Calls.push(payload);
    });

    await mockEmit('multi-event', 'test-payload');

    expect(handler1Calls).toHaveLength(1);
    expect(handler2Calls).toHaveLength(1);
    expect(handler1Calls[0]).toBe('test-payload');
    expect(handler2Calls[0]).toBe('test-payload');
  });

  /**
   * Test: Emit without listeners
   * Verifies emit works without any listeners (no-op behavior)
   */
  it('test_emit_no_listeners', async () => {
    // Should not throw even with no listeners
    await expect(mockEmit('no-listener-event', 'data')).resolves.toBeUndefined();

    const events = getEventLog();
    expect(events).toHaveLength(1);
  });

  /**
   * Test: Emit handles serialization errors gracefully
   * Verifies emit handles circular references or non-serializable data
   */
  it('test_emit_error_handling', async () => {
    // Create object with circular reference
    const circular: any = { name: 'circular' };
    circular.self = circular;

    // Should handle gracefully (JSON.stringify would fail, but mock logs it)
    await mockEmit('circular-event', circular);

    const events = getEventLog();
    // Event is still logged even with circular ref
    expect(events).toHaveLength(1);
    expect(events[0].eventName).toBe('circular-event');
  });
});

describe('Tauri Event Listen Tests', () => {
  beforeEach(() => {
    clearEventLog();
  });

  afterEach(() => {
    cleanupAllListeners();
  });

  /**
   * Test: Listen registers handler
   * Verifies handler is called on emit
   */
  it('test_listen_registers_handler', async () => {
    const calls: unknown[] = [];

    await mockListen('handler-test', (payload) => {
      calls.push(payload);
    });

    await mockEmit('handler-test', 'test-data');

    expect(calls).toHaveLength(1);
    expect(calls[0]).toBe('test-data');
  });

  /**
   * Test: Listen returns unlisten function
   * Verifies unlisten removes handler
   */
  it('test_listen_returns_unlisten', async () => {
    const calls: unknown[] = [];

    const unlisten = await mockListen('unlisten-test', (payload) => {
      calls.push(payload);
    });

    // First emit
    await mockEmit('unlisten-test', 'first');
    expect(calls).toHaveLength(1);

    // Unlisten
    unlisten();

    // Second emit - should not trigger handler
    await mockEmit('unlisten-test', 'second');
    expect(calls).toHaveLength(1); // Still 1
    expect(calls[0]).toBe('first');
  });

  /**
   * Test: Multiple handlers for same event
   * Verifies isolation between different handlers
   */
  it('test_listen_multiple_handlers_same_event', async () => {
    const handler1Data: unknown[] = [];
    const handler2Data: unknown[] = [];
    const handler3Data: unknown[] = [];

    await mockListen('multi-handler', (payload) => {
      handler1Data.push(`h1: ${payload}`);
    });

    await mockListen('multi-handler', (payload) => {
      handler2Data.push(`h2: ${payload}`);
    });

    await mockListen('multi-handler', (payload) => {
      handler3Data.push(`h3: ${payload}`);
    });

    await mockEmit('multi-handler', 'test');

    expect(handler1Data).toHaveLength(1);
    expect(handler2Data).toHaveLength(1);
    expect(handler3Data).toHaveLength(1);
    expect(handler1Data[0]).toBe('h1: test');
    expect(handler2Data[0]).toBe('h2: test');
    expect(handler3Data[0]).toBe('h3: test');
  });

  /**
   * Test: Event filtering
   * Verifies handlers receive correct event data only
   */
  it('test_listen_event_filtering', async () => {
    const eventA: unknown[] = [];
    const eventB: unknown[] = [];

    await mockListen('event-a', (payload) => {
      eventA.push(payload);
    });

    await mockListen('event-b', (payload) => {
      eventB.push(payload);
    });

    await mockEmit('event-a', 'data-a');
    await mockEmit('event-b', 'data-b');
    await mockEmit('event-a', 'data-a-2');

    expect(eventA).toHaveLength(2);
    expect(eventB).toHaveLength(1);
    expect(eventA).toEqual(['data-a', 'data-a-2']);
    expect(eventB).toEqual(['data-b']);
  });

  /**
   * Test: Listener persists across multiple emits
   * Verifies handler stays registered until unlisten is called
   */
  it('test_listen_persists_across_emits', async () => {
    const calls: unknown[] = [];

    await mockListen('persistent-event', (payload) => {
      calls.push(payload);
    });

    await mockEmit('persistent-event', 'emit1');
    await mockEmit('persistent-event', 'emit2');
    await mockEmit('persistent-event', 'emit3');

    expect(calls).toHaveLength(3);
    expect(calls).toEqual(['emit1', 'emit2', 'emit3']);
  });

  /**
   * Test: Cleanup prevents memory leaks
   * Verifies unlisten removes all handler references
   */
  it('test_listen_cleanup_prevents_memory_leaks', async () => {
    const listenersBefore = getActiveListeners();

    const unlisten1 = await mockListen('cleanup-test', () => {});
    const unlisten2 = await mockListen('cleanup-test', () => {});

    const listenersDuring = getActiveListeners();
    expect(listenersDuring.get('cleanup-test')).toBe(2);

    unlisten1();
    unlisten2();

    const listenersAfter = getActiveListeners();
    expect(listenersAfter.get('cleanup-test')).toBeUndefined();
  });
});

describe('Bidirectional Communication Tests', () => {
  beforeEach(() => {
    clearEventLog();
  });

  afterEach(() => {
    cleanupAllListeners();
  });

  /**
   * Test: Emit then listen roundtrip
   * Verifies emit then listen in same session works correctly
   */
  it('test_emit_listen_roundtrip', async () => {
    const requestData = { action: 'fetch', id: 42 };

    // Emit request
    await mockEmit('request', requestData);

    const events = getEventLog();
    expect(events).toHaveLength(1);
    expect(events[0].payload).toEqual(requestData);

    // Listen for response
    const responseReceived: unknown[] = [];
    await mockListen('response', (payload) => {
      responseReceived.push(payload);
    });

    // Emit response
    await mockEmit('response', { status: 'ok', data: 'result' });

    expect(responseReceived).toHaveLength(1);
    expect(responseReceived[0]).toEqual({ status: 'ok', data: 'result' });
  });

  /**
   * Test: Listener can emit back
   * Verifies handlers can emit events while processing
   */
  it('test_listener_can_emit_response', async () => {
    const responses: unknown[] = [];

    await mockListen('request', async (payload) => {
      // Handler emits response
      await mockEmit('response', { reply: `processed: ${payload}` });
    });

    await mockListen('response', (payload) => {
      responses.push(payload);
    });

    await mockEmit('request', 'test-data');

    // Wait a bit for async emit
    await new Promise((resolve) => setTimeout(resolve, 10));

    expect(responses).toHaveLength(1);
    expect(responses[0]).toEqual({ reply: 'processed: test-data' });
  });

  /**
   * Test: Event ordering preserved
   * Verifies FIFO event delivery order
   */
  it('test_event_ordering_preserved', async () => {
    const receivedOrder: number[] = [];

    await mockListen('ordered-event', (payload) => {
      receivedOrder.push(payload as number);
    });

    // Emit multiple events rapidly
    await mockEmit('ordered-event', 1);
    await mockEmit('ordered-event', 2);
    await mockEmit('ordered-event', 3);
    await mockEmit('ordered-event', 4);
    await mockEmit('ordered-event', 5);

    expect(receivedOrder).toEqual([1, 2, 3, 4, 5]);
  });

  /**
   * Test: Concurrent event handling
   * Verifies simultaneous emit operations work correctly
   */
  it('test_concurrent_events_handling', async () => {
    const received: any[] = [];

    await mockListen('concurrent-event', (payload) => {
      received.push(payload);
    });

    // Emit concurrently
    await Promise.all([
      mockEmit('concurrent-event', { id: 1 }),
      mockEmit('concurrent-event', { id: 2 }),
      mockEmit('concurrent-event', { id: 3 }),
    ]);

    expect(received).toHaveLength(3);
    expect(received.every((r) => r && typeof r.id === 'number')).toBe(true);
  });
});

describe('Event Serialization Tests', () => {
  beforeEach(() => {
    clearEventLog();
  });

  afterEach(() => {
    cleanupAllListeners();
  });

  /**
   * Test: JSON payload serialization
   * Verifies complex objects serialize correctly
   */
  it('test_json_payload_serialization', async () => {
    const complexPayload = {
      string: 'text',
      number: 123.45,
      boolean: true,
      null: null,
      array: [1, 'two', { three: 3 }],
      nested: {
        deep: {
          value: 'nested',
        },
      },
      date: new Date().toISOString(),
    };

    await mockEmit('json-test', complexPayload);

    const events = getEventLog();
    expect(events[0].payload).toEqual(complexPayload);
  });

  /**
   * Test: Binary data handling
   * Verifies ArrayBuffer/binary payload handling
   */
  it('test_binary_data_handling', async () => {
    const binaryData = new Uint8Array([0x00, 0x01, 0x02, 0xff, 0xfe, 0xfd]);
    const arrayBuffer = binaryData.buffer;

    await mockEmit('binary-event', arrayBuffer);

    const events = getEventLog();
    expect(events[0].payload).toEqual(arrayBuffer);
  });

  /**
   * Test: Unicode in events
   * Verifies Unicode strings preserve correctly
   */
  it('test_unicode_in_events', async () => {
    const unicodeStrings = [
      'Hello 世界',
      'Привет мир',
      'مرحبا بالعالم',
      '🎉🚀✨',
      'Ñoño café',
      '日本語',
      'Ελληνικά',
      'עברית',
    ];

    for (const str of unicodeStrings) {
      await mockEmit('unicode-event', str);
    }

    const events = getEventLog();
    expect(events).toHaveLength(unicodeStrings.length);

    events.forEach((event, index) => {
      expect(event.payload).toBe(unicodeStrings[index]);
    });
  });
});

describe('Event Helper Functions Tests', () => {
  beforeEach(() => {
    clearEventLog();
  });

  afterEach(() => {
    cleanupAllListeners();
  });

  /**
   * Test: assertEventEmitted helper
   * Verifies assertion helper works correctly
   */
  it('test_assert_event_emitted', async () => {
    await mockEmit('assert-test', 'data');

    // Should not throw
    assertEventEmitted('assert-test');

    // Should not throw with matching payload
    assertEventEmitted('assert-test', 'data');

    // Should throw with non-matching payload
    expect(() => {
      assertEventEmitted('assert-test', 'wrong-data');
    }).toThrow();
  });

  /**
   * Test: assertEventEmitted throws for missing event
   */
  it('test_assert_event_emitted_throws_for_missing', () => {
    expect(() => {
      assertEventEmitted('non-existent-event');
    }).toThrow('Event "non-existent-event" was not emitted');
  });

  /**
   * Test: getEventsByName filters correctly
   */
  it('test_get_events_by_name', async () => {
    await mockEmit('event-a', 'data-a-1');
    await mockEmit('event-b', 'data-b-1');
    await mockEmit('event-a', 'data-a-2');
    await mockEmit('event-b', 'data-b-2');
    await mockEmit('event-a', 'data-a-3');

    const eventA = getEventsByName('event-a');
    const eventB = getEventsByName('event-b');

    expect(eventA).toHaveLength(3);
    expect(eventB).toHaveLength(2);
    expect(eventA[0].payload).toBe('data-a-1');
    expect(eventB[0].payload).toBe('data-b-1');
  });

  /**
   * Test: waitForEvent resolves on event
   */
  it('test_wait_for_event_resolves', async () => {
    const waitForEventPromise = waitForEvent('wait-test', 1000);

    setTimeout(() => {
      mockEmit('wait-test', 'resolved-data');
    }, 100);

    const result = await waitForEventPromise;
    expect(result).toBe('resolved-data');
  });

  /**
   * Test: waitForEvent times out
   */
  it('test_wait_for_event_times_out', async () => {
    const waitForEventPromise = waitForEvent('timeout-test', 100);

    await expect(waitForEventPromise).rejects.toThrow(
      'Event "timeout-test" not received within 100ms'
    );
  });

  /**
   * Test: getActiveListeners returns correct counts
   */
  it('test_get_active_listeners', async () => {
    const unlisten1 = await mockListen('count-test', () => {});
    const unlisten2 = await mockListen('count-test', () => {});
    await mockListen('other-test', () => {});

    const listeners = getActiveListeners();

    expect(listeners.get('count-test')).toBe(2);
    expect(listeners.get('other-test')).toBe(1);

    unlisten1();

    const listenersAfter = getActiveListeners();
    expect(listenersAfter.get('count-test')).toBe(1);
  });

  /**
   * Test: cleanupAllListeners clears all listeners
   */
  it('test_cleanup_all_listeners', async () => {
    await mockListen('cleanup-a', () => {});
    await mockListen('cleanup-b', () => {});
    await mockListen('cleanup-c', () => {});

    expect(getActiveListeners().size).toBe(3);

    cleanupAllListeners();

    expect(getActiveListeners().size).toBe(0);
  });
});

describe('Memory Leak Prevention Tests', () => {
  beforeEach(() => {
    clearEventLog();
  });

  afterEach(() => {
    cleanupAllListeners();
  });

  /**
   * Test: Unlisten prevents memory leaks
   * Verifies no handler references remain after cleanup
   */
  it('test_unlisten_prevents_memory_leaks', async () => {
    const listeners: any[] = [];

    for (let i = 0; i < 100; i++) {
      const unlisten = await mockListen('memory-leak-test', () => {});
      listeners.push(unlisten);
    }

    expect(getActiveListeners().get('memory-leak-test')).toBe(100);

    // Cleanup all
    listeners.forEach((unlisten) => unlisten());

    expect(getActiveListeners().get('memory-leak-test')).toBeUndefined();
  });

  /**
   * Test: Multiple cleanup cycles
   * Verifies cleanup can be called multiple times safely
   */
  it('test_multiple_cleanup_cycles', async () => {
    await mockListen('cycle-test', () => {});

    expect(getActiveListeners().size).toBe(1);

    cleanupAllListeners();
    expect(getActiveListeners().size).toBe(0);

    cleanupAllListeners(); // Should not throw
    expect(getActiveListeners().size).toBe(0);
  });
});
