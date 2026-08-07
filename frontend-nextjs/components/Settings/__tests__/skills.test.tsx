/**
 * Settings skill-module tests.
 *
 * These modules were previously imported from the non-existent `src/skills/`
 * directory (unresolvable import — the production bug). Re-created at
 * components/Settings/skills/ against the real credentials API surface; these
 * tests exercise the actual implementations against a mocked fetch.
 */
import {
  getGDriveConnectionStatus,
  disconnectGDrive,
} from '../skills/gdriveSkills';
import {
  getDropboxConnectionStatus,
  disconnectDropbox,
} from '../skills/dropboxSkills';
import {
  getShopifyConnectionStatus,
  disconnectShopify,
} from '../skills/shopifySkills';

describe('gdriveSkills', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('reports connected when the credentials API returns isConnected', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ isConnected: true, value: 'secret' }),
    });
    const result = await getGDriveConnectionStatus('u1');
    expect(result.ok).toBe(true);
    expect(result.data).toEqual({ isConnected: true });
    expect(global.fetch).toHaveBeenCalledWith('/api/integrations/credentials?service=gdrive');
  });

  it('reports disconnected with the API message when not connected', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ isConnected: false, message: 'No credential found' }),
    });
    const result = await getGDriveConnectionStatus('u1');
    expect(result.ok).toBe(true);
    expect(result.data).toEqual({ isConnected: false, reason: 'No credential found' });
  });

  it('returns an error result when the fetch rejects', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('offline'));
    const result = await getGDriveConnectionStatus('u1');
    expect(result.ok).toBe(false);
    expect(result.error?.message).toBe('offline');
  });

  it('disconnects by clearing the stored credential', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    const result = await disconnectGDrive('u1');
    expect(result.ok).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/integrations/credentials',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ service: 'gdrive', secret: '' }),
      })
    );
  });

  it('returns an error when the disconnect request fails', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });
    const result = await disconnectGDrive('u1');
    expect(result.ok).toBe(false);
    expect(result.error?.message).toBe('Failed to disconnect');
  });
});

describe('dropboxSkills', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('reports connected status', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ isConnected: true }),
    });
    const result = await getDropboxConnectionStatus('u1');
    expect(result).toEqual({ ok: true, data: { isConnected: true } });
  });

  it('reports disconnected when the API says so', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ isConnected: false, message: 'Not connected' }),
    });
    const result = await getDropboxConnectionStatus('u1');
    expect(result.data).toEqual({ isConnected: false, reason: 'Not connected' });
  });

  it('disconnects by clearing the stored credential', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    const result = await disconnectDropbox('u1');
    expect(result.ok).toBe(true);
    expect(JSON.parse((global.fetch as jest.Mock).mock.calls[0][1].body)).toEqual({
      service: 'dropbox',
      secret: '',
    });
  });
});

describe('shopifySkills', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('reports connected with the stored shop URL', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ isConnected: true, value: 'my-store.myshopify.com' }),
    });
    const result = await getShopifyConnectionStatus('u1');
    expect(result.ok).toBe(true);
    expect(result.data).toEqual({ isConnected: true, shopUrl: 'my-store.myshopify.com' });
  });

  it('reports disconnected when the API says so', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ isConnected: false, message: 'Not connected' }),
    });
    const result = await getShopifyConnectionStatus('u1');
    expect(result.data).toEqual({ isConnected: false, reason: 'Not connected' });
  });

  it('disconnects by clearing the stored credential', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    const result = await disconnectShopify('u1');
    expect(result.ok).toBe(true);
    expect(JSON.parse((global.fetch as jest.Mock).mock.calls[0][1].body)).toEqual({
      service: 'shopify',
      secret: '',
    });
  });
});
