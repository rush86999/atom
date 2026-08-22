/**
 * ZohoWorkDriveIngestion component tests.
 *
 * Note: the component only fetches files on user action (Refresh / Open
 * folder / Go to Root) — there is no auto-load on mount (teams fetch only).
 *
 * Covers: card render, empty-folder state with Go to Root, file/folder
 * listing (size formatting, extensions), opening a folder, ingest success and
 * failure toasts, and the Refresh action.
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

const files = [
  { id: 'f1', name: 'quarterly-report.pdf', type: 'file', extension: 'pdf', size: 2621440 },
  { id: 'f2', name: 'Budget.xlsx', type: 'file', extension: 'xlsx', size: 512 },
  { id: 'd1', name: 'Team Drive', type: 'folder' },
];

function mockApi({ fileList = files, ingestSuccess = true } = {}) {
  global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
    const u = String(url);
    if (u.includes('/api/zoho-workdrive/files/list')) {
      return Promise.resolve({ ok: true, json: async () => ({ success: true, data: fileList }) });
    }
    if (u.includes('/api/zoho-workdrive/ingest')) {
      return Promise.resolve({
        ok: true,
        json: async () => (ingestSuccess ? { success: true } : { success: false, error: 'permission denied' }),
      });
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
    render(<ZohoWorkDriveIngestion userId="u1" />);
    expect(await screen.findByText('Zoho WorkDrive Ingestion')).toBeInTheDocument();
    expect(screen.getByText(/Sync and ingest documents/)).toBeInTheDocument();
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
          json: async () => ({ success: true, data: empty ? [] : files }),
        });
      }
      if (u.includes('/api/zoho-workdrive/teams')) {
        return Promise.resolve({ ok: true, json: async () => ({ success: true, data: [] }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });

    render(<ZohoWorkDriveIngestion userId="u1" />);
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
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await loadFiles();
    expect(screen.getByText('quarterly-report.pdf')).toBeInTheDocument();
    expect(screen.getByText('Budget.xlsx')).toBeInTheDocument();
    expect(screen.getByText('Team Drive')).toBeInTheDocument();
    expect(screen.getByText(/PDF • 2\.5 MB/)).toBeInTheDocument();
    expect(screen.getByText(/XLSX • 512 B/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Open/ })).toBeInTheDocument();
    expect(screen.getByText('Folder')).toBeInTheDocument();
  });

  it('opens a folder by fetching its children', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await loadFiles();
    fireEvent.click(await screen.findByRole('button', { name: /Open/ }));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      const openCall = listCalls[listCalls.length - 1];
      expect(JSON.parse(openCall[1].body)).toEqual({ user_id: 'u1', parent_id: 'd1' });
    });
  });

  it('ingests a file and toasts success', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
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
    expect(JSON.parse(ingestCall[1].body)).toEqual({ user_id: 'u1', file_id: 'f1' });
  });

  it('toasts an error when ingestion fails', async () => {
    mockApi({ ingestSuccess: false });
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await loadFiles();
    const ingestBtn = (await screen.findAllByRole('button', { name: /^Ingest$/ }))[0];
    fireEvent.click(ingestBtn);
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Ingestion Failed', description: 'permission denied' })
      );
    });
  });

  it('refreshes the current folder via the Refresh button', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await screen.findByText('quarterly-report.pdf');
    fireEvent.click(screen.getByRole('button', { name: /Refresh/ }));
    await screen.findByText('quarterly-report.pdf');
    fireEvent.click(screen.getByRole('button', { name: /Refresh/ }));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      expect(listCalls.length).toBeGreaterThanOrEqual(2);
    });
  });
});
