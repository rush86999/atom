/**
 * VersionComparisonMetrics Component Tests
 *
 * Tests verify the real VersionComparisonMetrics
 * (components/Versioning/VersionComparisonMetrics.tsx):
 * - empty state before any version is selected
 * - selecting a version badge fetches + renders its metrics
 * - comparing 2 versions renders trend vs the first selected version
 * - at most 4 versions can be compared (5th is rejected with a toast)
 * - deselecting removes a version from the comparison
 * - versions without metrics fall back to zeroed metrics
 * - Refresh re-fetches, Export downloads a JSON blob and toasts
 * - View Version Details forwards the selected version
 *
 * API: GET /api/v1/workflows/:id/versions/:version/metrics
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { VersionComparisonMetrics } from '../VersionComparisonMetrics';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const metricsByVersion: Record<string, any> = {
  '1.0.0': {
    workflow_id: 'wf-1',
    version: '1.0.0',
    execution_count: 12,
    success_rate: 94.5,
    avg_execution_time: 1.25,
    error_count: 2,
    last_execution: '2026-08-01T10:00:00.000Z',
    performance_score: 92,
  },
  '1.1.0': {
    workflow_id: 'wf-1',
    version: '1.1.0',
    execution_count: 20,
    success_rate: 90.1,
    avg_execution_time: 1.75,
    error_count: 5,
    last_execution: '2026-08-05T10:00:00.000Z',
    performance_score: 80,
  },
  '1.2.0': {
    workflow_id: 'wf-1',
    version: '1.2.0',
    execution_count: 7,
    success_rate: 88,
    avg_execution_time: 2.1,
    error_count: 1,
    last_execution: null,
    performance_score: 70,
  },
};

const defaultProps = {
  workflowId: 'wf-1',
  workflowName: 'Sales Pipeline',
  versions: ['1.0.0', '1.1.0', '1.2.0', '1.3.0', '1.4.0'],
  onVersionSelect: jest.fn(),
};

const metricsFetch = jest.fn();

const mockFetchWithMetrics = () => {
  (global.fetch as jest.Mock).mockImplementation((url: string) => {
    const u = String(url);
    const match = u.match(/\/versions\/([\d.]+)\/metrics/);
    if (match) {
      metricsFetch(u);
      const v = match[1];
      if (metricsByVersion[v]) {
        return Promise.resolve({ ok: true, json: async () => ({ metrics: metricsByVersion[v] }) });
      }
      return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
    }
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });
};

describe('VersionComparisonMetrics', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
    metricsFetch.mockClear();
    mockFetchWithMetrics();
  });

  it('shows the empty state when no versions are selected', () => {
    render(<VersionComparisonMetrics {...defaultProps} />);

    expect(screen.getByText('No Versions Selected')).toBeInTheDocument();
    expect(
      screen.getByText(/Select one or more versions above to compare/)
    ).toBeInTheDocument();
    expect(screen.queryByText('Total Executions')).not.toBeInTheDocument();
  });

  it('selects a version, fetches its metrics and renders the metric cards', async () => {
    render(<VersionComparisonMetrics {...defaultProps} />);

    fireEvent.click(screen.getByText('v1.0.0'));

    expect(await screen.findByText('92.0')).toBeInTheDocument();
    expect(screen.getByText('1 version selected')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument(); // executions
    expect(screen.getByText('94.5')).toBeInTheDocument(); // success rate
    expect(screen.getByText('1.25')).toBeInTheDocument(); // avg time
    expect(screen.getByText('2')).toBeInTheDocument(); // errors
    expect(metricsFetch).toHaveBeenCalledWith(
      expect.stringContaining('/versions/1.0.0/metrics')
    );
  });

  it('renders a trend against the first selected version when comparing two', async () => {
    render(<VersionComparisonMetrics {...defaultProps} />);

    fireEvent.click(screen.getByText('v1.0.0'));
    await screen.findByText('92.0');
    fireEvent.click(screen.getByText('v1.1.0'));

    // v1.1.0 (80) vs v1.0.0 (92) => -13.0%
    expect(await screen.findByText('13.0%')).toBeInTheDocument();
    expect(screen.getByText('2 versions selected')).toBeInTheDocument();
    // both versions' detail cards present
    expect(screen.getAllByText('Total Executions')).toHaveLength(2);
  });

  it('rejects a 5th version with a toast and does not fetch it', async () => {
    render(<VersionComparisonMetrics {...defaultProps} />);

    for (const v of ['1.0.0', '1.1.0', '1.2.0', '1.3.0']) {
      fireEvent.click(screen.getByText(`v${v}`));
    }
    await screen.findByText('4 versions selected');

    fireEvent.click(screen.getByText('v1.4.0'));

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Maximum Reached', variant: 'error' })
    );
    expect(screen.getByText('4 versions selected')).toBeInTheDocument();
    expect(metricsFetch.mock.calls.flat().some((u) => u.includes('/versions/1.4.0/metrics'))).toBe(false);
  });

  it('deselects a version and removes its metric cards', async () => {
    render(<VersionComparisonMetrics {...defaultProps} />);

    fireEvent.click(screen.getByText('v1.0.0'));
    await screen.findByText('92.0');
    fireEvent.click(screen.getByText('v1.1.0'));
    await screen.findByText('13.0%');

    // "v1.1.0" now appears both in the selector badge and the metric cards —
    // click the selector badge (first in DOM order) to deselect
    fireEvent.click(screen.getAllByText('v1.1.0')[0]);

    await waitFor(() => {
      expect(screen.getAllByText('Total Executions')).toHaveLength(1);
    });
    expect(screen.getByText('1 version selected')).toBeInTheDocument();
    expect(screen.queryByText('13.0%')).not.toBeInTheDocument();
  });

  it('renders zeroed metrics when a version has no metrics yet', async () => {
    render(<VersionComparisonMetrics {...defaultProps} />);

    fireEvent.click(screen.getByText('v1.3.0'));

    // performance score + success rate both render "0.0"; executions/errors render "0"
    const zeros = await screen.findAllByText('0.0');
    expect(zeros.length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(2);
  });

  it('re-fetches metrics on Refresh', async () => {
    render(<VersionComparisonMetrics {...defaultProps} />);

    fireEvent.click(screen.getByText('v1.0.0'));
    await screen.findByText('92.0');
    const before = metricsFetch.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => {
      expect(metricsFetch.mock.calls.length).toBeGreaterThan(before);
    });
  });

  it('exports the metrics comparison as a JSON download and toasts', async () => {
    const createObjectURL = jest.fn(() => 'blob:mock-url');
    const revokeObjectURL = jest.fn();
    (URL.createObjectURL as jest.Mock) = createObjectURL;
    (URL.revokeObjectURL as jest.Mock) = revokeObjectURL;

    render(<VersionComparisonMetrics {...defaultProps} />);
    fireEvent.click(screen.getByText('v1.0.0'));
    await screen.findByText('92.0');

    fireEvent.click(screen.getByRole('button', { name: /export/i }));

    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Exported' })
    );

    // The temp anchor is removed from the DOM after the click
    await waitFor(() => {
      expect(document.body.querySelector('a[download$="metrics_comparison.json"]')).toBeNull();
    });
  });

  it('forwards the version to onVersionSelect via View Version Details', async () => {
    const onVersionSelect = jest.fn();
    render(
      <VersionComparisonMetrics {...defaultProps} onVersionSelect={onVersionSelect} />
    );

    fireEvent.click(screen.getByText('v1.0.0'));
    const buttons = await screen.findAllByRole('button', { name: /view version details/i });
    expect(buttons).toHaveLength(1);
    fireEvent.click(buttons[0]);

    expect(onVersionSelect).toHaveBeenCalledWith('1.0.0');
  });

  it('renders a 3-card performance score row for three selected versions', async () => {
    render(<VersionComparisonMetrics {...defaultProps} />);

    for (const v of ['1.0.0', '1.1.0', '1.2.0']) {
      fireEvent.click(screen.getByText(`v${v}`));
    }

    expect(await screen.findByText('70.0')).toBeInTheDocument();
    expect(screen.getByText('3 versions selected')).toBeInTheDocument();
  });
});
