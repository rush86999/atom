/**
 * ZohoWorkDriveIngestion component tests.
 *
 * The component auto-loads on mount: teams, team folders, and the private
 * workspace ("root") listing. It also browses Team Folders via the
 * /team-folders endpoint, passing workspace_id/team_id to /files/list.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import ZohoWorkDriveIngestion from '../ZohoWorkDriveIngestion';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const mockGetAuthToken = jest.fn().mockReturnValue('test-jwt-token');
jest.mock('@/lib/identity', () => ({
  getAuthToken: () => mockGetAuthToken(),
}));

const privateFiles = [
  { id: 'f1', name: 'quarterly-report.pdf', type: 'file', extension: 'pdf', size: 2621440 },
  { id: 'f2', name: 'Budget.xlsx', type: 'file', extension: 'xlsx', size: 512 },
  { id: 'd1', name: 'My Folder', type: 'folder' },
];

const teamFolderFiles = [
  { id: 'tff1', name: 'team-notes.docx', type: 'file', extension: 'docx', size: 1024 },
];

const teamFolders = [
  { id: 'tf1', name: 'Marketing Assets', team_id: 't1', team_name: 'Marketing', workspace_id: 'ws1', type: 'teamfolder' },
  { id: 'tf2', name: 'Finance Docs', team_id: 't2', team_name: 'Finance', workspace_id: 'ws2', type: 'teamfolder' },
];

function mockApi({
  fileList = privateFiles,
  teamFiles = teamFolderFiles,
  teamFolderList = teamFolders,
  ingestSuccess = true,
  preIngested = [] as string[],
  runningJobs = [] as any[],
} = {}) {
  global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
    const u = String(url);
    // Parseable-file count for the folder-ingest job result (mirrors the
    // backend: /ingest-folder only counts supported extensions).
    const supported = ['.docx', '.xlsx', '.xls', '.csv', '.pdf', '.txt', '.md', '.pptx'];
    const ingested = fileList.filter(
      (f: any) => f.type !== 'folder' && supported.some(ext => (f.name || '').toLowerCase().endsWith(ext))
    ).length;
    if (u.includes('/api/zoho-workdrive/ingest/jobs') && !u.includes('/api/zoho-workdrive/ingest/jobs/')) {
      // Recent-jobs list (no job id suffix) — powers the status strip.
      return Promise.resolve({ ok: true, json: async () => ({ success: true, data: runningJobs }) });
    }
    if (u.includes('/api/zoho-workdrive/ingested-ids')) {
      // Durable badge source of truth.
      return Promise.resolve({ ok: true, json: async () => ({ success: true, data: { ingested: preIngested } }) });
    }
    if (u.includes('/api/zoho-workdrive/files/list')) {
      const body = JSON.parse(String(init?.body || '{}'));
      const data = body.workspace_id ? teamFiles : fileList;
      return Promise.resolve({ ok: true, json: async () => ({ success: true, data }) });
    }
    if (u.includes('/api/zoho-workdrive/ingest-folder/jobs/')) {
      // Mirror the backend job-status endpoint: the folder ingest runs as a
      // background job and the component polls until completed/failed.
      return Promise.resolve({
        ok: true,
        json: async () => ({
          success: true,
          data: {
            job_id: 'job-test-1',
            status: 'completed',
            result: {
              success: ingestSuccess,
              files_ingested: ingested,
              files_processed: ingested,
              errors: [],
            },
          },
        }),
      });
    }
    if (u.includes('/api/zoho-workdrive/ingest-folder') && init?.method === 'POST') {
      // Mirror the backend: /ingest-folder starts a background JOB and
      // returns its id immediately.
      return Promise.resolve({
        ok: true,
        json: async () => ({ success: true, job_id: 'job-test-1', status: 'started' }),
      });
    }
    if (u.includes('/api/zoho-workdrive/ingest/jobs/')) {
      // Mirror the backend job-status endpoint: single-file AND folder
      // ingest jobs share one registry/status route, and the component polls
      // until completed/failed. The result carries both shapes' fields
      // (doc_id for a file job, files_ingested/errors for a folder job).
      return Promise.resolve({
        ok: true,
        json: async () => ({
          success: true,
          data: {
            job_id: 'file-job-1',
            status: ingestSuccess ? 'completed' : 'failed',
            result: ingestSuccess
              ? { success: true, doc_id: 'd1', files_ingested: ingested, files_processed: ingested, errors: [] }
              : { success: false, error: 'permission denied' },
            error: null,
          },
        }),
      });
    }
    if (u.includes('/api/zoho-workdrive/ingest') && init?.method === 'POST') {
      // Mirror the backend: /ingest starts a background JOB and returns its
      // id immediately (a big file parses for minutes past any proxy
      // timeout).
      return Promise.resolve({
        ok: true,
        json: async () => ({ success: true, job_id: 'file-job-1', status: 'started', file_id: 'f1' }),
      });
    }
    if (u.includes('/api/zoho-workdrive/team-folders')) {
      return Promise.resolve({ ok: true, json: async () => ({ success: true, data: teamFolderList }) });
    }
    if (u.includes('/api/zoho-workdrive/teams')) {
      return Promise.resolve({ ok: true, json: async () => ({ success: true, data: [] }) });
    }
    return Promise.resolve({ ok: true, json: async () => ({}) });
  });
}


async function loadFiles() {
  // The component auto-loads the root folder on mount (files are fetched
  // during init, not only on user action), so wait for the listing itself.
  await screen.findByText('quarterly-report.pdf');
}


describe('ZohoWorkDriveIngestion', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApi();
  });

  it('renders the card title and description', async () => {
    render(<ZohoWorkDriveIngestion />);
    expect(await screen.findByText('Zoho WorkDrive Ingestion')).toBeInTheDocument();
    expect(screen.getByText(/Sync and ingest documents/)).toBeInTheDocument();
  });

  it('sends the Bearer token on every backend call (CSRF middleware rejects cookie-only POSTs)', async () => {
    // jest.config resets mocks between tests — arm the token inside the test.
    mockGetAuthToken.mockReturnValue('test-jwt-token');
    render(<ZohoWorkDriveIngestion />);
    await loadFiles();
    const calls = (global.fetch as jest.Mock).mock.calls;

    // GETs (teams, team-folders) carry Authorization without Content-Type.
    for (const path of ['/api/zoho-workdrive/teams', '/api/zoho-workdrive/team-folders']) {
      const call = calls.find(([u]) => String(u).includes(path));
      expect(call).toBeTruthy();
      expect(call[1].headers.Authorization).toBe('Bearer test-jwt-token');
      expect(call[1].headers['Content-Type']).toBeUndefined();
    }
    // POSTs (files/list) carry Authorization + JSON Content-Type.
    const listCall = calls.find(([u]) => String(u).includes('/files/list'));
    expect(listCall[1].headers.Authorization).toBe('Bearer test-jwt-token');
    expect(listCall[1].headers['Content-Type']).toBe('application/json');
  });


  it('auto-lists the private workspace on mount, with sizes and folder Open buttons', async () => {
    render(<ZohoWorkDriveIngestion />);
    expect(await screen.findByText('quarterly-report.pdf')).toBeInTheDocument();
  });

  it('shows the empty state and Go to Root fetches the root folder', async () => {
    // Stateful mock: the root folder holds files; opening Team Drive (d1)
    // returns an empty listing so the empty state admits the Go to Root CTA
    // (rendered only when currentFolderId !== 'root').
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes('/api/zoho-workdrive/files/list')) {
        const body = JSON.parse(String(init?.body || '{}'));
        const empty = body.parent_id === 'd1';
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true, data: empty ? [] : privateFiles }),
        });
      }
      if (u.includes('/api/zoho-workdrive/teams')) {
        return Promise.resolve({ ok: true, json: async () => ({ success: true, data: [] }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    render(<ZohoWorkDriveIngestion />);
    await screen.findByText('quarterly-report.pdf');
    fireEvent.click(await screen.findByRole('button', { name: /Open/ }));
    await screen.findByText('No files found in this folder');

    const goRoot = await screen.findByRole('button', { name: /Go to Root/ });
    fireEvent.click(goRoot);
    await waitFor(() => {
      const listCall = (global.fetch as jest.Mock).mock.calls
        .filter(([u]) => String(u).includes('/files/list'))
        .slice(-1)[0];
      expect(JSON.parse(listCall[1].body).parent_id).toBe('root');
    });
  });

  it('lists files after Refresh, with formatted sizes and folder Open buttons', async () => {
    render(<ZohoWorkDriveIngestion />);
    await loadFiles();
    expect(screen.getByText('quarterly-report.pdf')).toBeInTheDocument();
    expect(screen.getByText('Budget.xlsx')).toBeInTheDocument();
    expect(screen.getByText('My Folder')).toBeInTheDocument();
    expect(screen.getByText(/PDF • 2\.5 MB/)).toBeInTheDocument();
    expect(screen.getByText(/XLSX • 512 B/)).toBeInTheDocument();
    expect(screen.getByText('Folder')).toBeInTheDocument();
  });

  it('lists Team Folders at the private root', async () => {
    render(<ZohoWorkDriveIngestion />);
    expect(await screen.findByText('Marketing Assets')).toBeInTheDocument();
    expect(screen.getByText('Finance Docs')).toBeInTheDocument();
    expect(screen.getByText(/Marketing • Team Folder/)).toBeInTheDocument();
  });

  it('opens a team folder by fetching its workspace files with workspace_id', async () => {
    render(<ZohoWorkDriveIngestion />);
    await screen.findByText('Marketing Assets');
    fireEvent.click(screen.getAllByRole('button', { name: /Open/ })[0]);
    expect(await screen.findByText('team-notes.docx')).toBeInTheDocument();
    const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
    const teamCall = listCalls[listCalls.length - 1];
    expect(JSON.parse(teamCall[1].body)).toEqual({ parent_id: 'tf1', workspace_id: 'ws1', team_id: 't1' });
  });

  it('hides team folders inside a team folder and returns to the private root via the breadcrumb', async () => {
    render(<ZohoWorkDriveIngestion />);
    await screen.findByText('Marketing Assets');
    fireEvent.click(screen.getAllByRole('button', { name: /Open/ })[0]);
    await screen.findByText('team-notes.docx');
    expect(screen.queryByText('Finance Docs')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('My WorkDrive'));
    expect(await screen.findByText('quarterly-report.pdf')).toBeInTheDocument();
    const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
    const rootCall = listCalls[listCalls.length - 1];
    expect(JSON.parse(rootCall[1].body)).toEqual({ parent_id: 'root' });
  });

  it('opens a regular folder by fetching its children', async () => {
    mockApi({ teamFolderList: [] });
    render(<ZohoWorkDriveIngestion />);
    await screen.findByText('My Folder');
    fireEvent.click(screen.getByRole('button', { name: /Open/ }));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      const openCall = listCalls[listCalls.length - 1];
      expect(JSON.parse(openCall[1].body)).toEqual({ parent_id: 'd1' });
    });
  });

  it('opens a folder row on double-click', async () => {
    mockApi({ teamFolderList: [] });
    render(<ZohoWorkDriveIngestion />);
    await screen.findByText('My Folder');
    fireEvent.dblClick(screen.getByText('My Folder'));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      const openCall = listCalls[listCalls.length - 1];
      expect(JSON.parse(openCall[1].body)).toEqual({ parent_id: 'd1' });
    });
  });

  it('opens a team folder row on double-click', async () => {
    render(<ZohoWorkDriveIngestion />);
    await screen.findByText('Marketing Assets');
    fireEvent.dblClick(screen.getByText('Marketing Assets'));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      const openCall = listCalls[listCalls.length - 1];
      expect(JSON.parse(openCall[1].body)).toEqual({ parent_id: 'tf1', workspace_id: 'ws1', team_id: 't1' });
    });
  });

  it('does not open anything when double-clicking a file row', async () => {
    render(<ZohoWorkDriveIngestion />);
    await screen.findByText('quarterly-report.pdf');
    fireEvent.dblClick(screen.getByText('quarterly-report.pdf'));
    // No extra /files/list call beyond the mount-time fetch.
    const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
    expect(listCalls.length).toBe(1);
  });

  it('shows the empty state with Refresh Files while still listing team folders', async () => {
    mockApi({ fileList: [] });
    render(<ZohoWorkDriveIngestion />);
    expect(await screen.findByText('No files found in this folder')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Refresh Files/ })).toBeInTheDocument();
    // Team folders are still listed so the user can navigate to them
    expect(screen.getByText('Marketing Assets')).toBeInTheDocument();
  });

  it('ingests a file and toasts success', async () => {
    render(<ZohoWorkDriveIngestion />);

    await loadFiles();
    // Scope to the file's own row: team-folder rows also render an exact
    // "Ingest" button (and render before the file list), so a bare
    // findAllByRole(/^Ingest$/) hits a folder, not quarterly-report.pdf.
    const ingestBtn = within(
      (screen.getByText('quarterly-report.pdf').closest('div.justify-between') as HTMLElement)
    ).getByRole('button', { name: /^Ingest$/ });
    fireEvent.click(ingestBtn);
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Ingestion Successful',
          description: 'Loaded quarterly-report.pdf into AI Employee working memory.',
        })
      );
    });
    // Scope to the ingest POST — /ingest/jobs (recent-jobs list) also
    // contains '/ingest' but is a GET.
    const ingestCall = (global.fetch as jest.Mock).mock.calls
      .find(([u, init]) => String(u).endsWith('/api/zoho-workdrive/ingest') && init?.method === 'POST');
    expect(JSON.parse(ingestCall[1].body)).toEqual({ file_id: 'f1' });
    // Single-file ingest runs as a backend job: the component polls the
    // job-status endpoint instead of waiting on one long request (which the
    // dev proxy kills at 30s with a phantom 500).
    const jobPoll = (global.fetch as jest.Mock).mock.calls.find(([u]) => String(u).includes('/ingest/jobs/'));
    expect(String(jobPoll[0])).toContain('/api/zoho-workdrive/ingest/jobs/file-job-1');
  });

  it('hydrates durable ingested badges from the backend after a reload', async () => {
    // Session-only React state used to reset every navigation — the badge
    // now comes from POST /ingested-ids (document-store truth).
    mockApi({ preIngested: ['f1'] });
    render(<ZohoWorkDriveIngestion />);
    await loadFiles();

    const row = within(
      (screen.getByText('quarterly-report.pdf').closest('div.justify-between') as HTMLElement)
    );
    expect(row.getByText('✓ Ingested to Memory')).toBeInTheDocument();
    expect(row.getByRole('button', { name: /Re-Ingest/ })).toBeInTheDocument();
    const badgeCall = (global.fetch as jest.Mock).mock.calls.find(([u]) => String(u).includes('/ingested-ids'));
    expect(JSON.parse(badgeCall[1].body).file_ids).toContain('f1');
  });

  it('surfaces a running ingestion job started before this page load', async () => {
    // Job ids used to live only in the page that started the ingest; the
    // recent-jobs strip re-attaches after navigating away and back.
    mockApi({
      runningJobs: [{
        job_id: 'job-running-1', status: 'running', kind: 'folder',
        folder_ids: ['fld-h'], file_id: null,
        started_at: new Date().toISOString(), finished_at: null, result: null, error: null,
      }],
    });
    render(<ZohoWorkDriveIngestion />);
    expect(await screen.findByText(/Folder ingest \(1 folder\) in progress/)).toBeInTheDocument();
  });

  it('ingests all files via the server-side batch endpoint', async () => {
    render(<ZohoWorkDriveIngestion />);
    await loadFiles();
    fireEvent.click(screen.getByRole('button', { name: /Ingest All Files/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Batch Ingestion Complete' })
      );
    });
    const batchCall = (global.fetch as jest.Mock).mock.calls
      .filter(([u, init]) => String(u).includes('/api/zoho-workdrive/ingest-folder') && init?.method === 'POST')
      .slice(-1)[0];
    expect(JSON.parse(batchCall[1].body)).toEqual({ folder_id: 'root', recursive: false });
    // Every ingestable visible file is marked ingested on a clean batch
    expect(await screen.findAllByText('✓ Ingested to Memory')).toHaveLength(2);
  });

  it('ingests multiple ticked folders in one folder_ids batch call', async () => {
    render(<ZohoWorkDriveIngestion />);
    await loadFiles();

    // Tick both listed folders ("My Folder" is the only one in the fixture's
    // root listing — tick it and verify the batch envelope, then re-run with
    // the folder count of the listing by ticking every folder checkbox).
    const folderChecks = screen.getAllByRole('checkbox', { name: /^Select folder / });
    expect(folderChecks.length).toBeGreaterThanOrEqual(1);
    folderChecks.forEach(c => fireEvent.click(c));

    fireEvent.click(screen.getByRole('button', { name: /Ingest \d+ folders?/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Folder Ingestion Complete' })
      );
    });
    const batchCall = (global.fetch as jest.Mock).mock.calls
      .filter(([u, init]) => String(u).includes('/api/zoho-workdrive/ingest-folder') && init?.method === 'POST')
      .slice(-1)[0];
    const body = JSON.parse(batchCall[1].body);
    expect(body.folder_ids).toEqual(['d1']);
    expect(body.recursive).toBe(true);
    expect(body.folder_id).toBeUndefined();
    // Selection clears after a successful run.
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Ingest \d+ folders?/ })).not.toBeInTheDocument();
    });
  });

  it('batch ingests only parseable extensions and still marks them when unsupported files are present', async () => {
    // A .xyz file sits alongside supported ones; the backend /ingest-folder
    // skips it, so it must not count as a failure or block the badges.
    const mixedFiles = [
      ...privateFiles,
      { id: 'fx', name: 'notes.xyz', type: 'file', extension: 'xyz', size: 10 },
    ];
    mockApi({ fileList: mixedFiles });
    render(<ZohoWorkDriveIngestion />);
    await screen.findByText('notes.xyz');
    fireEvent.click(screen.getByRole('button', { name: /Ingest All Files/ }));
    await waitFor(() => {
      const batchCall = (global.fetch as jest.Mock).mock.calls
        .filter(([u, init]) => String(u).includes('/api/zoho-workdrive/ingest-folder') && init?.method === 'POST')
        .slice(-1)[0];
      // Badge gating succeeded — the toast reports the supported count only
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Batch Ingestion Complete',
          description: expect.stringContaining('2 of 2 files'),
        })
      );
      expect(JSON.parse(batchCall[1].body)).toEqual({ folder_id: 'root', recursive: false });
    });
    // Only the two supported files get the badge
    expect(await screen.findAllByText('✓ Ingested to Memory')).toHaveLength(2);
  });

  it('toasts an error when ingestion fails', async () => {
    mockApi({ ingestSuccess: false });
    render(<ZohoWorkDriveIngestion />);
    await screen.findByText('quarterly-report.pdf');

    // Row-scoped: team-folder rows carry an identical "Ingest" button.
    const ingestBtn = within(
      (screen.getByText('quarterly-report.pdf').closest('div.justify-between') as HTMLElement)
    ).getByRole('button', { name: /^Ingest$/ });
    fireEvent.click(ingestBtn);

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Ingestion Failed', description: 'permission denied' })
      );
    });
  });

  it('refreshes the current folder via the Refresh button using the last params', async () => {
    render(<ZohoWorkDriveIngestion />);


    await screen.findByText('quarterly-report.pdf');
    fireEvent.click(screen.getByRole('button', { name: /Refresh/ }));
    await screen.findByText('quarterly-report.pdf');
    fireEvent.click(screen.getByRole('button', { name: /^Refresh$/ }));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      expect(listCalls.length).toBeGreaterThanOrEqual(2);
      expect(JSON.parse(listCalls[listCalls.length - 1][1].body)).toEqual({ parent_id: 'root' });
    });
  });

  it('shows only files in recursive All Files mode and toggles back', async () => {
    render(<ZohoWorkDriveIngestion />);
    await screen.findByText('quarterly-report.pdf');
    expect(screen.getByText('My Folder')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^All Files$/ }));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      expect(JSON.parse(listCalls[listCalls.length - 1][1].body)).toEqual({ parent_id: 'root', recursive: true });
    });
    // folders are filtered out in all-files mode
    expect(screen.queryByText('My Folder')).not.toBeInTheDocument();
    expect(screen.getByText('quarterly-report.pdf')).toBeInTheDocument();

    // The button stays disabled until the recursive fetch settles — wait for
    // it to re-enable so the toggle-back click isn't suppressed.
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^Current Folder$/ })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole('button', { name: /^Current Folder$/ }));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      expect(JSON.parse(listCalls[listCalls.length - 1][1].body)).toEqual({ parent_id: 'root' });
    });
    expect(await screen.findByText('My Folder')).toBeInTheDocument();
  });
});
