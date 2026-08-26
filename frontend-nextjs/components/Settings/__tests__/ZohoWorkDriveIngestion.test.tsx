/**
 * ZohoWorkDriveIngestion component tests.
 *
 * The component auto-loads on mount: teams, team folders, and the private
 * workspace ("root") listing. It also browses Team Folders via the
 * /team-folders endpoint, passing workspace_id/team_id to /files/list.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ZohoWorkDriveIngestion from '../ZohoWorkDriveIngestion';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
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
} = {}) {
  global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
    const u = String(url);
    if (u.includes('/api/zoho-workdrive/files/list')) {
      const body = JSON.parse(String(init?.body || '{}'));
      const data = body.workspace_id ? teamFiles : fileList;
      return Promise.resolve({ ok: true, json: async () => ({ success: true, data }) });
    }
    if (u.includes('/api/zoho-workdrive/ingest-folder')) {
      // Mirror the backend: /ingest-folder only counts parseable extensions.
      const supported = ['.docx', '.xlsx', '.xls', '.csv', '.pdf', '.txt', '.md', '.pptx'];
      const ingested = fileList.filter(
        (f: any) => f.type !== 'folder' && supported.some(ext => (f.name || '').toLowerCase().endsWith(ext))
      ).length;
      return Promise.resolve({
        ok: true,
        json: async () => ({ success: true, files_ingested: ingested, files_processed: ingested, errors: [] }),
      });
    }
    if (u.includes('/api/zoho-workdrive/ingest')) {
      return Promise.resolve({
        ok: true,
        json: async () => (ingestSuccess ? { success: true } : { success: false, error: 'permission denied' }),
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
    // Match the per-file Ingest button exactly (the header also renders an
    // "Ingest All Files" button that matches a loose /Ingest/ regex); the
    // first file row is quarterly-report.pdf.
    const ingestBtn = (await screen.findAllByRole('button', { name: /^Ingest$/ }))[0];
    fireEvent.click(ingestBtn);
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Ingestion Successful',
          description: 'Loaded quarterly-report.pdf into AI Employee working memory.',
        })
      );
    });
    const ingestCall = (global.fetch as jest.Mock).mock.calls.find(([u]) => String(u).includes('/ingest'));
    expect(JSON.parse(ingestCall[1].body)).toEqual({ file_id: 'f1' });
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
      .filter(([u]) => String(u).includes('/api/zoho-workdrive/ingest-folder'))
      .slice(-1)[0];
    expect(JSON.parse(batchCall[1].body)).toEqual({ folder_id: 'root', recursive: false });
    // Every ingestable visible file is marked ingested on a clean batch
    expect(await screen.findAllByText('✓ Ingested to Memory')).toHaveLength(2);
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
        .filter(([u]) => String(u).includes('/api/zoho-workdrive/ingest-folder'))
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
    fireEvent.click(screen.getAllByRole('button', { name: /^Ingest$/ })[0]);

    await loadFiles();
    const ingestBtn = (await screen.findAllByRole('button', { name: /^Ingest$/ }))[0];
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
