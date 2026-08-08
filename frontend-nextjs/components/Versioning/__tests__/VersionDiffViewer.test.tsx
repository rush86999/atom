/**
 * VersionDiffViewer Component Tests
 *
 * Tests verify the real VersionDiffViewer
 * (components/Versioning/VersionDiffViewer.tsx):
 * - loading state while the diff is fetched
 * - overview tab: impact badge, add/remove/modify counts, structural
 *   changes and impact assessment copy per impact level
 * - steps tab: parametric old/new values + filter behavior
 * - dependencies tab: added/removed deps and the empty state (regression:
 *   the empty state previously crashed with a missing GitBranch import)
 * - metadata tab: old/new values and the empty state
 * - Export downloads a JSON diff; Close fires onClose; fetch failure
 *   renders the error state + toast
 *
 * API: GET /api/v1/workflows/:id/versions/compare?from_version=&to_version=
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { VersionDiffViewer } from '../VersionDiffViewer';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const criticalDiff = {
  workflow_id: 'wf-1',
  from_version: '1.0.0',
  to_version: '1.1.0',
  impact_level: 'critical',
  added_steps_count: 2,
  removed_steps_count: 1,
  modified_steps_count: 3,
  structural_changes: ['Step order changed: send_email moved after validate'],
  dependency_changes: [{ added: ['api-client@2.0.0'], removed: ['api-client@1.0.0'] }],
  parametric_changes: {
    step_send_email: { old: { recipient: 'team@example.com' }, new: { recipient: 'ops@example.com' } },
  },
  metadata_changes: { workflow_name: { old: 'Sales Pipe', new: 'Sales Pipeline' } },
};

const defaultProps = {
  workflowId: 'wf-1',
  fromVersion: '1.0.0',
  toVersion: '1.1.0',
  onClose: jest.fn(),
};

describe('VersionDiffViewer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => criticalDiff,
    });
  });

  it('shows a loading state before the diff resolves', () => {
    global.fetch = jest.fn(() => new Promise(() => {}));
    render(<VersionDiffViewer {...defaultProps} />);

    expect(screen.getByText('Comparing Versions')).toBeInTheDocument();
  });

  it('renders the overview with impact badge, counts and structural changes', async () => {
    render(<VersionDiffViewer {...defaultProps} />);

    expect(await screen.findByText('CRITICAL IMPACT')).toBeInTheDocument();
    expect(screen.getByText('1.0.0 → 1.1.0')).toBeInTheDocument();
    expect(screen.getByText('Step order changed: send_email moved after validate')).toBeInTheDocument();
    expect(screen.getByText(/breaking changes that require immediate attention/i)).toBeInTheDocument();

    // counts: 2 added / 1 removed / 3 modified
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getAllByText('steps')).toHaveLength(3);

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/versions/compare?from_version=1.0.0&to_version=1.1.0')
    );
  });

  it('renders impact-specific assessment copy for low/medium/high impact', async () => {
    for (const [level, copy] of [
      ['low', 'minimal impact on workflow behavior'],
      ['medium', 'may affect some workflow scenarios'],
      ['high', 'significantly affects workflow behavior'],
    ] as const) {
      global.fetch = jest.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ ...criticalDiff, impact_level: level }),
      });
      const { unmount } = render(<VersionDiffViewer {...defaultProps} />);
      expect(await screen.findByText(new RegExp(copy))).toBeInTheDocument();
      expect(screen.getByText(`${level.toUpperCase()} IMPACT`)).toBeInTheDocument();
      unmount();
    }
  });

  it('shows old/new parameter values in the steps tab and filters them', async () => {
    render(<VersionDiffViewer {...defaultProps} />);
    await screen.findByText('CRITICAL IMPACT');

    fireEvent.click(screen.getByRole('button', { name: /steps/i }));

    expect(await screen.findByText('step_send_email')).toBeInTheDocument();
    expect(screen.getByText('Old Value')).toBeInTheDocument();
    expect(screen.getByText('New Value')).toBeInTheDocument();
    // object values render as JSON
    expect(screen.getByText('{"recipient":"ops@example.com"}')).toBeInTheDocument();

    // Filter to "Added Only" hides the modified parameter change
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'added' } });
    expect(screen.queryByText('Old Value')).not.toBeInTheDocument();
  });

  it('shows the no-parameter-changes empty state', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...criticalDiff, parametric_changes: {} }),
    });
    render(<VersionDiffViewer {...defaultProps} />);
    await screen.findByText('CRITICAL IMPACT');

    fireEvent.click(screen.getByRole('button', { name: /steps/i }));

    expect(await screen.findByText('No parameter changes detected')).toBeInTheDocument();
  });

  it('lists added and removed dependencies in the dependencies tab', async () => {
    render(<VersionDiffViewer {...defaultProps} />);
    await screen.findByText('CRITICAL IMPACT');

    fireEvent.click(screen.getByRole('button', { name: /dependencies/i }));

    expect(await screen.findByText('Added Dependencies')).toBeInTheDocument();
    expect(screen.getByText('api-client@2.0.0')).toBeInTheDocument();
    expect(screen.getByText('Removed Dependencies')).toBeInTheDocument();
    expect(screen.getByText('api-client@1.0.0')).toBeInTheDocument();
  });

  it('renders the dependencies empty state without crashing (GitBranch regression)', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...criticalDiff, dependency_changes: [] }),
    });
    render(<VersionDiffViewer {...defaultProps} />);
    await screen.findByText('CRITICAL IMPACT');

    fireEvent.click(screen.getByRole('button', { name: /dependencies/i }));

    expect(await screen.findByText('No dependency changes detected')).toBeInTheDocument();
  });

  it('shows metadata old/new values and the metadata empty state', async () => {
    render(<VersionDiffViewer {...defaultProps} />);
    await screen.findByText('CRITICAL IMPACT');

    fireEvent.click(screen.getByRole('button', { name: /metadata/i }));
    expect(await screen.findByText('workflow_name')).toBeInTheDocument();
    expect(screen.getByText('Sales Pipe')).toBeInTheDocument();
    expect(screen.getByText('Sales Pipeline')).toBeInTheDocument();

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...criticalDiff, metadata_changes: {} }),
    });
    const { unmount } = render(<VersionDiffViewer {...defaultProps} />);
    // wait until BOTH instances rendered their tabs
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /metadata/i })).toHaveLength(2);
    });
    fireEvent.click(screen.getAllByRole('button', { name: /metadata/i })[1]);
    expect(await screen.findByText('No metadata changes detected')).toBeInTheDocument();
    unmount();
  });

  it('exports the diff as a JSON download and toasts', async () => {
    const createObjectURL = jest.fn(() => 'blob:diff-url');
    const revokeObjectURL = jest.fn();
    (URL.createObjectURL as jest.Mock) = createObjectURL;
    (URL.revokeObjectURL as jest.Mock) = revokeObjectURL;

    render(<VersionDiffViewer {...defaultProps} />);
    await screen.findByText('CRITICAL IMPACT');

    fireEvent.click(screen.getByRole('button', { name: /export/i }));

    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:diff-url');
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Exported' })
    );
    await waitFor(() => {
      expect(document.body.querySelector('a[download="diff_1.0.0_to_1.1.0.json"]')).toBeNull();
    });
  });

  it('calls onClose when the Close button is clicked', async () => {
    const onClose = jest.fn();
    render(<VersionDiffViewer {...defaultProps} onClose={onClose} />);
    await screen.findByText('CRITICAL IMPACT');

    fireEvent.click(screen.getByRole('button', { name: /close/i }));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('shows the error state and toasts when the diff fetch fails', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });

    render(<VersionDiffViewer {...defaultProps} />);

    expect(await screen.findByText('Failed to fetch version diff')).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Error', variant: 'error' })
    );
  });

  it('refetches the diff when versions change', async () => {
    const { rerender } = render(<VersionDiffViewer {...defaultProps} />);
    await screen.findByText('CRITICAL IMPACT');
    expect((global.fetch as jest.Mock).mock.calls.length).toBe(1);

    rerender(<VersionDiffViewer {...defaultProps} fromVersion="1.1.0" toVersion="1.2.0" />);

    await waitFor(() => {
      expect((global.fetch as jest.Mock).mock.calls.length).toBe(2);
    });
    expect((global.fetch as jest.Mock).mock.calls[1][0]).toContain(
      'from_version=1.1.0&to_version=1.2.0'
    );
  });
});
