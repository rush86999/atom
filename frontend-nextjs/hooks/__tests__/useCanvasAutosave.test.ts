/**
 * useCanvasAutosave — unit tests.
 *
 * Covers the autosave contract used by CanvasPanel / CanvasHost:
 * - idle debounce: repeated schedule() calls collapse into one save at the
 *   end of the burst, invoking the LATEST save closure
 * - flush(): immediate save that cancels the pending timer; no-op when
 *   clean; force:true always saves (manual Save button semantics)
 * - reset(): drops pending state without saving (new payload / close)
 * - failure: save() resolving false or throwing retries up to maxRetries,
 *   then surfaces "error" (a later edit re-arms autosave)
 * - unmount with pending edits fires one best-effort final save
 */

import { renderHook, act } from '@testing-library/react';
import useCanvasAutosave from '@/hooks/useCanvasAutosave';

const DELAY = 3000;

function setup(save: jest.Mock, opts?: { delayMs?: number; enabled?: boolean; maxRetries?: number }) {
    return renderHook(
        ({ saveFn, ...rest }) => useCanvasAutosave({ save: saveFn, delayMs: DELAY, ...rest }),
        { initialProps: { saveFn: save, ...(opts ?? {}) } }
    );
}

beforeEach(() => {
    jest.useFakeTimers();
});

afterEach(() => {
    jest.useRealTimers();
});

describe('useCanvasAutosave', () => {
    it('saves once after the idle delay and reports saved', async () => {
        const save = jest.fn().mockResolvedValue(true);
        const { result } = setup(save);

        act(() => result.current.schedule());
        expect(result.current.status).toBe('pending');
        expect(save).not.toHaveBeenCalled();

        await act(async () => {
            jest.advanceTimersByTime(DELAY);
        });
        expect(save).toHaveBeenCalledTimes(1);
        expect(result.current.status).toBe('saved');
    });

    it('debounces a burst of edits into a single save of the latest state', async () => {
        let latestContent = 'v1';
        const save = jest.fn().mockImplementation(() => Promise.resolve(latestContent));
        const { result, rerender } = setup(save);

        act(() => result.current.schedule());
        // More edits arrive — the timer keeps pushing forward.
        for (let i = 0; i < 5; i++) {
            latestContent = `v${i + 2}`;
            rerender({ saveFn: save });
            act(() => {
                jest.advanceTimersByTime(DELAY - 100);
                result.current.schedule();
            });
        }
        expect(save).not.toHaveBeenCalled();

        await act(async () => {
            jest.advanceTimersByTime(DELAY);
        });
        expect(save).toHaveBeenCalledTimes(1);
        // The hook invoked the freshest closure, not the one captured at
        // the first schedule().
        expect(latestContent).toBe('v6');
    });

    it('flush() saves immediately, cancels the pending timer, and only saves once', async () => {
        const save = jest.fn().mockResolvedValue(true);
        const { result } = setup(save);

        act(() => result.current.schedule());
        await act(async () => {
            await result.current.flush();
        });
        expect(save).toHaveBeenCalledTimes(1);

        await act(async () => {
            jest.advanceTimersByTime(DELAY * 2);
        });
        expect(save).toHaveBeenCalledTimes(1);
        expect(result.current.status).toBe('saved');
    });

    it('flush() is a no-op when there are no pending edits', async () => {
        const save = jest.fn().mockResolvedValue(true);
        const { result } = setup(save);

        await act(async () => {
            await result.current.flush();
        });
        expect(save).not.toHaveBeenCalled();
        expect(result.current.status).toBe('idle');
    });

    it('flush({force:true}) always saves — manual Save button semantics', async () => {
        const save = jest.fn().mockResolvedValue(true);
        const { result } = setup(save);

        await act(async () => {
            await result.current.flush({ force: true });
        });
        expect(save).toHaveBeenCalledTimes(1);
    });

    it('reset() drops pending edits without saving', async () => {
        const save = jest.fn().mockResolvedValue(true);
        const { result } = setup(save);

        act(() => result.current.schedule());
        act(() => result.current.reset());
        expect(result.current.status).toBe('idle');

        await act(async () => {
            jest.advanceTimersByTime(DELAY * 2);
        });
        expect(save).not.toHaveBeenCalled();
    });

    it('retries a failed save up to maxRetries, then reports error', async () => {
        const save = jest.fn().mockResolvedValue(false);
        const { result } = setup(save, { maxRetries: 2 });

        act(() => result.current.schedule());
        // Initial attempt.
        await act(async () => {
            jest.advanceTimersByTime(DELAY);
        });
        expect(save).toHaveBeenCalledTimes(1);
        expect(result.current.status).toBe('pending');
        // Retry 1.
        await act(async () => {
            jest.advanceTimersByTime(DELAY);
        });
        expect(save).toHaveBeenCalledTimes(2);
        // Retry 2 — attempts exhausted.
        await act(async () => {
            jest.advanceTimersByTime(DELAY);
        });
        expect(save).toHaveBeenCalledTimes(3);
        expect(result.current.status).toBe('error');
    });

    it('treats a thrown save error like a failure (retry, then error)', async () => {
        const save = jest.fn().mockRejectedValue(new Error('network down'));
        const { result } = setup(save, { maxRetries: 0 });

        act(() => result.current.schedule());
        await act(async () => {
            jest.advanceTimersByTime(DELAY);
        });
        expect(save).toHaveBeenCalledTimes(1);
        expect(result.current.status).toBe('error');
    });

    it('a later edit re-arms autosave after an error', async () => {
        let fail = true;
        const save = jest.fn().mockImplementation(() => (fail ? Promise.resolve(false) : Promise.resolve(true)));
        const { result } = setup(save, { maxRetries: 0 });

        act(() => result.current.schedule());
        await act(async () => {
            jest.advanceTimersByTime(DELAY);
        });
        expect(result.current.status).toBe('error');

        fail = false;
        act(() => result.current.schedule());
        await act(async () => {
            jest.advanceTimersByTime(DELAY);
        });
        expect(save).toHaveBeenCalledTimes(2);
        expect(result.current.status).toBe('saved');
    });

    it('fires one best-effort final save on unmount when edits are pending', async () => {
        const save = jest.fn().mockResolvedValue(true);
        const { result, unmount } = setup(save);

        act(() => result.current.schedule());
        unmount();

        await act(async () => {
            jest.advanceTimersByTime(DELAY * 2);
        });
        expect(save).toHaveBeenCalledTimes(1);
    });

    it('does not save on unmount when clean', () => {
        const save = jest.fn().mockResolvedValue(true);
        const { unmount } = setup(save);

        unmount();
        expect(save).not.toHaveBeenCalled();
    });

    it('enabled:false disables scheduling but not forced flushes', async () => {
        const save = jest.fn().mockResolvedValue(true);
        const { result } = setup(save, { enabled: false });

        act(() => result.current.schedule());
        await act(async () => {
            jest.advanceTimersByTime(DELAY * 2);
        });
        expect(save).not.toHaveBeenCalled();

        await act(async () => {
            await result.current.flush({ force: true });
        });
        expect(save).toHaveBeenCalledTimes(1);
    });
});
