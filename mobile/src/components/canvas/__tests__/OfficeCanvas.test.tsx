/**
 * OfficeCanvas Component Tests
 *
 * Native rendering + co-editing for file-backed office canvas snapshots:
 * - office detection (isOfficeContent)
 * - xlsx grid (display values, sheet tabs, formula-cell highlight) with cell
 *   commits on end-editing
 * - docx paragraph editor committing edit_type 'document'
 * - pptx slide title/content edits + Add Slide
 * - read-only mode when no canvas binding is present
 * - sync-update payloads match the web contract exactly
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';

import { OfficeCanvas, isOfficeContent } from '../OfficeCanvas';

jest.mock('../../services/api', () => ({
  apiService: {
    post: jest.fn().mockResolvedValue({ success: true, data: {} }),
  },
}));

import { apiService } from '../../services/api';
const postMock = apiService.post as jest.Mock;

describe('isOfficeContent', () => {
  it('detects office-bound canvases', () => {
    expect(isOfficeContent({ office_file: '/data/office/a.xlsx' })).toBe(true);
    expect(isOfficeContent({ format: 'docx' })).toBe(true);
    expect(isOfficeContent({ format: 'pptx' })).toBe(true);
    expect(isOfficeContent({ format: 'markdown' })).toBe(false);
    expect(isOfficeContent(null)).toBe(false);
    expect(isOfficeContent('text')).toBe(false);
  });
});

describe('OfficeCanvas — xlsx', () => {
  const content = {
    format: 'xlsx',
    title: 'book.xlsx',
    active_sheet: 'Sheet1',
    sheet_names: ['Sheet1'],
    sheets: [{ name: 'Sheet1', rows: [['Item', 'Qty'], ['Widget', 4]] }],
    formulas: {},
  };

  beforeEach(() => {
    postMock.mockReset();
    postMock.mockResolvedValue({ success: true, data: {} });
  });

  it('renders cells as display values with a file header', () => {
    render(<OfficeCanvas content={content} />);
    expect(screen.getByText('book.xlsx')).toBeTruthy();
    expect(screen.getByText('Excel')).toBeTruthy();
    expect(screen.getByDisplayValue('Item')).toBeTruthy();
    expect(screen.getByDisplayValue('Widget')).toBeTruthy();
    expect(screen.getByDisplayValue('4')).toBeTruthy();
  });

  it('switches sheets via tabs', () => {
    const multi = {
      ...content,
      sheet_names: ['Sheet1', 'Summary'],
      sheets: [...content.sheets, { name: 'Summary', rows: [['Total', 90]] }],
    };
    render(<OfficeCanvas content={multi} />);
    expect(screen.getByDisplayValue('Widget')).toBeTruthy();

    fireEvent.press(screen.getByText('Summary'));
    expect(screen.getByDisplayValue('Total')).toBeTruthy();
    expect(screen.queryByDisplayValue('Widget')).toBeNull();
  });

  it('commits an edited cell on end-editing with its cell_path', async () => {
    render(<OfficeCanvas content={content} canvasId="c-1" />);

    const qty = screen.getByDisplayValue('4');
    fireEvent.changeText(qty, '9');
    fireEvent(qty, 'onEndEditing', { nativeEvent: { text: '9' } });

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(postMock.mock.calls[0][0]).toBe('/api/v1/office/sync-update');
    expect(postMock.mock.calls[0][1]).toMatchObject({
      canvas_id: 'c-1',
      file_path: '/data/office/book.xlsx'.replace('/data/office', '') || undefined,
      edit_type: 'cell',
      data: { cell_path: '/Sheet1/B2', value: '9', is_formula: false },
    });
  });

  it('does not POST when nothing changed', () => {
    render(<OfficeCanvas content={content} canvasId="c-1" />);
    const widget = screen.getByDisplayValue('Widget');
    fireEvent(widget, 'onEndEditing', { nativeEvent: { text: 'Widget' } });
    expect(postMock).not.toHaveBeenCalled();
  });

  it('stays read-only without a canvas binding', () => {
    render(<OfficeCanvas content={content} />);
    const qty = screen.getByDisplayValue('4');
    fireEvent.changeText(qty, '9');
    fireEvent(qty, 'onEndEditing', { nativeEvent: { text: '9' } });
    expect(postMock).not.toHaveBeenCalled();
    expect(screen.getByText(/read-only/i)).toBeTruthy();
  });
});

describe('OfficeCanvas — docx', () => {
  beforeEach(() => {
    postMock.mockReset();
    postMock.mockResolvedValue({ success: true, data: {} });
  });

  it('renders and commits the document text', async () => {
    render(
      <OfficeCanvas
        content={{ format: 'docx', title: 'r.docx', text: 'Para one.' }}
        canvasId="c-doc"
      />
    );
    expect(screen.getByText('Word')).toBeTruthy();

    const area = screen.getByDisplayValue('Para one.');
    fireEvent.changeText(area, 'Para one.\nPara two.');
    fireEvent(area, 'onEndEditing');

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(postMock.mock.calls[0][1].edit_type).toBe('document');
    expect(postMock.mock.calls[0][1].data.content).toBe('Para one.\nPara two.');
  });
});

describe('OfficeCanvas — pptx', () => {
  const pptx = {
    format: 'pptx',
    title: 'deck.pptx',
    slides: [{ slide_number: 1, title: 'Intro', content: 'Body text' }],
  };

  beforeEach(() => {
    postMock.mockReset();
    postMock.mockResolvedValue({ success: true, data: {} });
  });

  it('renders slide cards', () => {
    render(<OfficeCanvas content={pptx} />);
    expect(screen.getByText('PowerPoint')).toBeTruthy();
    expect(screen.getByDisplayValue('Intro')).toBeTruthy();
    expect(screen.getByDisplayValue('Body text')).toBeTruthy();
  });

  it('commits slide title edits', async () => {
    render(<OfficeCanvas content={pptx} canvasId="c-deck" />);

    const title = screen.getByDisplayValue('Intro');
    fireEvent.changeText(title, 'Agenda');
    fireEvent(title, 'onEndEditing', { nativeEvent: { text: 'Agenda' } });

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(postMock.mock.calls[0][1].edit_type).toBe('slide');
    expect(postMock.mock.calls[0][1].data).toMatchObject({
      slide_number: 1,
      title: 'Agenda',
      content: 'Body text',
    });
  });

  it('adds a slide via the Add Slide button', async () => {
    render(<OfficeCanvas content={pptx} canvasId="c-deck" />);

    fireEvent.press(screen.getByText('+ ADD SLIDE'));

    await waitFor(() => expect(postMock).toHaveBeenCalled());
    expect(postMock.mock.calls[0][1].edit_type).toBe('add_slide');
    expect(postMock.mock.calls[0][1].data.title).toBe('New Slide');
  });
});

describe('OfficeCanvas — unsupported', () => {
  it('shows a graceful fallback', () => {
    render(<OfficeCanvas content={{ format: 'odp' }} />);
    expect(screen.getByText(/unsupported office format/i)).toBeTruthy();
  });
});
