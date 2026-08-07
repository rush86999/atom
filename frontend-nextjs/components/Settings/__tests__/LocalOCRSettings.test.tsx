/**
 * LocalOCRSettings component tests.
 *
 * Covers: non-Tauri notice, Tauri mode with OCR engine status (installed /
 * missing badges, recommended engine), install guide when no engine is
 * available, and the test-OCR flow (select file, run OCR, result display).
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { invoke } from '@tauri-apps/api/core';
import LocalOCRSettings from '../LocalOCRSettings';

jest.mock('@tauri-apps/api/core', () => ({
  invoke: jest.fn(),
}));

const mockInvoke = invoke as jest.Mock;

const ocrStatusAll = {
  python_available: true,
  tesseract_available: true,
  surya_available: false,
  recommended: 'tesseract',
  any_available: true,
};

const installGuide = {
  tesseract: {
    description: 'Fast, lightweight OCR',
    install: { macos: 'brew install tesseract', windows: 'choco install tesseract', linux: 'apt install tesseract-ocr' },
  },
  surya: {
    description: 'High accuracy',
    install: { all: 'pip install surya' },
    note: 'Requires GPU for best results',
  },
};

function setupTauri(overrides: Record<string, unknown> = {}) {
  (window as any).__TAURI__ = { event: { listen: jest.fn() } };
  mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
    if (opts?.command === 'check_ocr_availability') return ocrStatusAll;
    if (opts?.command === 'get_ocr_installation_guide') return installGuide;
    return {};
  });
}

describe('LocalOCRSettings', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete (window as any).__TAURI__;
  });

  it('shows the desktop-app notice when not running in Tauri', async () => {
    render(<LocalOCRSettings />);
    expect(await screen.findByText(/Local OCR is only available in the Atom desktop app/)).toBeInTheDocument();
  });

  it('shows engine availability badges and the recommended engine', async () => {
    setupTauri();
    render(<LocalOCRSettings />);
    expect(await screen.findByText('Local OCR Settings')).toBeInTheDocument();
    expect(screen.getByText('✓ Installed')).toBeInTheDocument();
    expect(screen.getByText('Not Installed')).toBeInTheDocument();
    expect(screen.getByText(/Recommended:/)).toBeInTheDocument();
    expect(screen.getByText('tesseract')).toBeInTheDocument();
  });

  it('shows the install guide when no engine is available', async () => {
    setupTauri();
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (opts?.command === 'check_ocr_availability') {
        return {
          python_available: false,
          tesseract_available: false,
          surya_available: false,
          recommended: 'none',
          any_available: false,
        };
      }
      if (opts?.command === 'get_ocr_installation_guide') return installGuide;
      return {};
    });
    render(<LocalOCRSettings />);
    expect(await screen.findByText('Install an OCR Engine')).toBeInTheDocument();
    expect(screen.getByText(/brew install tesseract/)).toBeInTheDocument();
    expect(screen.getByText(/pip install surya/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Select File/ })).not.toBeInTheDocument();
  });

  it('selects a file and runs OCR, showing the extracted text', async () => {
    setupTauri();
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (cmd === 'open_file_dialog') return { success: true, path: '/docs/scanned.pdf' };
      if (opts?.command === 'check_ocr_availability') return ocrStatusAll;
      if (opts?.command === 'get_ocr_installation_guide') return installGuide;
      if (opts?.command === 'process_local_ocr') {
        return { success: true, text: 'OCR extracted text from the document.' };
      }
      return {};
    });
    render(<LocalOCRSettings />);
    fireEvent.click(await screen.findByRole('button', { name: /Select File/ }));
    expect(await screen.findByText('scanned.pdf')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Run OCR/ }));
    expect(await screen.findByText('OCR extracted text from the document.')).toBeInTheDocument();
  });

  it('shows the error text when OCR processing fails', async () => {
    setupTauri();
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (cmd === 'open_file_dialog') return { success: true, path: '/docs/scanned.pdf' };
      if (opts?.command === 'check_ocr_availability') return ocrStatusAll;
      if (opts?.command === 'get_ocr_installation_guide') return installGuide;
      if (opts?.command === 'process_local_ocr') return { success: false, error: 'no text found' };
      return {};
    });
    render(<LocalOCRSettings />);
    fireEvent.click(await screen.findByRole('button', { name: /Select File/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Run OCR/ }));
    expect(await screen.findByText(/Error: no text found/)).toBeInTheDocument();
  });

  it('shows the exception message when OCR throws', async () => {
    setupTauri();
    mockInvoke.mockImplementation(async (cmd: string, opts: any) => {
      if (cmd === 'open_file_dialog') return { success: true, path: '/docs/scanned.pdf' };
      if (opts?.command === 'check_ocr_availability') return ocrStatusAll;
      if (opts?.command === 'get_ocr_installation_guide') return installGuide;
      if (opts?.command === 'process_local_ocr') return Promise.reject(new Error('tesseract crashed'));
      return {};
    });
    render(<LocalOCRSettings />);
    fireEvent.click(await screen.findByRole('button', { name: /Select File/ }));
    fireEvent.click(await screen.findByRole('button', { name: /Run OCR/ }));
    expect(await screen.findByText(/Error: Error: tesseract crashed/)).toBeInTheDocument();
  });
});
