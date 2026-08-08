/**
 * QuickActions component tests.
 *
 * Covers the REAL QuickActions (components/admin/jit-verification/QuickActions.tsx):
 * - Start Worker shown when stopped; Stop Worker shown when running
 * - Start/Stop call the API, toast, and invoke onUpdate on success
 * - Error paths toast destructively without onUpdate
 * - Clear Cache confirmation dialog (now reachable — was unreachable before the
 *   controlled-open fix) → clearCache() + onUpdate
 * - Warm Cache calls warmCache(100) and toasts with the API response
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { QuickActions } from '../QuickActions';
import { jitVerificationAPI } from '@/lib/api-admin';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

jest.mock('@/lib/api-admin', () => ({
  jitVerificationAPI: {
    startWorker: jest.fn(),
    stopWorker: jest.fn(),
    clearCache: jest.fn(),
    warmCache: jest.fn(),
  },
}));

const startWorkerMock = jitVerificationAPI.startWorker as jest.Mock;
const stopWorkerMock = jitVerificationAPI.stopWorker as jest.Mock;
const clearCacheMock = jitVerificationAPI.clearCache as jest.Mock;
const warmCacheMock = jitVerificationAPI.warmCache as jest.Mock;

describe('QuickActions', () => {
  const onUpdate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    startWorkerMock.mockResolvedValue({ data: { status: 'ok' } });
    stopWorkerMock.mockResolvedValue({ data: { status: 'ok' } });
    clearCacheMock.mockResolvedValue({ data: { status: 'ok' } });
    warmCacheMock.mockResolvedValue({
      data: { citations_verified: 5, duration_seconds: 1.25 },
    });
  });

  it('shows Start Worker when the worker is stopped', () => {
    render(<QuickActions isWorkerRunning={false} onUpdate={onUpdate} />);

    expect(screen.getByRole('button', { name: /Start Worker/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Stop Worker/ })).not.toBeInTheDocument();
  });

  it('shows Stop Worker when the worker is running', () => {
    render(<QuickActions isWorkerRunning={true} onUpdate={onUpdate} />);

    expect(screen.getByRole('button', { name: /Stop Worker/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Start Worker/ })).not.toBeInTheDocument();
  });

  it('starts the worker, toasts, and calls onUpdate', async () => {
    render(<QuickActions isWorkerRunning={false} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /Start Worker/ }));

    await waitFor(() => {
      expect(startWorkerMock).toHaveBeenCalled();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Worker started' })
    );
    expect(onUpdate).toHaveBeenCalled();
  });

  it('stops the worker, toasts, and calls onUpdate', async () => {
    render(<QuickActions isWorkerRunning={true} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /Stop Worker/ }));

    await waitFor(() => {
      expect(stopWorkerMock).toHaveBeenCalled();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Worker stopped' })
    );
    expect(onUpdate).toHaveBeenCalled();
  });

  it('toasts an error and skips onUpdate when starting the worker fails', async () => {
    startWorkerMock.mockRejectedValue({ userMessage: 'cannot start' });
    render(<QuickActions isWorkerRunning={false} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /Start Worker/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Failed to start worker', description: 'cannot start', variant: 'destructive' })
      );
    });
    expect(onUpdate).not.toHaveBeenCalled();
  });

  it('opens the clear-cache confirmation dialog and clears on confirm', async () => {
    render(<QuickActions isWorkerRunning={false} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /Clear Cache/ }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Clear JIT Verification Cache?')).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Clear Cache' }));

    await waitFor(() => {
      expect(clearCacheMock).toHaveBeenCalled();
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Cache cleared' })
    );
    expect(onUpdate).toHaveBeenCalled();
  });

  it('cancelling the clear-cache dialog never calls the API', () => {
    render(<QuickActions isWorkerRunning={false} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /Clear Cache/ }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancel' }));

    expect(clearCacheMock).not.toHaveBeenCalled();
  });

  it('warms the cache with a limit of 100 and toasts the result', async () => {
    render(<QuickActions isWorkerRunning={false} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /Warm Cache/ }));

    await waitFor(() => {
      expect(warmCacheMock).toHaveBeenCalledWith(100);
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Cache warmed', description: 'Warmed 5 citations in 1.25s' })
    );
    expect(onUpdate).toHaveBeenCalled();
  });

  it('toasts an error when warming the cache fails', async () => {
    warmCacheMock.mockRejectedValue({ userMessage: 'warm failed' });
    render(<QuickActions isWorkerRunning={false} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /Warm Cache/ }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Failed to warm cache', description: 'warm failed', variant: 'destructive' })
      );
    });
    expect(onUpdate).not.toHaveBeenCalled();
  });
});
