/**
 * Runtime Settings API client tests (lib/runtime-settings-api.ts)
 *
 * Mocks apiClient.fetch and asserts the URL/method/body contract for
 * the /api/v1/admin/settings/* admin surface.
 */

const mockFetch = jest.fn();

jest.mock('../../api-client', () => ({
  __esModule: true,
  apiClient: {
    fetch: (...args: unknown[]) => mockFetch(...args),
  },
}));

import {
  getSettings,
  getSettingCategories,
  updateSetting,
  resetSetting,
  getSettingChanges,
} from '../../runtime-settings-api';

function jsonResponse(body: unknown, ok = true, status = 200) {
  return { ok, status, json: async () => body };
}

beforeEach(() => mockFetch.mockReset());

describe('runtime-settings-api reads', () => {
  test('getSettings hits catalog endpoint and unwraps data', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        data: {
          settings: [
            {
              key: 'ATOM_SELF_CONSISTENCY',
              type: 'bool',
              default: false,
              category: 'Hallucination Mitigation',
              description: 'N-sample majority vote master switch',
              secret: false,
              editable: true,
              value: true,
              source: 'db',
            },
          ],
          categories: ['Hallucination Mitigation'],
        },
      })
    );

    const out = await getSettings();
    expect(out.settings[0].key).toBe('ATOM_SELF_CONSISTENCY');
    expect(out.settings[0].source).toBe('db');
    expect(mockFetch.mock.calls[0][0]).toBe('/api/v1/admin/settings');
  });

  test('getSettingCategories returns list + count', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ success: true, data: { categories: ['A', 'B'], count: 150 } })
    );
    const out = await getSettingCategories();
    expect(out.count).toBe(150);
    expect(mockFetch.mock.calls[0][0]).toBe('/api/v1/admin/settings/categories');
  });

  test('getSettingChanges forwards limit + key filters', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ success: true, data: { changes: [] } }));
    await getSettingChanges({ limit: 10, settingKey: 'ATOM_MOA_SAMPLES' });
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain('/api/v1/admin/settings/audit');
    expect(url).toContain('limit=10');
    expect(url).toContain('setting_key=ATOM_MOA_SAMPLES');
  });
});

describe('runtime-settings-api mutations', () => {
  test('updateSetting PUTs JSON body with encoded key', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        message: 'updated',
        data: { key: 'ATOM_MOA_SAMPLES', value: 5, source: 'db' },
      })
    );

    const out = await updateSetting('ATOM_MOA_SAMPLES', 5);

    expect(out.data.source).toBe('db');
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/v1/admin/settings/ATOM_MOA_SAMPLES');
    expect((init as RequestInit).method).toBe('PUT');
    expect((init as RequestInit).body).toBe(JSON.stringify({ value: 5 }));
  });

  test('updateSetting surfaces backend detail on validation error', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ detail: 'Invalid value for ATOM_MOA_SAMPLES (expected int)' }, false, 400)
    );
    await expect(updateSetting('ATOM_MOA_SAMPLES', 'nope')).rejects.toThrow(
      'Invalid value for ATOM_MOA_SAMPLES'
    );
  });

  test('resetSetting DELETEs the override', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({
        success: true,
        message: 'reset',
        data: { key: 'X', value: null, source: 'default' },
      })
    );
    const out = await resetSetting('X');
    expect(out.data.source).toBe('default');
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe('/api/v1/admin/settings/X');
    expect((init as RequestInit).method).toBe('DELETE');
  });

  test('errors surface with status when no detail', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}, false, 403));
    await expect(getSettings()).rejects.toThrow('403');
  });
});
