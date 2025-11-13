import { renderHook, act, waitFor } from '@testing-library/react';
import { useCache, cacheUtils } from '../useCache';

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

let mockTime = 0;

describe('useCache', () => {
  beforeEach(() => {
    mockTime = Date.now();
    jest.spyOn(Date, 'now').mockImplementation(() => mockTime);
    jest.clearAllMocks();
    jest.useFakeTimers();
    cacheUtils.clear();
  });

  afterEach(() => {
    jest.restoreAllMocks();
    jest.useRealTimers();
  });

  it('should return cached data when available', async () => {
    const mockData = { id: 1, name: 'Test' };
    const fetcher = jest.fn().mockResolvedValue(mockData);

    const { result } = renderHook(() =>
      useCache('test-key', fetcher, { ttl: 5000 })
    );

    await waitFor(() => {
      expect(result.current.data).toEqual(mockData);
    });

    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('should refetch when cache is stale', async () => {
    const mockData = { id: 1, name: 'Test' };
    const fetcher = jest.fn().mockResolvedValue(mockData);

    const { result } = renderHook(() =>
      useCache('test-key', fetcher, { ttl: 1000 })
    );

    await waitFor(() => {
      expect(result.current.data).toEqual(mockData);
    });

    // Advance time past TTL
    mockTime += 2000;
    act(() => {
      jest.advanceTimersByTime(2000);
    });

    // Refetch
    act(() => {
      result.current.refetch();
    });

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledTimes(2);
    });
  });

  it('should handle errors gracefully', async () => {
    const error = new Error('Fetch failed');
    const fetcher = jest.fn().mockRejectedValue(error);

    const { result } = renderHook(() =>
      useCache('test-key', fetcher)
    );

    await waitFor(() => {
      expect(result.current.error).toBe(error);
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('should invalidate cache', async () => {
    const mockData = { id: 1, name: 'Test' };
    const fetcher = jest.fn().mockResolvedValue(mockData);

    const { result } = renderHook(() =>
      useCache('test-key', fetcher)
    );

    await waitFor(() => {
      expect(result.current.data).toEqual(mockData);
    });

    act(() => {
      result.current.invalidate();
    });

    expect(result.current.data).toBeNull();
  });

  it('should refetch on window focus when enabled', async () => {
    const mockData = { id: 1, name: 'Test' };
    const fetcher = jest.fn().mockResolvedValue(mockData);

    renderHook(() =>
      useCache('test-key', fetcher, { refetchOnWindowFocus: true })
    );

    act(() => {
      window.dispatchEvent(new Event('focus'));
    });

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledTimes(2);
    });
  });

  it('should refetch at specified interval', async () => {
    const mockData = { id: 1, name: 'Test' };
    const fetcher = jest.fn().mockResolvedValue(mockData);

    renderHook(() =>
      useCache('test-key', fetcher, { refetchInterval: 5000 })
    );

    act(() => {
      jest.advanceTimersByTime(5000);
    });

    await waitFor(() => {
      expect(fetcher).toHaveBeenCalledTimes(2);
    }, { timeout: 1000 });
  });
});
