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
  // Wait for the mount-time teams fetch to finish (the Refresh button is
  // disabled while it is in flight), then trigger the file listing.
  await screen.findByText('No files found in this folder');
  fireEvent.click(screen.getByRole('button', { name: /Refresh/ }));
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
    mockApi({ fileList: [] });
    render(<ZohoWorkDriveIngestion userId="u1" />);
    const goRoot = await screen.findByRole('button', { name: /Go to Root/ });
    fireEvent.click(goRoot);
    await waitFor(() => {
      const listCall = (global.fetch as jest.Mock).mock.calls.find(([u]) => String(u).includes('/files/list'));
      expect(JSON.parse(listCall[1].body).parent_id).toBe('root');
    });
  });

  it('lists files after Refresh, with formatted sizes and folder Open buttons', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await loadFiles();
    expect(await screen.findByText('quarterly-report.pdf')).toBeInTheDocument();
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
    const ingestBtn = (await screen.findAllByRole('button', { name: /Ingest/ }))[0];
    fireEvent.click(ingestBtn);
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Success', description: 'Successfully ingested quarterly-report.pdf to ATOM memory' })
      );
    });
    const ingestCall = (global.fetch as jest.Mock).mock.calls.find(([u]) => String(u).includes('/ingest'));
    expect(JSON.parse(ingestCall[1].body)).toEqual({ user_id: 'u1', file_id: 'f1' });
  });

  it('toasts an error when ingestion fails', async () => {
    mockApi({ ingestSuccess: false });
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await loadFiles();
    const ingestBtn = (await screen.findAllByRole('button', { name: /Ingest/ }))[0];
    fireEvent.click(ingestBtn);
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Ingestion Failed', description: 'permission denied' })
      );
    });
  });

  it('refreshes the current folder via the Refresh button', async () => {
    render(<ZohoWorkDriveIngestion userId="u1" />);
    await screen.findByText('No files found in this folder');
    fireEvent.click(screen.getByRole('button', { name: /Refresh/ }));
    await screen.findByText('quarterly-report.pdf');
    fireEvent.click(screen.getByRole('button', { name: /Refresh/ }));
    await waitFor(() => {
      const listCalls = (global.fetch as jest.Mock).mock.calls.filter(([u]) => String(u).includes('/files/list'));
      expect(listCalls.length).toBeGreaterThanOrEqual(2);
    });
  });
});
