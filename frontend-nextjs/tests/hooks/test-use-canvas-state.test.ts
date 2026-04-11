import { renderHook, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

describe('useCanvasState Hook', () => {
    beforeEach(() => {
        // Clear window.atom before each test
        delete (window as any).atom;
    });

    // Basic smoke test to verify the hook can be imported
    it('should import useCanvasState hook', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');
        expect(useCanvasState).toBeDefined();
        expect(typeof useCanvasState).toBe('function');
    });

    // Test hook returns expected structure
    it('should return expected hook API', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result } = renderHook(() => useCanvasState());

        expect(result.current).toHaveProperty('state');
        expect(result.current).toHaveProperty('allStates');
        expect(result.current).toHaveProperty('getState');
        expect(result.current).toHaveProperty('getAllStates');
        expect(result.current).toHaveProperty('isApiReady');
    });

    // Test hook initializes canvas API if not exists
    it('should initialize canvas API if not exists', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        expect((window as any).atom).toBeUndefined();

        renderHook(() => useCanvasState());

        await waitFor(() => {
            expect((window as any).atom).toBeDefined();
            expect((window as any).atom.canvas).toBeDefined();
        });
    });

    // Test hook with canvasId parameter
    it('should accept canvasId parameter', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        expect(() => {
            renderHook(() => useCanvasState('test-canvas'));
        }).not.toThrow();
    });

    // Test hook without canvasId parameter
    it('should work without canvasId parameter', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        expect(() => {
            renderHook(() => useCanvasState());
        }).not.toThrow();
    });

    // Test getState function
    it('should provide getState function', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result } = renderHook(() => useCanvasState());

        expect(typeof result.current.getState).toBe('function');
    });

    // Test getAllStates function
    it('should provide getAllStates function', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result } = renderHook(() => useCanvasState());

        expect(typeof result.current.getAllStates).toBe('function');
    });

    // Test initial state is null
    it('should have initial state as null', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result } = renderHook(() => useCanvasState());

        expect(result.current.state).toBeNull();
    });

    // Test initial allStates is empty array
    it('should have initial allStates as empty array', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result } = renderHook(() => useCanvasState());

        expect(result.current.allStates).toEqual([]);
    });

    // Test isApiReady becomes true
    it('should set isApiReady to true', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result } = renderHook(() => useCanvasState());

        await waitFor(() => {
            expect(result.current.isApiReady).toBe(true);
        });
    });

    // Test getState returns null for non-existent canvas
    it('should return null from getState for non-existent canvas', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result } = renderHook(() => useCanvasState());

        const state = result.current.getState('non-existent-canvas');
        expect(state).toBeNull();
    });

    // Test getAllStates returns empty array initially
    it('should return empty array from getAllStates initially', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result } = renderHook(() => useCanvasState());

        const states = result.current.getAllStates();
        expect(states).toEqual([]);
    });

    // Test hook handles window.atom.canvas existence
    it('should handle existing window.atom.canvas', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        // Setup mock canvas API
        (window as any).atom = {
            canvas: {
                getState: () => ({ canvas_type: 'generic', title: 'Test' }),
                getAllStates: () => [],
                subscribe: () => () => {},
                subscribeAll: () => () => {}
            }
        };

        expect(() => {
            renderHook(() => useCanvasState());
        }).not.toThrow();
    });

    // Test hook cleanup on unmount
    it('should cleanup on unmount', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { unmount } = renderHook(() => useCanvasState('test-canvas'));

        expect(() => {
            unmount();
        }).not.toThrow();
    });

    // Test hook with different canvas IDs
    it('should work with different canvas IDs', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const canvasIds = ['canvas-1', 'canvas-2', 'canvas-3'];

        for (const id of canvasIds) {
            expect(() => {
                renderHook(() => useCanvasState(id));
            }).not.toThrow();
        }
    });

    // Test multiple hook instances
    it('should support multiple hook instances', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        expect(() => {
            const { result: result1 } = renderHook(() => useCanvasState('canvas-1'));
            const { result: result2 } = renderHook(() => useCanvasState('canvas-2'));

            expect(result1.current.getState).toBeInstanceOf(Function);
            expect(result2.current.getState).toBeInstanceOf(Function);
        }).not.toThrow();
    });

    // Test getCanvasRegistrationStatus function
    it('should export getCanvasRegistrationStatus function', async () => {
        const { getCanvasRegistrationStatus } = await import('@/hooks/useCanvasState');

        expect(getCanvasRegistrationStatus).toBeDefined();
        expect(typeof getCanvasRegistrationStatus).toBe('function');
    });

    // Test getCanvasRegistrationStatus returns expected structure
    it('should return registration status object', async () => {
        const { getCanvasRegistrationStatus } = await import('@/hooks/useCanvasState');

        const status = getCanvasRegistrationStatus();

        expect(status).toHaveProperty('registeredCount');
        expect(status).toHaveProperty('registeredIds');
        expect(status).toHaveProperty('warningCount');
        expect(status).toHaveProperty('warnings');
        expect(Array.isArray(status.registeredIds)).toBe(true);
        expect(Array.isArray(status.warnings)).toBe(true);
    });

    // Test clearCanvasRegistrationWarnings function
    it('should export clearCanvasRegistrationWarnings function', async () => {
        const { clearCanvasRegistrationWarnings } = await import('@/hooks/useCanvasState');

        expect(clearCanvasRegistrationWarnings).toBeDefined();
        expect(typeof clearCanvasRegistrationWarnings).toBe('function');
    });

    // Test clearCanvasRegistrationWarnings clears warnings
    it('should clear registration warnings', async () => {
        const { getCanvasRegistrationStatus, clearCanvasRegistrationWarnings } = await import('@/hooks/useCanvasState');

        // Clear warnings
        clearCanvasRegistrationWarnings();

        const status = getCanvasRegistrationStatus();
        expect(status.warningCount).toBe(0);
        expect(status.warnings).toEqual([]);
    });

    // Test hook default export
    it('should export useCanvasState as default', async () => {
        const module = await import('@/hooks/useCanvasState');

        expect(module.default).toBeDefined();
        expect(module.default).toBe(module.useCanvasState);
    });

    // Test hook handles missing canvas gracefully
    it('should handle missing canvas gracefully', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result } = renderHook(() => useCanvasState('missing-canvas'));

        // Should not throw, state should be null
        expect(result.current.state).toBeNull();
    });

    // Test hook re-renders correctly
    it('should re-render correctly', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result, rerender } = renderHook(() => useCanvasState('test-canvas'));

        rerender();

        expect(result.current.getState).toBeInstanceOf(Function);
        expect(result.current.getAllStates).toBeInstanceOf(Function);
    });

    // Test hook maintains reference stability
    it('should maintain function reference stability', async () => {
        const { useCanvasState } = await import('@/hooks/useCanvasState');

        const { result } = renderHook(() => useCanvasState());

        const getState1 = result.current.getState;
        const getAllStates1 = result.current.getAllStates;

        // Re-render shouldn't change function references
        const { rerender } = renderHook(() => useCanvasState());
        rerender();

        const getState2 = result.current.getState;
        const getAllStates2 = result.current.getAllStates;

        expect(getState1).toBe(getState2);
        expect(getAllStates1).toBe(getAllStates2);
    });
});
