/**
 * lib/websocket-client tests — mock client connect/subscribe/on/disconnect.
 */

import { WebSocketClient, getWebSocketClient, WebSocketMessage } from '../websocket-client';

describe('lib/websocket-client', () => {
  beforeEach(() => {
    jest.spyOn(console, 'log').mockImplementation(() => {});
  });

  it('connects and resolves', async () => {
    const client = new WebSocketClient({ url: 'ws://x' });
    await expect(client.connect()).resolves.toBeUndefined();
  });

  it('subscribes to a channel', () => {
    const client = new WebSocketClient({});
    expect(() => client.subscribe('workspace:default')).not.toThrow();
  });

  it('registers and invokes listeners, and returns an unsubscribe function', () => {
    const client = new WebSocketClient({});
    const listener = jest.fn();
    const msg: WebSocketMessage = { type: 'agent_step', timestamp: 't' };
    // Second registration for the same event exercises the existing-array path.
    const unsubscribe = client.on('message', listener);
    client.on('message', jest.fn());
    (client as any).listeners['message'].forEach((fn: Function) => fn(msg));
    expect(listener).toHaveBeenCalledWith(msg);

    unsubscribe();
    expect((client as any).listeners['message']).toHaveLength(1);
  });

  it('disconnects', () => {
    const client = new WebSocketClient({});
    expect(() => client.disconnect()).not.toThrow();
  });

  it('getWebSocketClient returns a configured client', () => {
    const client = getWebSocketClient({ url: 'ws://y' });
    expect(client).toBeInstanceOf(WebSocketClient);
  });
});
