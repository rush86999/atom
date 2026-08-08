/**
 * RollbackWorkflowModal Component Tests
 *
 * Tests verify the real RollbackWorkflowModal
 * (components/Versioning/RollbackWorkflowModal.tsx):
 * - fetches the target version on open (loading -> preview)
 * - renders version metadata, tags, parent version, checksum
 * - fetch failure surfaces an error alert + toast
 * - rollback requires a reason (no POST without one)
 * - successful rollback POSTs {target_version, rollback_reason}, toasts,
 *   calls onRollbackComplete, closes the dialog and resets the reason
 * - failed rollback toasts an error and stays open
 * - Cancel closes the dialog and resets local state
 *
 * API: GET /api/v1/workflows/:id/versions/:version,
 *      POST /api/v1/workflows/:id/rollback
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { RollbackWorkflowModal } from '../RollbackWorkflowModal';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const versionData = {
  workflow_id: 'wf-1',
  version: '1.2.3',
  version_type: 'patch',
  change_type: 'bugfix',
  created_at: '2026-07-15T10:00:00.000Z',
  created_by: 'alice',
  commit_message: 'Fix timeout in sales pipeline',
  tags: ['stable', 'release-candidate'],
  parent_version: '1.2.2',
  branch_name: 'main',
  checksum: 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6',
  is_active: false,
};

const defaultProps = {
  workflowId: 'wf-1',
  workflowName: 'Sales Pipeline',
  targetVersion: '1.2.3',
  open: true,
  onOpenChange: jest.fn(),
  currentUserId: 'user-1',
  onRollbackComplete: jest.fn(),
};

const mockFetch = () =>
  (global.fetch as jest.Mock).mockImplementation((url: string, init?: RequestInit) => {
    const u = String(url);
    if (u.includes('/versions/1.2.3') && !init?.method) {
      return Promise.resolve({ ok: true, json: async () => versionData });
    }
    if (u.endsWith('/rollback')) {
      return Promise.resolve({ ok: true, json: async () => ({ rollback_version: '1.2.4' }) });
    }
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });

describe('RollbackWorkflowModal', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
    mockFetch();
  });

  it('renders nothing when closed', () => {
    const { container } = render(
      <RollbackWorkflowModal {...defaultProps} open={false} />
    );
    expect(container.innerHTML).toBe('');
  });

  it('shows a loading state while fetching the target version', async () => {
    global.fetch = jest.fn(
      () => new Promise(() => {}) // never resolves
    );
    render(<RollbackWorkflowModal {...defaultProps} />);

    expect(screen.getByText('Loading version details...')).toBeInTheDocument();
    expect(screen.getByText('Rollback Workflow')).toBeInTheDocument();
    expect(screen.getByText('Rollback "Sales Pipeline" to version 1.2.3')).toBeInTheDocument();
  });

  it('fetches the target version and renders its details once loaded', async () => {
    render(<RollbackWorkflowModal {...defaultProps} />);

    expect(await screen.findByText('Fix timeout in sales pipeline')).toBeInTheDocument();
    expect(screen.getByText('v1.2.3')).toBeInTheDocument();
    expect(screen.getByText('bugfix')).toBeInTheDocument();
    expect(screen.getByText('main')).toBeInTheDocument();
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('from v1.2.2')).toBeInTheDocument();
    expect(screen.getByText('stable')).toBeInTheDocument();
    expect(screen.getByText('release-candidate')).toBeInTheDocument();
    // Rollback reason field + warning + info alerts
    expect(screen.getByLabelText(/Rollback Reason/)).toBeInTheDocument();
    expect(screen.getByText('This action cannot be undone')).toBeInTheDocument();
    expect(screen.getByText(/restored to the exact state of version/)).toBeInTheDocument();
  });

  it('shows the error alert and toasts when the version fetch fails', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 404, json: async () => ({}) });
    render(<RollbackWorkflowModal {...defaultProps} />);

    expect(await screen.findByText('Error Loading Version')).toBeInTheDocument();
    expect(screen.getByText('Failed to fetch target version')).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Error', variant: 'error' })
    );
  });

  it('expands the preview with checksum and status via Show Details', async () => {
    render(<RollbackWorkflowModal {...defaultProps} />);
    await screen.findByText('Fix timeout in sales pipeline');

    expect(screen.queryByText('SHA-256')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /show details/i }));

    expect(await screen.findByText('Checksum')).toBeInTheDocument();
    expect(screen.getByText('a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  it('keeps Confirm Rollback disabled until a reason is provided', async () => {
    render(<RollbackWorkflowModal {...defaultProps} />);
    await screen.findByText('Fix timeout in sales pipeline');

    const confirmBtn = screen.getByRole('button', { name: /confirm rollback/i });
    expect(confirmBtn).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Rollback Reason/), {
      target: { value: 'The new release broke auth' },
    });
    expect(confirmBtn).toBeEnabled();
  });

  it('blocks rollback without a reason: no POST is fired', async () => {
    render(<RollbackWorkflowModal {...defaultProps} />);
    await screen.findByText('Fix timeout in sales pipeline');

    fireEvent.click(screen.getByRole('button', { name: /confirm rollback/i }));

    const posts = (global.fetch as jest.Mock).mock.calls.filter(([, init]) => init?.method === 'POST');
    expect(posts).toHaveLength(0);
    expect(mockToast).not.toHaveBeenCalled();
  });

  it('rolls back successfully: POSTs reason, toasts, completes and closes', async () => {
    const onOpenChange = jest.fn();
    const onRollbackComplete = jest.fn();
    render(
      <RollbackWorkflowModal
        {...defaultProps}
        onOpenChange={onOpenChange}
        onRollbackComplete={onRollbackComplete}
      />
    );
    await screen.findByText('Fix timeout in sales pipeline');

    fireEvent.change(screen.getByLabelText(/Rollback Reason/), {
      target: { value: 'Auth regression' },
    });
    fireEvent.click(screen.getByRole('button', { name: /confirm rollback/i }));

    await waitFor(() => {
      expect(onRollbackComplete).toHaveBeenCalledWith('1.2.4');
    });
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Rollback Successful' })
    );

    const posts = (global.fetch as jest.Mock).mock.calls.filter(([, init]) => init?.method === 'POST');
    expect(posts).toHaveLength(1);
    expect(JSON.parse(posts[0][1].body)).toEqual({
      target_version: '1.2.3',
      rollback_reason: 'Auth regression',
    });
  });

  it('shows a loading spinner on the button while the rollback is in flight', async () => {
    let resolveRollback: (value: unknown) => void = () => {};
    (global.fetch as jest.Mock).mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return new Promise((resolve) => {
          resolveRollback = resolve;
        });
      }
      return Promise.resolve({ ok: true, json: async () => versionData });
    });

    render(<RollbackWorkflowModal {...defaultProps} />);
    await screen.findByText('Fix timeout in sales pipeline');

    fireEvent.change(screen.getByLabelText(/Rollback Reason/), {
      target: { value: 'Testing spinner' },
    });
    fireEvent.click(screen.getByRole('button', { name: /confirm rollback/i }));

    expect(await screen.findByText('Rolling Back...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /rolling back/i })).toBeDisabled();

    resolveRollback({ ok: true, json: async () => ({ rollback_version: '1.2.4' }) });
    await waitFor(() => {
      expect(screen.queryByText('Rolling Back...')).not.toBeInTheDocument();
    });
  });

  it('toasts an error and stays open when the rollback POST fails', async () => {
    const onOpenChange = jest.fn();
    (global.fetch as jest.Mock).mockImplementation((url: string, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      }
      return Promise.resolve({ ok: true, json: async () => versionData });
    });

    render(<RollbackWorkflowModal {...defaultProps} onOpenChange={onOpenChange} />);
    await screen.findByText('Fix timeout in sales pipeline');

    fireEvent.change(screen.getByLabelText(/Rollback Reason/), {
      target: { value: 'Will fail' },
    });
    fireEvent.click(screen.getByRole('button', { name: /confirm rollback/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Rollback Failed', variant: 'error' })
      );
    });
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
    expect(screen.getByText('Fix timeout in sales pipeline')).toBeInTheDocument();
  });

  it('cancels: closes the dialog, clears the reason and hides details', async () => {
    const onOpenChange = jest.fn();
    render(<RollbackWorkflowModal {...defaultProps} onOpenChange={onOpenChange} />);
    await screen.findByText('Fix timeout in sales pipeline');

    fireEvent.change(screen.getByLabelText(/Rollback Reason/), {
      target: { value: 'Half-typed reason' },
    });
    fireEvent.click(screen.getByRole('button', { name: /show details/i }));
    await screen.findByText('Checksum');

    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(screen.getByLabelText(/Rollback Reason/)).toHaveValue('');
    expect(screen.queryByText('Checksum')).not.toBeInTheDocument();
  });
});
