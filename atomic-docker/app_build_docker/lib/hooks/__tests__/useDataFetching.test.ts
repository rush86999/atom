import { renderHook, act } from '@testing-library/react';
import { useDataFetching } from '../useDataFetching';

// Mock the global fetch function before each test
beforeEach(() => {
  global.fetch = jest.fn();
});

// Restore the original fetch function after all tests have run
afterEach(() => {
  jest.restoreAllMocks();
});

describe('useDataFetching', () => {
  it('should initialize with correct default states', () => {
    const { result } = renderHook(() => useDataFetching());

    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should handle successful data fetching correctly', async () => {
    const mockData = { message: 'Success' };
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockData),
    });

    const { result } = renderHook(() => useDataFetching());

    // Use `act` to wrap the state update
    await act(async () => {
      await result.current.fetchData('/api/test');
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.data).toEqual(mockData);
    expect(result.current.error).toBeNull();
  });

  it('should handle API errors (non-2xx responses)', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      statusText: 'Not Found',
    });

    const { result } = renderHook(() => useDataFetching());

    await act(async () => {
      await result.current.fetchData('/api/non-existent');
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe('API call failed: Not Found');
  });

  it('should handle network errors or fetch promise rejections', async () => {
    const mockError = new Error('Network request failed');
    (global.fetch as jest.Mock).mockRejectedValue(mockError);

    const { result } = renderHook(() => useDataFetching());

    await act(async () => {
      await result.current.fetchData('/api/error');
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toEqual(mockError);
  });
});
