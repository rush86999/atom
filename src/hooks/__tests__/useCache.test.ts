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

  it('should apply optimistic update on refetch', async () => {
    const initialData = { id: 1, name: 'Test' };
    const optimisticData = { id: 1, name: 'Optimistic Test' };
    const finalData = { id: 1, name: 'Final Test' };
    let fetcherResult = initialData;
    const fetcher = jest.fn().mockImplementation(() => Promise.resolve(fetcherResult));

    const { result } = renderHook(() =>
      useCache('test-key', fetcher, { optimisticUpdate: () => optimisticData })
    );

    await waitFor(() => {
      expect(result.current.data).toEqual(initialData);
    });

    fetcherResult = finalData;
    act(() => {
      result.current.refetch();
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(finalData);
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('should revert optimistic update on error', async () => {
    const initialData = { id: 1, name: 'Test' };
    const optimisticData = { id: 1, name: 'Optimistic Test' };
    let shouldFail = false;
    const fetcher = jest.fn().mockImplementation(() => {
      if (shouldFail) {
        return Promise.reject(new Error('Fetch failed'));
      }
      return Promise.resolve(initialData);
    });

    const { result } = renderHook(() =>
      useCache('test-key', fetcher, { optimisticUpdate: () => optimisticData })
    );

    await waitFor(() => {
      expect(result.current.data).toEqual(initialData);
    });

    shouldFail = true;
    act(() => {
      result.current.refetch();
    });

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
      expect(result.current.data).toEqual(initialData); // Reverted
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(initialData);
    });

    act(() => {
      result.current.refetch();
    });

    await waitFor(() => {
      expect(result.current.error).toBeTruthy();
      expect(result.current.data).toEqual(initialData); // Reverted
    });
  });

  it('should mutate with optimistic update', async () => {
    const initialData = { count: 0 };
    const optimisticData = { count: 1 };
    const finalData = { count: 2 };
    let fetcherResult = initialData;
    const fetcher = jest.fn().mockImplementation(() => Promise.resolve(fetcherResult));

    const { result } = renderHook(() =>
      useCache('test-key', fetcher)
    );

    await waitFor(() => {
      expect(result.current.data).toEqual(initialData);
    });

    // Change the fetcher result for the next call
    fetcherResult = finalData;
    act(() => {
      result.current.mutate(() => optimisticData);
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(finalData);
    });

    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it('should revert mutation on error', async () => {
    const initialData = { count: 0 };
    const optimisticData = { count: 1 };
    let shouldFail = false;
    const fetcher = jest.fn().mockImplementation(() => {
      if (shouldFail) {
        return Promise.reject(new Error('Mutation failed'));
      }
      return Promise.resolve(initialData);
    });

    const { result } = renderHook(() =>
      useCache('test-key', fetcher)
    );

    await waitFor(() => {
      expect(result.current.data).toEqual(initialData);
    });

    shouldFail = true;
    await act(async () => {
      try {
        await result.current.mutate(() => optimisticData);
      } catch (error) {
        // Error is expected
      }
    });

    expect(result.current.error).toBeTruthy();
    expect(result.current.data).toEqual(initialData); // Reverted
  });
});
