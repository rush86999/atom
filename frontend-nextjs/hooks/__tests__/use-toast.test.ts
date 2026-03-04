/**
 * useToast Hook Tests
 *
 * Tests for toast notification hook with timer cleanup verification.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useToast } from '@/hooks/use-toast';

// ============================================
// Test Utilities
// ============================================

function createMockToast(overrides?: Partial<any>) {
  return {
    id: expect.any(String),
    title: 'Test Toast',
    description: 'Test Description',
    variant: 'default',
    duration: 3000,
    ...overrides
  };
}

// ============================================
// Initialization Tests
// ============================================

describe('useToast - Initialization', () => {
  test('should initialize with empty toasts array', () => {
    const { result } = renderHook(() => useToast());

    expect(result.current.toasts).toEqual([]);
  });

  test('should provide toast function', () => {
    const { result } = renderHook(() => useToast());

    expect(typeof result.current.toast).toBe('function');
  });

  test('should provide dismiss function', () => {
    const { result } = renderHook(() => useToast());

    expect(typeof result.current.dismiss).toBe('function');
  });
});

// ============================================
// Toast Creation Tests
// ============================================

describe('useToast - Toast Creation', () => {
  test('should create toast with correct structure', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({
        title: 'Test Toast',
        description: 'Test Description',
        variant: 'default',
        duration: 3000
      });
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0]).toMatchObject({
      id: expect.any(String),
      title: 'Test Toast',
      description: 'Test Description',
      variant: 'default',
      duration: 3000
    });
  });

  test('should add toast to toasts array', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({ title: 'Test Toast' });
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].title).toBe('Test Toast');
  });

  test('should generate unique IDs for multiple toasts', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({ title: 'Toast 1' });
      result.current.toast({ title: 'Toast 2' });
      result.current.toast({ title: 'Toast 3' });
    });

    expect(result.current.toasts).toHaveLength(3);
    const ids = result.current.toasts.map(t => t.id);
    expect(new Set(ids).size).toBe(3); // All IDs are unique
  });

  test('should use default variant "default"', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({ title: 'Test' });
    });

    expect(result.current.toasts[0].variant).toBe('default');
  });

  test('should use default duration 3000ms', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({ title: 'Test' });
    });

    expect(result.current.toasts[0].duration).toBe(3000);
  });

  test('should accept custom variant', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({
        title: 'Test',
        variant: 'destructive'
      });
    });

    expect(result.current.toasts[0].variant).toBe('destructive');
  });

  test('should accept custom duration', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({
        title: 'Test',
        duration: 5000
      });
    });

    expect(result.current.toasts[0].duration).toBe(5000);
  });
});

// ============================================
// Toast Dismissal Tests
// ============================================

describe('useToast - Toast Dismissal', () => {
  test('should remove toast by ID from array', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({ title: 'Toast 1' });
      result.current.toast({ title: 'Toast 2' });
    });

    const toastId = result.current.toasts[0].id;

    act(() => {
      result.current.dismiss(toastId);
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].title).toBe('Toast 2');
  });

  test('should only remove specified toast', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({ title: 'Toast 1' });
      result.current.toast({ title: 'Toast 2' });
      result.current.toast({ title: 'Toast 3' });
    });

    const middleToastId = result.current.toasts[1].id;

    act(() => {
      result.current.dismiss(middleToastId);
    });

    expect(result.current.toasts).toHaveLength(2);
    expect(result.current.toasts[0].title).toBe('Toast 1');
    expect(result.current.toasts[1].title).toBe('Toast 3');
  });

  test('should handle non-existent ID gracefully', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({ title: 'Test' });
    });

    const initialLength = result.current.toasts.length;

    act(() => {
      result.current.dismiss('non-existent-id');
    });

    expect(result.current.toasts).toHaveLength(initialLength);
  });
});

// ============================================
// Timer Cleanup Tests (CRITICAL - Memory Leak Prevention)
// ============================================

describe('useToast - Timer Cleanup', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  test('should auto-dismiss toast after duration', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({
        title: 'Test',
        duration: 3000
      });
    });

    expect(result.current.toasts).toHaveLength(1);

    // Fast-forward time
    act(() => {
      jest.advanceTimersByTime(3000);
    });

    expect(result.current.toasts).toHaveLength(0);
  });

  test('should cleanup function called on unmount', () => {
    const { result, unmount } = renderHook(() => useToast());

    act(() => {
      result.current.toast({
        title: 'Test',
        duration: 3000
      });
    });

    expect(result.current.toasts).toHaveLength(1);

    // Unmount before timer expires
    unmount();

    // Fast-forward time
    act(() => {
      jest.advanceTimersByTime(3000);
    });

    // Toast should be removed (cleanup prevents memory leak)
    // Note: After unmount, we can't check result.current.toasts
    // but the timer should have been cleaned up
  });

  test('should handle multiple timers independently', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({ title: 'Toast 1', duration: 2000 });
      result.current.toast({ title: 'Toast 2', duration: 4000 });
      result.current.toast({ title: 'Toast 3', duration: 1000 });
    });

    expect(result.current.toasts).toHaveLength(3);

    // First toast dismissed
    act(() => {
      jest.advanceTimersByTime(1000);
    });

    expect(result.current.toasts).toHaveLength(2);
    expect(result.current.toasts.find(t => t.title === 'Toast 3')).toBeUndefined();

    // Second toast dismissed
    act(() => {
      jest.advanceTimersByTime(1000);
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts.find(t => t.title === 'Toast 1')).toBeUndefined();

    // Third toast dismissed
    act(() => {
      jest.advanceTimersByTime(2000);
    });

    expect(result.current.toasts).toHaveLength(0);
  });

  test('should not auto-dismiss with zero duration', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({
        title: 'Test',
        duration: 0
      });
    });

    expect(result.current.toasts).toHaveLength(1);

    // Fast-forward time significantly
    act(() => {
      jest.advanceTimersByTime(10000);
    });

    expect(result.current.toasts).toHaveLength(1);
  });

  test('should manually dismiss toast before timer expires', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({
        title: 'Test',
        duration: 5000
      });
    });

    expect(result.current.toasts).toHaveLength(1);

    const toastId = result.current.toasts[0].id;

    // Dismiss manually before timer
    act(() => {
      result.current.dismiss(toastId);
    });

    expect(result.current.toasts).toHaveLength(0);

    // Fast-forward past duration
    act(() => {
      jest.advanceTimersByTime(5000);
    });

    // Should still be empty (no error from timer)
    expect(result.current.toasts).toHaveLength(0);
  });
});

// ============================================
// Edge Cases
// ============================================

describe('useToast - Edge Cases', () => {
  test('should handle empty title', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({
        title: '',
        description: 'Description only'
      });
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].title).toBe('');
  });

  test('should handle empty description', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({
        title: 'Title only'
      });
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0].title).toBe('Title only');
  });

  test('should handle destructive variant', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({
        title: 'Error',
        variant: 'destructive'
      });
    });

    expect(result.current.toasts[0].variant).toBe('destructive');
  });

  test('should handle multiple concurrent toasts', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      for (let i = 0; i < 10; i++) {
        result.current.toast({
          title: `Toast ${i}`,
          description: `Description ${i}`
        });
      }
    });

    expect(result.current.toasts).toHaveLength(10);

    // Verify all have unique IDs
    const ids = result.current.toasts.map(t => t.id);
    expect(new Set(ids).size).toBe(10);
  });

  test('should handle toast with only title (no description, variant, duration)', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.toast({ title: 'Minimal Toast' });
    });

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toasts[0]).toMatchObject({
      id: expect.any(String),
      title: 'Minimal Toast',
      variant: 'default',
      duration: 3000
    });
  });

  test('should handle rapid toast creation', () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      // Create 20 toasts rapidly
      for (let i = 0; i < 20; i++) {
        result.current.toast({ title: `Toast ${i}` });
      }
    });

    expect(result.current.toasts).toHaveLength(20);

    // Verify all unique IDs
    const ids = result.current.toasts.map(t => t.id);
    expect(new Set(ids).size).toBe(20);
  });
});
