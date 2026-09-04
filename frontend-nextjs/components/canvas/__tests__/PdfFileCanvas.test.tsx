/**
 * PdfFileCanvas tests (PDF canvas P1)
 *
 * Mocks lib/pdf-canvas-api and pdfjs-dist; verifies the panel contract:
 * state unwrap (filename/pages/lifecycle), the pending page-map working
 * copy (rotate/delete/move enable Save with the right payload), undo,
 * version-conflict surfacing, and attach-to-email handoff.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockApi = {
  fetchPdfBytes: jest.fn(),
  createBlankPdf: jest.fn(),
  createPdfFromUpload: jest.fn(),
  applyPageOps: jest.fn(),
  mergePdfUpload: jest.fn(),
  mergePdfCanvas: jest.fn(),
  attachPdfToEmail: jest.fn(),
  transitionLifecycle: jest.fn(),
  extractText: jest.fn(),
  getFormFields: jest.fn(),
  setFormFields: jest.fn(),
  flattenForm: jest.fn(),
  redactText: jest.fn(),
  stampSignature: jest.fn(),
  archiveToOnedrive: jest.fn(),
  sendToDocuSign: jest.fn(),
};

jest.mock('@/lib/pdf-canvas-api', () => ({
  __esModule: true,
  ...mockApi,
  unwrapPdfState: jest.requireActual('@/lib/pdf-canvas-api').unwrapPdfState,
}));

jest.mock('pdfjs-dist', () => ({
  __esModule: true,
  GlobalWorkerOptions: {},
  getDocument: () => ({
    promise: Promise.resolve({
      numPages: 3,
      getPage: async () => ({
        getViewport: ({ scale }: any) => ({ width: 612 * scale, height: 792 * scale }),
        render: () => ({ promise: Promise.resolve() }),
      }),
    }),
  }),
}));

import { PdfFileCanvas } from '../PdfFileCanvas';
import type { PdfCanvasState } from '@/lib/pdf-canvas-api';

function makeState(overrides: Partial<PdfCanvasState> = {}): PdfCanvasState {
  return {
    file: { hash: 'a'.repeat(64), page_count: 3, size_bytes: 1024, filename: 'Q3 quote.pdf' },
    versions: [{ hash: 'a'.repeat(64), action: 'create', author: 'user:u1', at: '2026-09-04T00:00:00Z' }],
    lifecycle: { state: 'drafting', approved_by: null, approved_at: null },
    source: 'upload',
    ...overrides,
  };
}

jest.mock('@/lib/pdf-worker-src', () => ({ pdfWorkerSrc: () => '' }));

describe('PdfFileCanvas', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApi.fetchPdfBytes.mockResolvedValue(new Blob([new Uint8Array([1, 2, 3])]));
  });

  it('renders filename, page count and lifecycle from the canvas state', async () => {
    render(<PdfFileCanvas canvasId="c1" data={makeState()} />);
    expect(screen.getByText('Q3 quote.pdf')).toBeInTheDocument();
    expect(screen.getByTestId('canvas-pdf-root')).toHaveTextContent('3 pages');
    expect(screen.getByTestId('canvas-pdf-root')).toHaveTextContent('drafting');
    await waitFor(() => expect(mockApi.fetchPdfBytes).toHaveBeenCalledWith('c1', 'a'.repeat(64)));
  });

  it('enables Save only after a pending page-map change and sends the working map', async () => {
    mockApi.applyPageOps.mockResolvedValue({ state: makeState({ file: { hash: 'b'.repeat(64), page_count: 3, size_bytes: 2048, filename: 'Q3 quote.pdf' } }) });
    render(<PdfFileCanvas canvasId="c1" data={makeState()} />);
    await screen.findByTestId('canvas-pdf-page-2');
    const save = screen.getByTestId('canvas-pdf-save');
    expect(save).toBeDisabled();

    fireEvent.click(screen.getByTestId('canvas-pdf-move-up-1'));
    expect(save).toBeEnabled();

    fireEvent.click(save);
    await waitFor(() => expect(mockApi.applyPageOps).toHaveBeenCalledWith('c1', [
      { src_index: 1, rotation: 0 },
      { src_index: 0, rotation: 0 },
      { src_index: 2, rotation: 0 },
    ], 'a'.repeat(64)));
  });

  it('accumulates absolute rotation and deletes via omission, undo restores', async () => {
    render(<PdfFileCanvas canvasId="c1" data={makeState()} />);
    await screen.findByTestId('canvas-pdf-page-2');
    fireEvent.click(screen.getByTestId('canvas-pdf-rotate-right-0'));
    fireEvent.click(screen.getByTestId('canvas-pdf-rotate-right-0'));
    fireEvent.click(screen.getByTestId('canvas-pdf-delete-1'));
    expect(screen.getByTestId('canvas-pdf-root')).toHaveTextContent('2 pages');
    expect(screen.getByText('Page 1 · 180°')).toBeInTheDocument();

    const save = screen.getByTestId('canvas-pdf-save');
    fireEvent.click(screen.getByTestId('canvas-pdf-undo'));
    expect(screen.getByTestId('canvas-pdf-root')).toHaveTextContent('3 pages');
    expect(save).toBeEnabled(); // rotation ops remain pending
  });

  it('surfaces a version conflict when the server refuses a stale save', async () => {
    mockApi.applyPageOps.mockRejectedValue({
      response: { data: { error: { message: 'version conflict: the document changed since it was loaded — reload and retry' } } },
    });
    render(<PdfFileCanvas canvasId="c1" data={makeState()} />);
    await screen.findByTestId('canvas-pdf-page-2');
    fireEvent.click(screen.getByTestId('canvas-pdf-rotate-right-2'));
    fireEvent.click(screen.getByTestId('canvas-pdf-save'));
    await waitFor(() =>
      expect(screen.getByTestId('canvas-pdf-error')).toHaveTextContent(/version conflict/),
    );
  });

  it('attaches to email and links the resulting draft', async () => {
    mockApi.attachPdfToEmail.mockResolvedValue({
      email_canvas_id: 'email-9',
      created_email_canvas: true,
      filename: 'Q3 quote.pdf',
    });
    render(<PdfFileCanvas canvasId="c1" data={makeState()} />);
    await screen.findByTestId('canvas-pdf-page-2');
    fireEvent.click(screen.getByTestId('canvas-pdf-attach'));
    await waitFor(() => expect(mockApi.attachPdfToEmail).toHaveBeenCalledWith('c1', false));
    const notice = screen.getByTestId('canvas-pdf-notice');
    expect(notice).toHaveTextContent('Attached — new email draft (Q3 quote.pdf)');
    expect(notice.querySelector('a')).toHaveAttribute('href', '/canvas/email-9');
  });

  it('shows the missing-state placeholder without a canvas id or file state', () => {
    render(<PdfFileCanvas canvasId={undefined} data={{ hello: 1 }} />);
    expect(screen.getByTestId('canvas-pdf-missing')).toBeInTheDocument();
  });

  it('lifecycle: drafting shows approve, approved locks edits and offers reopen', async () => {
    mockApi.transitionLifecycle.mockResolvedValue({ state: makeState() });
    render(<PdfFileCanvas canvasId="c1" data={makeState()} />);
    await screen.findByTestId('canvas-pdf-page-2');

    expect(screen.getByTestId('canvas-pdf-lifecycle')).toHaveTextContent('drafting');
    expect(screen.getByTestId('canvas-pdf-approve')).toBeInTheDocument();
    expect(screen.queryByTestId('canvas-pdf-reopen')).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('canvas-pdf-approve'));
    await waitFor(() => expect(mockApi.transitionLifecycle).toHaveBeenCalledWith('c1', 'approve'));
  });

  it('approved documents disable page mutations until reopened', async () => {
    const approved = makeState({
      lifecycle: { state: 'approved', approved_by: 'user:u-1', approved_at: '2026-09-04T00:00:00Z' },
    });
    render(<PdfFileCanvas canvasId="c1" data={approved} />);
    await screen.findByTestId('canvas-pdf-page-2');

    expect(screen.getByTestId('canvas-pdf-lifecycle')).toHaveTextContent('approved');
    expect(screen.getByTestId('canvas-pdf-save')).toBeDisabled();
    expect(screen.getByTestId('canvas-pdf-rotate-right-0')).toBeDisabled();
    expect(screen.getByTestId('canvas-pdf-delete-0')).toBeDisabled();
    expect(screen.getByTestId('canvas-pdf-reopen')).toBeInTheDocument();
    expect(screen.queryByTestId('canvas-pdf-approve')).not.toBeInTheDocument();
  });
});

describe('PdfFileCanvas P3/P4 panels', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApi.fetchPdfBytes.mockResolvedValue(new Blob([new Uint8Array([1, 2, 3])]));
    mockApi.extractText.mockResolvedValue({
      pages: [
        { page: 0, text: 'SSN: 123-45-6789 visible' },
        { page: 1, text: 'public line' },
      ],
    });
  });

  it('text pane renders extraction and OCR toggle refetches', async () => {
    render(<PdfFileCanvas canvasId="c1" data={makeState()} />);
    fireEvent.click(screen.getByTestId('canvas-pdf-mode-text'));
    await waitFor(() => expect(screen.getByTestId('canvas-pdf-text-pane')).toHaveTextContent('SSN: 123-45-6789 visible'));
    expect(mockApi.extractText).toHaveBeenCalledWith('c1', false);
    fireEvent.click(screen.getByTestId('canvas-pdf-ocr-toggle'));
    await waitFor(() => expect(mockApi.extractText).toHaveBeenCalledWith('c1', true));
  });

  it('form pane lists fields and saves values as a new version', async () => {
    mockApi.getFormFields.mockResolvedValue({ fields: { po_number: { type: '/Tx', value: 'PO-1' } } });
    mockApi.setFormFields.mockResolvedValue({ state: makeState({ file: { hash: 'c'.repeat(64), page_count: 1, size_bytes: 10, filename: 'po.pdf' } }) });
    render(<PdfFileCanvas canvasId="c1" data={makeState({ file: { hash: 'a'.repeat(64), page_count: 1, size_bytes: 10, filename: 'po.pdf' } })} />);
    fireEvent.click(screen.getByTestId('canvas-pdf-mode-form'));
    await waitFor(() => expect(screen.getByTestId('canvas-pdf-field-po_number')).toHaveValue('PO-1'));
    fireEvent.change(screen.getByTestId('canvas-pdf-field-po_number'), { target: { value: 'PO-9' } });
    fireEvent.click(screen.getByTestId('canvas-pdf-form-save'));
    await waitFor(() => expect(mockApi.setFormFields).toHaveBeenCalledWith('c1', { po_number: 'PO-9' }, 'a'.repeat(64)));
  });

  it('redact locates pages client-side and sends per-page items', async () => {
    mockApi.redactText.mockResolvedValue({ state: makeState() });
    render(<PdfFileCanvas canvasId="c1" data={makeState()} />);
    await screen.findByTestId('canvas-pdf-page-1');
    fireEvent.click(screen.getByTestId('canvas-pdf-redact-open'));
    fireEvent.change(screen.getByTestId('canvas-pdf-redact-input'), { target: { value: 'SSN: 123-45-6789\npublic line' } });
    fireEvent.click(screen.getByTestId('canvas-pdf-redact-apply'));
    await waitFor(() => expect(mockApi.redactText).toHaveBeenCalledWith('c1', [
      { page: 0, text: 'SSN: 123-45-6789' },
      { page: 1, text: 'public line' },
    ]));
  });

  it('redact refuses targets that are not in the document', async () => {
    render(<PdfFileCanvas canvasId="c1" data={makeState()} />);
    await screen.findByTestId('canvas-pdf-page-1');
    fireEvent.click(screen.getByTestId('canvas-pdf-redact-open'));
    fireEvent.change(screen.getByTestId('canvas-pdf-redact-input'), { target: { value: 'not-in-doc' } });
    fireEvent.click(screen.getByTestId('canvas-pdf-redact-apply'));
    await waitFor(() => expect(screen.getByTestId('canvas-pdf-error')).toHaveTextContent('Not found in the document: not-in-doc'));
    expect(mockApi.redactText).not.toHaveBeenCalled();
  });

  it('sign stamps signature lines with attribution', async () => {
    mockApi.stampSignature.mockResolvedValue({ state: makeState() });
    render(<PdfFileCanvas canvasId="c1" data={makeState()} />);
    await screen.findByTestId('canvas-pdf-page-1');
    fireEvent.click(screen.getByTestId('canvas-pdf-sign-open'));
    fireEvent.change(screen.getByTestId('canvas-pdf-sign-lines'), { target: { value: 'Rishi P.' } });
    fireEvent.click(screen.getByTestId('canvas-pdf-sign-apply'));
    await waitFor(() => expect(mockApi.stampSignature).toHaveBeenCalledWith('c1', ['Rishi P.'], expect.stringContaining('Signed')));
  });
});
