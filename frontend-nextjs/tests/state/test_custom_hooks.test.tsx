import { renderHook, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Custom hooks to test
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

function useThrottle<T>(value: T, delay: number): T {
  const [throttledValue, setThrottledValue] = useState(value);
  const lastUpdated = useRef(Date.now());

  useEffect(() => {
    const handler = setTimeout(() => {
      const now = Date.now();
      if (now - lastUpdated.current >= delay) {
        setThrottledValue(value);
        lastUpdated.current = now;
      }
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return throttledValue;
}

function useLocalStorage<T>(key: string, initialValue: T): [T, (value: T) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue;
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      return initialValue;
    }
  });

  const setValue = (value: T) => {
    try {
      setStoredValue(value);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(key, JSON.stringify(value));
      }
    } catch (error) {
      console.error(error);
    }
  };

  return [storedValue, setValue];
}

function useSessionStorage<T>(key: string, initialValue: T): [T, (value: T) => void] {
  const [storedValue, setStoredValue] = useState<T>(() => {
    if (typeof window === 'undefined') return initialValue;
    try {
      const item = window.sessionStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      return initialValue;
    }
  });

  const setValue = (value: T) => {
    try {
      setStoredValue(value);
      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(key, JSON.stringify(value));
      }
    } catch (error) {
      console.error(error);
    }
  };

  return [storedValue, setValue];
}

function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T>();

  useEffect(() => {
    ref.current = value;
  }, [value]);

  return ref.current;
}

function useAsync<T>(
  asyncFunction: () => Promise<T>,
  immediate = true
): {
  status: 'idle' | 'pending' | 'success' | 'error';
  value: T | null;
  error: Error | null;
  execute: () => Promise<void>;
  reset: () => void;
} {
  const [status, setStatus] = useState<'idle' | 'pending' | 'success' | 'error'>('idle');
  const [value, setValue] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(async () => {
    setStatus('pending');
    setValue(null);
    setError(null);

    try {
      const response = await asyncFunction();
      setValue(response);
      setStatus('success');
    } catch (err) {
      setError(err as Error);
      setStatus('error');
    }
  }, [asyncFunction]);

  const reset = useCallback(() => {
    setStatus('idle');
    setValue(null);
    setError(null);
  }, []);

  useEffect(() => {
    if (immediate) {
      execute();
    }
  }, [immediate, execute]);

  return { status, value, error, execute, reset };
}

import { useState, useEffect, useCallback, useRef } from 'react';

describe('Custom Hooks Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('test_use_debounce', () => {
    it('should delay updates by specified delay', () => {
      const { result } = renderHook(() => useDebounce('test', 500));

      expect(result.current).toBe('test');

      act(() => {
        rerenderHook(useDebounce('updated', 500));
      });

      expect(result.current).toBe('test');

      act(() => {
        jest.advanceTimersByTime(500);
      });

      expect(result.current).toBe('updated');
    });

    it('should reset timer on rapid updates', () => {
      const { result, rerender } = renderHook(
        ({ value, delay }) => useDebounce(value, delay),
        { initialProps: { value: 'initial', delay: 500 } as any }
      );

      act(() => {
        rerender({ value: 'update1', delay: 500 });
        jest.advanceTimersByTime(250);
        rerender({ value: 'update2', delay: 500 });
        jest.advanceTimersByTime(250);
      });

      expect(result.current).toBe('initial');

      act(() => {
        jest.advanceTimersByTime(500);
      });

      expect(result.current).toBe('update2');
    });

    it('should handle zero delay', () => {
      const { result, rerender } = renderHook(
        ({ value, delay }) => useDebounce(value, delay),
        { initialProps: { value: 'initial', delay: 0 } as any }
      );

      act(() => {
        rerender({ value: 'updated', delay: 0 });
        jest.advanceTimersByTime(0);
      });

      expect(result.current).toBe('updated');
    });
  });

  describe('test_use_throttle', () => {
    it('should limit update frequency', () => {
      const { result, rerender } = renderHook(
        ({ value, delay }) => useThrottle(value, delay),
        { initialProps: { value: 0, delay: 500 } as any }
      );

      act(() => {
        rerender({ value: 1, delay: 500 });
        rerender({ value: 2, delay: 500 });
        rerender({ value: 3, delay: 500 });
        jest.advanceTimersByTime(500);
      });

      expect(result.current).toBe(1);
    });

    it('should update after throttle period', () => {
      const { result, rerender } = renderHook(
        ({ value, delay }) => useThrottle(value, delay),
        { initialProps: { value: 'initial', delay: 500 } as any }
      );

      act(() => {
        rerender({ value: 'updated', delay: 500 });
        jest.advanceTimersByTime(500);
      });

      expect(result.current).toBe('updated');
    });

    it('should throttle rapid updates', () => {
      const { result, rerender } = renderHook(
        ({ value, delay }) => useThrottle(value, delay),
        { initialProps: { value: 0, delay: 300 } as any }
      );

      act(() => {
        for (let i = 1; i <= 10; i++) {
          rerender({ value: i, delay: 300 });
        }
        jest.advanceTimersByTime(300);
      });

      expect(result.current).toBe(1);

      act(() => {
        jest.advanceTimersByTime(300);
      });

      const updates = Math.floor(10 / (300 / 300));
      expect(result.current).toBeGreaterThan(0);
    });
  });

  describe('test_use_local_storage', () => {
    it('should persist value to localStorage', () => {
      const { result } = renderHook(() => useLocalStorage('test-key', 'default'));

      expect(result.current[0]).toBe('default');

      act(() => {
        const [, setValue] = result.current;
        setValue('stored-value');
      });

      expect(result.current[0]).toBe('stored-value');
      expect(localStorage.getItem('test-key')).toBe(JSON.stringify('stored-value'));
    });

    it('should retrieve initial value from localStorage', () => {
      localStorage.setItem('existing-key', JSON.stringify('existing-value'));

      const { result } = renderHook(() => useLocalStorage('existing-key', 'default'));

      expect(result.current[0]).toBe('existing-value');
    });

    it('should handle complex objects', () => {
      const complexObject = { name: 'Test', count: 42, nested: { value: true } };

      const { result } = renderHook(() => useLocalStorage('object-key', {}));

      act(() => {
        const [, setValue] = result.current;
        setValue(complexObject);
      });

      expect(result.current[0]).toEqual(complexObject);
      expect(JSON.parse(localStorage.getItem('object-key')!)).toEqual(complexObject);
    });

    it('should handle storage errors gracefully', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      const originalSetItem = Storage.prototype.setItem;
      Storage.prototype.setItem = jest.fn(() => {
        throw new Error('Storage quota exceeded');
      });

      const { result } = renderHook(() => useLocalStorage('error-key', 'initial'));

      act(() => {
        const [, setValue] = result.current;
        setValue('error-value');
      });

      expect(result.current[0]).toBe('error-value');

      Storage.prototype.setItem = originalSetItem;
      consoleSpy.mockRestore();
    });
  });

  describe('test_use_session_storage', () => {
    it('should persist value to sessionStorage', () => {
      const { result } = renderHook(() => useSessionStorage('session-key', 'default'));

      expect(result.current[0]).toBe('default');

      act(() => {
        const [, setValue] = result.current;
        setValue('session-value');
      });

      expect(result.current[0]).toBe('session-value');
      expect(sessionStorage.getItem('session-key')).toBe(JSON.stringify('session-value'));
    });

    it('should retrieve initial value from sessionStorage', () => {
      sessionStorage.setItem('existing-session', JSON.stringify('session-value'));

      const { result } = renderHook(() => useSessionStorage('existing-session', 'default'));

      expect(result.current[0]).toBe('session-value');
    });

    it('should handle arrays', () => {
      const testArray = [1, 2, 3, 4, 5];

      const { result } = renderHook(() => useSessionStorage('array-key', []));

      act(() => {
        const [, setValue] = result.current;
        setValue(testArray);
      });

      expect(result.current[0]).toEqual(testArray);
    });
  });

  describe('test_use_previous', () => {
    it('should track previous value', () => {
      const { result, rerender } = renderHook(
        ({ value }) => usePrevious(value),
        { initialProps: { value: 'first' } as any }
      );

      expect(result.current).toBeUndefined();

      act(() => {
        rerender({ value: 'second' });
      });

      expect(result.current).toBe('first');

      act(() => {
        rerender({ value: 'third' });
      });

      expect(result.current).toBe('second');
    });

    it('should handle undefined values', () => {
      const { result, rerender } = renderHook(
        ({ value }) => usePrevious(value),
        { initialProps: { value: undefined } as any }
      );

      expect(result.current).toBeUndefined();

      act(() => {
        rerender({ value: 'defined' });
      });

      expect(result.current).toBeUndefined();
    });

    it('should handle null values', () => {
      const { result, rerender } = renderHook(
        ({ value }) => usePrevious(value),
        { initialProps: { value: null } as any }
      );

      act(() => {
        rerender({ value: 'not-null' });
      });

      expect(result.current).toBe(null);
    });
  });

  describe('test_use_async', () => {
    it('should execute async function immediately', async () => {
      const asyncFn = jest.fn().mockResolvedValue('async-result');

      const { result } = renderHook(() => useAsync(asyncFn, true));

      expect(result.current.status).toBe('pending');

      await waitFor(() => {
        expect(result.current.status).toBe('success');
      });

      expect(result.current.value).toBe('async-result');
      expect(asyncFn).toHaveBeenCalledTimes(1);
    });

    it('should not execute immediately when flag is false', () => {
      const asyncFn = jest.fn().mockResolvedValue('result');

      const { result } = renderHook(() => useAsync(asyncFn, false));

      expect(result.current.status).toBe('idle');
      expect(asyncFn).not.toHaveBeenCalled();
    });

    it('should handle async errors', async () => {
      const asyncError = new Error('Async failed');
      const asyncFn = jest.fn().mockRejectedValue(asyncError);

      const { result } = renderHook(() => useAsync(asyncFn, true));

      await waitFor(() => {
        expect(result.current.status).toBe('error');
      });

      expect(result.current.error).toEqual(asyncError);
    });

    it('should provide execute function', async () => {
      const asyncFn = jest.fn().mockResolvedValue('executed');

      const { result } = renderHook(() => useAsync(asyncFn, false));

      expect(result.current.status).toBe('idle');

      act(() => {
        result.current.execute();
      });

      await waitFor(() => {
        expect(result.current.status).toBe('success');
      });

      expect(result.current.value).toBe('executed');
    });

    it('should reset state', async () => {
      const asyncFn = jest.fn().mockResolvedValue('result');

      const { result } = renderHook(() => useAsync(asyncFn, true));

      await waitFor(() => {
        expect(result.current.status).toBe('success');
      });

      act(() => {
        result.current.reset();
      });

      expect(result.current.status).toBe('idle');
      expect(result.current.value).toBe(null);
      expect(result.current.error).toBe(null);
    });

    it('should handle rapid execute calls', async () => {
      let callCount = 0;
      const asyncFn = jest.fn().mockImplementation(async () => {
        callCount++;
        return `call-${callCount}`;
      });

      const { result } = renderHook(() => useAsync(asyncFn, false));

      act(() => {
        result.current.execute();
        result.current.execute();
        result.current.execute();
      });

      await waitFor(() => {
        expect(result.current.status).toBe('success');
      });

      expect(asyncFn).toHaveBeenCalledTimes(3);
    });
  });
});
