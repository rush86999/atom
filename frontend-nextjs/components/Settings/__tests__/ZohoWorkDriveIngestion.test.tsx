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

describe('ZohoWorkDriveIngestion', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApi();
  });

  it('renders the card title and description', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    expect(await screen.findByText('Zoho WorkDrive Ingestion')).toBeInTheDocument();
    expect(screen.getByText(/Sync and ingest documents/)).toBeInTheDocument();
  });

  it('auto-lists the private workspace on mount, with sizes and folder Open buttons', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    expect(await screen.findByText('quarterly-report.pdf')).toBeInTheDocument();
    expect(screen.getByText('Budget.xlsx')).toBeInTheDocument();
    expect(screen.getByText('My Folder')).toBeInTheDocument();
    expect(screen.getByText(/PDF • 2\.5 MB/)).toBeInTheDocument();
    expect(screen.getByText(/XLSX • 512 B/)).toBeInTheDocument();
    expect(screen.getByText('Folder')).toBeInTheDocument();
  });

  it('lists Team Folders at the private root', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    expect(await screen.findByText('Marketing Assets')).toBeInTheDocument();
    expect(screen.getByText('Finance Docs')).toBeInTheDocument();
    expect(screen.getByText(/Marketing • Team Folder/)).toBeInTheDocument();
  });

  it('opens a team folder by fetching its workspace files with workspace_id', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await screen.findByText('Marketing Assets');
    fireEvent.click(screen.getAllByRole('button', { name: /Open/ })[0]);
    expect(await screen.findByText('team-notes.docx')).toBeInTheDocument();
    const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
    const teamCall = listCalls[listCalls.length - 1];
    expect(JSON.parse(teamCall[1].body)).toEqual({ user_id: 'u1', parent_id: 'tf1', workspace_id: 'ws1', team_id: 't1' });
  });

  it('hides team folders inside a team folder and returns to the private root via the breadcrumb', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await screen.findByText('Marketing Assets');
    fireEvent.click(screen.getAllByRole('button', { name: /Open/ })[0]);
    await screen.findByText('team-notes.docx');
    expect(screen.queryByText('Finance Docs')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('My WorkDrive'));
    expect(await screen.findByText('quarterly-report.pdf')).toBeInTheDocument();
    const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
    const rootCall = listCalls[listCalls.length - 1];
    expect(JSON.parse(rootCall[1].body)).toEqual({ user_id: 'u1', parent_id: 'root' });
  });

  it('opens a regular folder by fetching its children', async () => {
    mockApi({ teamFolderList: [] });
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await screen.findByText('My Folder');
    fireEvent.click(screen.getByRole('button', { name: /Open/ }));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      const openCall = listCalls[listCalls.length - 1];
      expect(JSON.parse(openCall[1].body)).toEqual({ user_id: 'u1', parent_id: 'd1' });
    });
  });

  it('shows the empty state with Refresh Files while still listing team folders', async () => {
    mockApi({ fileList: [] });
    render(<ZohoWorkDriveIngestion userId="u1" />);
    expect(await screen.findByText('No files found in this folder')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Refresh Files/ })).toBeInTheDocument();
    // Team folders are still listed so the user can navigate to them
    expect(screen.getByText('Marketing Assets')).toBeInTheDocument();
  });

  it('ingests a file and toasts success', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await screen.findByText('quarterly-report.pdf');
    fireEvent.click(screen.getAllByRole('button', { name: /^Ingest$/ })[0]);
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Ingestion Successful', description: 'Loaded quarterly-report.pdf into AI Employee working memory.' })
      );
    });
    const ingestCall = (global.fetch as jest.Mock).mock.calls.find(([u]) => String(u).includes('/ingest'));
    expect(JSON.parse(ingestCall[1].body)).toEqual({ user_id: 'u1', file_id: 'f1' });
  });

  it('toasts an error when ingestion fails', async () => {
    mockApi({ ingestSuccess: false });
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await screen.findByText('quarterly-report.pdf');
    fireEvent.click(screen.getAllByRole('button', { name: /^Ingest$/ })[0]);
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Ingestion Failed', description: 'permission denied' })
      );
    });
  });

  it('refreshes the current folder via the Refresh button using the last params', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await screen.findByText('quarterly-report.pdf');
    fireEvent.click(screen.getByRole('button', { name: /^Refresh$/ }));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      expect(listCalls.length).toBeGreaterThanOrEqual(2);
      expect(JSON.parse(listCalls[listCalls.length - 1][1].body)).toEqual({ user_id: 'u1', parent_id: 'root' });
    });
  });

  it('shows only files in recursive All Files mode and toggles back', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await screen.findByText('quarterly-report.pdf');
    expect(screen.getByText('My Folder')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^All Files$/ }));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      expect(JSON.parse(listCalls[listCalls.length - 1][1].body)).toEqual({ user_id: 'u1', parent_id: 'root', recursive: true });
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
      expect(JSON.parse(listCalls[listCalls.length - 1][1].body)).toEqual({ user_id: 'u1', parent_id: 'root' });
    });
    expect(await screen.findByText('My Folder')).toBeInTheDocument();
  });
});
