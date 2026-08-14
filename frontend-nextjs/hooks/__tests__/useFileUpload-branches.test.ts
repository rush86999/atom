/**
 * useFileUpload — supplemental tests for the progress-clamp branches
 * (BUG-053: total=0 must clamp to 100, never >100).
 */

import { renderHook, act } from '@testing-library/react';

const mockApiPost = jest.fn();

jest.mock('axios', () => ({
  create: jest.fn(() => ({
    post: (...args: any[]) => mockApiPost(...args),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  })),
}));

import { useFileUpload } from '../useFileUpload';

describe('useFileUpload progress clamping', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  const invokeUpload = async (progressEvent: any) => {
    mockApiPost.mockImplementation((_url: string, _data: any, config: any) => {
      config.onUploadProgress(progressEvent);
      return Promise.resolve({ data: { id: 'doc-1' } });
    });
    const { result } = renderHook(() => useFileUpload());
    const file = new File(['data'], 'file.txt', { type: 'text/plain' });
    let uploaded: any;
    await act(async () => {
      uploaded = await result.current.uploadFile(file);
    });
    return { result, uploaded };
  };

  test('clamps progress to 100 when total is 0 (streaming uploads)', async () => {
    const { result } = await invokeUpload({ loaded: 5000, total: 0 });
    expect(result.current.progress).toBe(100);
  });

  test('reports the exact percentage when total is known', async () => {
    const { result } = await invokeUpload({ loaded: 50, total: 200 });
    expect(result.current.progress).toBe(25);
  });

  test('clamps progress to 100 when the computed value exceeds 100', async () => {
    const { result } = await invokeUpload({ loaded: 300, total: 100 });
    expect(result.current.progress).toBe(100);
  });

  test('returns the uploaded document and resets isUploading', async () => {
    const { result, uploaded } = await invokeUpload({ loaded: 10, total: 10 });
    expect(uploaded).toEqual({ id: 'doc-1' });
    expect(result.current.isUploading).toBe(false);
  });

  test('re-throws upload errors and resets isUploading', async () => {
    mockApiPost.mockRejectedValue(new Error('network'));
    const { result } = renderHook(() => useFileUpload());
    const file = new File(['data'], 'file.txt');
    await act(async () => {
      await expect(result.current.uploadFile(file)).rejects.toThrow('network');
    });
    expect(result.current.isUploading).toBe(false);
  });
});
