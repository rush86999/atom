/**
 * LocalFileIngestion component tests.
 *
 * Covers: non-Tauri notice, Tauri mode with watched folders, selecting a file
 * to ingest, importing a folder (bounded to 20 files), OCR-ing a file that
 * needs it, the watch-folder flow, and the empty state.
 *
 * BUG FIX (test-driven): the component crashed with
 * "Cannot read properties of undefined (reading 'length')" at
 * `watchedFolders.length` when the Tauri `get_watched_folders` command
 * returned an unexpected payload — the state was set to `undefined` and the
 * render guard was not null-safe. Fixed by guarding `watchedFolders?.length`
 * and coercing the result with Array.isArray.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { invoke } from '@tauri-apps/api/core';
import LocalFileIngestion from '../LocalFileIngestion';

jest.mock('@tauri-apps/api/core', () => ({
  invoke: jest.fn(),
}));

const mockInvoke = invoke as jest.Mock;

type ListenHandler = (event: { payload: { path: string; operation: string } }) => void;

const tauriState: { listener?: ListenHandler } = {};

function installTauri() {
  const listen = jest.fn();
  listen.mockImplementation((_event: string, cb: ListenHandler) => {
    tauriState.listener = cb;
    return Promise.resolve(jest.fn());
  });
  (window as any).__TAURI__ = { event: { listen } };
  return listen;
}

const ingestedFile = (overrides: any = {}) => ({
  file_path: '/docs/report.pdf',
  file_name: 'report.pdf',
  extension: 'pdf',
  file_size: 2048,
  content: null,
  needs_ocr: true,
  ingested_at: '2026-08-07T00:00:00Z',
  ...overrides,
});

describe('LocalFileIngestion', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete tauriState.listener;
    delete (window as any).__TAURI__;
  });

  it('shows the desktop-app notice when not running in Tauri', async () => {
    render(<LocalFileIngestion />);
    expect(await screen.findByText(/Local file ingestion is only available in the Atom desktop app/)).toBeInTheDocument();
  });

  it('shows the ingestion UI in Tauri mode', async () => {
    installTauri();
    mockInvoke.mockResolvedValue({ folders: [] });
    render(<LocalFileIngestion />);
    expect(await screen.findByRole('button', { name: /Select File/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Import Folder/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Watch Folder/ })).toBeInTheDocument();
    expect(screen.getByText('No files ingested yet')).toBeInTheDocument();
  });

  it('does not crash when the watched-folders payload is unexpected (BUG: undefined.length)', async () => {
    installTauri();
    mockInvoke.mockResolvedValue({});
    render(<LocalFileIngestion />);
    expect(await screen.findByRole('button', { name: /Select File/ })).toBeInTheDocument();
    expect(screen.getByText('No files ingested yet')).toBeInTheDocument();
  });

  it('lists watched folders with Stop actions', async () => {
    installTauri();
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (opts?.command === 'get_watched_folders') return { folders: ['/watched/docs', '/watched/notes'] };
      if (opts?.command === 'stop_watching_folder') return {};
      return {};
    });
    render(<LocalFileIngestion />);
    expect(await screen.findByText(/Watched Folders \(2\)/)).toBeInTheDocument();
    expect(screen.getByText('/watched/docs')).toBeInTheDocument();
    expect(screen.getByText('/watched/notes')).toBeInTheDocument();
    const stopBtns = screen.getAllByRole('button', { name: /Stop/ });
    fireEvent.click(stopBtns[0]);
    await waitFor(() => {
      const stopCall = mockInvoke.mock.calls.find(
        ([cmd, params]) => cmd === 'atom_invoke_command' && params.command === 'stop_watching_folder'
      );
      expect(stopCall[1].params).toEqual({ path: '/watched/docs' });
    });
  });

  it('selects a file through the dialog and ingests it', async () => {
    installTauri();
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (cmd === 'open_file_dialog') return { success: true, path: '/docs/report.pdf' };
      if (opts?.command === 'get_watched_folders') return { folders: [] };
      if (opts?.command === 'ingest_local_file') return ingestedFile();
      return {};
    });
    render(<LocalFileIngestion />);
    fireEvent.click(await screen.findByRole('button', { name: /Select File/ }));
    expect(await screen.findByText('report.pdf')).toBeInTheDocument();
    expect(screen.getByText(/PDF • 2\.0 KB/)).toBeInTheDocument();
    const ingestCall = mockInvoke.mock.calls.find(
      ([cmd, params]) => cmd === 'atom_invoke_command' && params.command === 'ingest_local_file'
    );
    expect(ingestCall[1].params).toEqual({ file_path: '/docs/report.pdf' });
  });

  it('imports a folder, bounded to the first 20 supported files', async () => {
    installTauri();
    const entries = Array.from({ length: 25 }, (_, i) => ({
      path: `/docs/file${i}.pdf`,
      is_directory: false,
      extension: 'pdf',
    }));
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (cmd === 'open_folder_dialog') return { success: true, path: '/docs' };
      if (cmd === 'list_directory') return { success: true, entries };
      if (opts?.command === 'get_watched_folders') return { folders: [] };
      if (opts?.command === 'ingest_local_file') return ingestedFile();
      return {};
    });
    render(<LocalFileIngestion />);
    fireEvent.click(await screen.findByRole('button', { name: /Import Folder/ }));
    await waitFor(() => {
      const ingestCalls = mockInvoke.mock.calls.filter(
        ([cmd, params]) => cmd === 'atom_invoke_command' && params.command === 'ingest_local_file'
      );
      expect(ingestCalls.length).toBe(20);
    });
  });

  it('ingests a supported file when a folder-event arrives', async () => {
    installTauri();
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (opts?.command === 'get_watched_folders') return { folders: [] };
      if (opts?.command === 'ingest_local_file') {
        return ingestedFile({ file_path: '/watched/notes.md', file_name: 'notes.md', extension: 'md' });
      }
      return {};
    });
    render(<LocalFileIngestion />);
    await screen.findByRole('button', { name: /Select File/ });
    tauriState.listener!({ payload: { path: '/watched/notes.md', operation: 'create' } });
    expect(await screen.findByText('notes.md')).toBeInTheDocument();
    const ingestCall = mockInvoke.mock.calls.find(
      ([cmd, params]) => cmd === 'atom_invoke_command' && params.command === 'ingest_local_file'
    );
    expect(ingestCall[1].params).toEqual({ file_path: '/watched/notes.md' });
  });

  it('ignores unsupported file types in folder events', async () => {
    installTauri();
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (opts?.command === 'get_watched_folders') return { folders: [] };
      return {};
    });
    render(<LocalFileIngestion />);
    await screen.findByRole('button', { name: /Select File/ });
    tauriState.listener!({ payload: { path: '/watched/evil.exe', operation: 'modify' } });
    await new Promise((r) => setTimeout(r, 50));
    const ingestCalls = mockInvoke.mock.calls.filter(
      ([cmd, params]) => cmd === 'atom_invoke_command' && params.command === 'ingest_local_file'
    );
    expect(ingestCalls.length).toBe(0);
  });

  it('runs OCR on a file that needs it and marks it ready', async () => {
    installTauri();
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (cmd === 'open_file_dialog') return { success: true, path: '/docs/report.pdf' };
      if (opts?.command === 'get_watched_folders') return { folders: [] };
      if (opts?.command === 'ingest_local_file') return ingestedFile();
      return {};
    });
    render(<LocalFileIngestion />);
    fireEvent.click(await screen.findByRole('button', { name: /Select File/ }));
    const ocrBtn = await screen.findByRole('button', { name: /OCR/ });
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (opts?.command === 'get_watched_folders') return { folders: [] };
      if (opts?.command === 'process_local_ocr') return { success: true, text: 'Extracted text from the scanned report.' };
      return {};
    });
    fireEvent.click(ocrBtn);
    expect(await screen.findByText(/Extracted text from the scanned report/)).toBeInTheDocument();
    expect(screen.getByText('✓ Ready')).toBeInTheDocument();
  });

  it('watches a folder via the Watch Folder flow', async () => {
    installTauri();
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (cmd === 'open_folder_dialog') return { success: true, path: '/watched/docs' };
      if (opts?.command === 'get_watched_folders') return { folders: ['/watched/docs'] };
      return {};
    });
    render(<LocalFileIngestion />);
    fireEvent.click(await screen.findByRole('button', { name: /Watch Folder/ }));
    await waitFor(() => {
      const watchCall = mockInvoke.mock.calls.find(
        ([cmd, params]) => cmd === 'atom_invoke_command' && params.command === 'start_watching_folder'
      );
      expect(watchCall[1].params).toEqual({ path: '/watched/docs' });
    });
    expect(await screen.findByText('/watched/docs')).toBeInTheDocument();
  });
});
