/**
 * VersionHistoryTimeline Component Tests
 *
 * Tests verify the real VersionHistoryTimeline
 * (components/Versioning/VersionHistoryTimeline.tsx):
 * - loading state, error state with Retry, and empty state
 * - renders version metadata (commit, author, branch, tags, active badge)
 * - branch filter re-fetches with the selected branch
 * - select two versions to reveal Compare and fire onCompareVersions
 * - rollback button only for the active version (and only when onRollback
 *   is provided); click forwards the version
 * - delete requires confirm, DELETEs, toasts and re-fetches
 * - checksum copy writes to the clipboard and toasts
 * - export downloads the version data and toasts
 * - expand reveals full details + onVersionSelect
 *
 * API: GET /api/v1/workflows/:id/versions?branch_name=&limit=100,
 *      DELETE /api/v1/workflows/:id/versions/:version,
 *      GET /api/v1/workflows/:id/versions/:version/data
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import { VersionHistoryTimeline } from '../VersionHistoryTimeline';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const allVersions = [
  {
    workflow_id: 'wf-1',
    version: '1.1.0',
    version_type: 'minor',
    change_type: 'feature',
    created_at: '2026-08-01T00:00:00.000Z',
    created_by: 'alice',
    commit_message: 'Fix login flow',
    tags: ['stable'],
    parent_version: '1.0.0',
    branch_name: 'main',
    checksum: 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6',
    is_active: true,
  },
  {
    workflow_id: 'wf-1',
    version: '1.0.0',
    version_type: 'major',
    change_type: 'breaking',
    created_at: '2026-07-01T00:00:00.000Z',
    created_by: 'bob',
    commit_message: 'Initial release',
    tags: [],
    parent_version: null,
    branch_name: 'main',
    checksum: null,
    is_active: false,
  },
  {
    workflow_id: 'wf-1',
    version: '0.9.0',
    version_type: 'beta',
    change_type: 'enhancement',
    created_at: '2026-06-01T00:00:00.000Z',
    created_by: 'carol',
    commit_message: 'Beta improvements',
    tags: ['beta'],
    parent_version: '0.8.0',
    branch_name: 'main',
    checksum: 'deadbeefdeadbeefdeadbeefdeadbeef',
    is_active: false,
  },
  {
    workflow_id: 'wf-1',
    version: '0.8.0',
    version_type: 'alpha',
    change_type: 'feature',
    created_at: '2026-05-01T00:00:00.000Z',
    created_by: 'dave',
    commit_message: 'Dev preview',
    tags: [],
    parent_version: null,
    branch_name: 'dev',
    checksum: null,
    is_active: false,
  },
];

const defaultProps = {
  workflowId: 'wf-1',
  workflowName: 'Sales Pipeline',
  currentUserId: 'user-1',
  onVersionSelect: jest.fn(),
  onCompareVersions: jest.fn(),
  onRollback: jest.fn(),
};

const mockFetch = () => {
  (global.fetch as jest.Mock).mockImplementation((url: string, init?: RequestInit) => {
    const u = String(url);
    if (u.includes('/versions?branch_name=')) {
      const branch = u.match(/branch_name=([^&]+)/)?.[1];
      // The initial (main) listing includes a dev-branch version so the
      // branch dropdown exposes both branches (branches derive from data).
      const filtered = branch === 'dev'
        ? allVersions.filter((v) => v.branch_name === 'dev')
        : allVersions;
      return Promise.resolve({ ok: true, json: async () => filtered });
    }
    if (init?.method === 'DELETE') {
      return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
    }
    if (u.includes('/data')) {
      return Promise.resolve({ ok: true, json: async () => ({ workflow: 'payload' }) });
    }
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });
};

const getVersionCard = (commitMessage: string) => {
  const el = screen.getByText(commitMessage).closest('.border.rounded-lg.p-4');
  expect(el).not.toBeNull();
  return el as HTMLElement;
};

describe('VersionHistoryTimeline', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
    mockFetch();
    // userEvent.setup() replaces navigator.clipboard with its own object, so
    // re-install the jest mock defensively (setup.ts's mock is one-time).
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: jest.fn().mockResolvedValue(undefined),
        readText: jest.fn().mockResolvedValue(''),
      },
      configurable: true,
    });
  });

  it('shows a loading state before the history resolves', () => {
    global.fetch = jest.fn(() => new Promise(() => {}));
    render(<VersionHistoryTimeline {...defaultProps} />);

    expect(screen.getByText('Version History')).toBeInTheDocument();
  });

  it('renders versions with metadata, tags and active badge', async () => {
    render(<VersionHistoryTimeline {...defaultProps} />);

    expect(await screen.findByText('Fix login flow')).toBeInTheDocument();
    expect(screen.getByText('4 versions • Sales Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Initial release')).toBeInTheDocument();
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('bob')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('stable')).toBeInTheDocument();
    expect(screen.getAllByText('feature').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Parent: v1.0.0')).toBeInTheDocument();
  });

  it('shows the empty state when no versions exist', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => [] });
    render(<VersionHistoryTimeline {...defaultProps} />);

    expect(await screen.findByText('No versions found')).toBeInTheDocument();
    expect(screen.getByText(/Create your first version to start tracking changes/)).toBeInTheDocument();
  });

  it('shows the error state with a working Retry button', async () => {
    let fail = true;
    (global.fetch as jest.Mock).mockImplementation(() => {
      if (fail) return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
      return Promise.resolve({ ok: true, json: async () => allVersions });
    });

    render(<VersionHistoryTimeline {...defaultProps} />);

    expect(await screen.findByText('Failed to fetch version history')).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Error', variant: 'error' })
    );

    fail = false;
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));

    expect(await screen.findByText('Fix login flow')).toBeInTheDocument();
  });

  it('re-fetches with the selected branch when the branch filter changes', async () => {
    const user = userEvent.setup();
    render(<VersionHistoryTimeline {...defaultProps} />);
    await screen.findByText('Fix login flow');

    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: 'dev' }));

    await waitFor(() => {
      expect((global.fetch as jest.Mock).mock.calls.some(([u]) => String(u).includes('branch_name=dev'))).toBe(true);
    });
    expect(await screen.findByText('Dev preview')).toBeInTheDocument();
    expect(screen.queryByText('Fix login flow')).not.toBeInTheDocument();
  });

  it('reveals Compare after selecting two versions and fires onCompareVersions', async () => {
    render(<VersionHistoryTimeline {...defaultProps} />);
    await screen.findByText('Fix login flow');

    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(4);
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);

    const compareBtn = screen.getByRole('button', { name: /compare/i });
    fireEvent.click(compareBtn);

    expect(defaultProps.onCompareVersions).toHaveBeenCalledWith('1.1.0', '1.0.0');
  });

  it('keeps only the two most recent selections', async () => {
    render(<VersionHistoryTimeline {...defaultProps} />);
    await screen.findByText('Fix login flow');

    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(checkboxes[2]);

    // oldest (0.9.0) replaced 1.1.0? No — shift() drops the first selected
    const compareBtn = screen.getByRole('button', { name: /compare/i });
    fireEvent.click(compareBtn);

    expect(defaultProps.onCompareVersions).toHaveBeenCalledWith('1.0.0', '0.9.0');
  });

  it('rolls back from the active version only, via onRollback', async () => {
    const onRollback = jest.fn();
    render(<VersionHistoryTimeline {...defaultProps} onRollback={onRollback} />);
    await screen.findByText('Fix login flow');

    const activeCard = getVersionCard('Fix login flow');
    const inactiveCard = getVersionCard('Initial release');

    // active: expand + rollback + export + delete + checksum-copy = 5
    // inactive (no checksum): expand + export + delete = 3
    expect(within(activeCard).getAllByRole('button')).toHaveLength(5);
    expect(within(inactiveCard).getAllByRole('button')).toHaveLength(3);

    fireEvent.click(within(activeCard).getAllByRole('button')[1]);
    expect(onRollback).toHaveBeenCalledWith('1.1.0');
  });

  it('does not render rollback buttons when onRollback is omitted', async () => {
    render(<VersionHistoryTimeline {...defaultProps} onRollback={undefined} />);
    await screen.findByText('Fix login flow');

    const activeCard = getVersionCard('Fix login flow');
    expect(within(activeCard).getAllByRole('button')).toHaveLength(4); // no rollback: expand + export + delete + checksum-copy
  });

  it('deletes a version after confirm, toasts and re-fetches', async () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    render(<VersionHistoryTimeline {...defaultProps} />);
    await screen.findByText('Fix login flow');

    const inactiveCard = getVersionCard('Initial release');
    fireEvent.click(within(inactiveCard).getAllByRole('button')[2]); // export is [1], delete is [2]

    await waitFor(() => {
      expect((global.fetch as jest.Mock).mock.calls.some(([u, init]) => String(u).includes('/versions/1.0.0') && init?.method === 'DELETE')).toBe(true);
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Success', description: 'Version 1.0.0 has been deleted' })
    );
    // refetch happened (fetch called again for the list)
    expect((global.fetch as jest.Mock).mock.calls.length).toBeGreaterThan(2);
    confirmSpy.mockRestore();
  });

  it('skips the DELETE when the user cancels the confirm dialog', async () => {
    jest.spyOn(window, 'confirm').mockReturnValue(false);
    render(<VersionHistoryTimeline {...defaultProps} />);
    await screen.findByText('Fix login flow');

    const inactiveCard = getVersionCard('Initial release');
    fireEvent.click(within(inactiveCard).getAllByRole('button')[2]);

    expect((global.fetch as jest.Mock).mock.calls.some(([, init]) => init?.method === 'DELETE')).toBe(false);
  });

  it('copies the checksum to the clipboard and toasts', async () => {
    render(<VersionHistoryTimeline {...defaultProps} />);
    await screen.findByText('Fix login flow');

    const activeCard = getVersionCard('Fix login flow');
    fireEvent.click(within(activeCard).getAllByRole('button')[4]); // checksum copy button

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6');
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Copied' })
    );
  });

  it('exports a version payload as a JSON download and toasts', async () => {
    const createObjectURL = jest.fn(() => 'blob:export-url');
    const revokeObjectURL = jest.fn();
    (URL.createObjectURL as jest.Mock) = createObjectURL;
    (URL.revokeObjectURL as jest.Mock) = revokeObjectURL;

    render(<VersionHistoryTimeline {...defaultProps} />);
    await screen.findByText('Fix login flow');

    const activeCard = getVersionCard('Fix login flow');
    fireEvent.click(within(activeCard).getAllByRole('button')[2]); // export

    await waitFor(() => {
      expect(createObjectURL).toHaveBeenCalled();
    });
    expect((global.fetch as jest.Mock).mock.calls.some(([u]) => String(u).includes('/versions/1.1.0/data'))).toBe(true);
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Exported', description: 'Version 1.1.0 exported successfully' })
    );
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:export-url');
  });

  it('expands a version to reveal full details and onVersionSelect', async () => {
    const onVersionSelect = jest.fn();
    render(<VersionHistoryTimeline {...defaultProps} onVersionSelect={onVersionSelect} />);
    await screen.findByText('Fix login flow');

    const activeCard = getVersionCard('Fix login flow');
    fireEvent.click(within(activeCard).getAllByRole('button')[0]); // expand chevron

    expect(within(activeCard).getByText('Version ID')).toBeInTheDocument();
    expect(within(activeCard).getByText('Workflow ID')).toBeInTheDocument();
    expect(within(activeCard).getByText('wf-1')).toBeInTheDocument();
    expect(within(activeCard).getByText(/SHA-256 Checksum/)).toBeInTheDocument();

    fireEvent.click(within(activeCard).getByRole('button', { name: /view full version details/i }));
    expect(onVersionSelect).toHaveBeenCalledWith(
      expect.objectContaining({ version: '1.1.0', commit_message: 'Fix login flow' })
    );
  });
});
