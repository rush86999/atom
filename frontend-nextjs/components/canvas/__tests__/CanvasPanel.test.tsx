/**
 * CanvasPanel Component Tests (components/canvas/CanvasPanel.tsx)
 *
 * Tests verify the real CanvasPanel rendering + save + AI accessibility:
 * - renders nothing before any canvas message arrives
 * - canvas:update / canvas:present renders title, version, component badge
 *   and content for markdown/code/email/sheet/snapshot/browser_view
 * - action: "close" clears the canvas
 * - editing content marks unsaved changes; Save POSTs to /api/artifacts
 *   (create) or /api/artifacts/update (existing id) and shows "Synced to
 *   cloud" with the updated version
 * - email canvas: editable To/Subject + Send via /api/canvas/email/send
 *   (deterministic policy path); Save embeds metadata
 * - sheet canvas: editable cells, Add New Row, Save serializes the grid
 * - window.atom.canvas.getState() exposes the AI accessibility state for
 *   each canvas type (markdown/code/sheet/email) via the real
 *   useCanvasStateRegistration hook
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

jest.mock('@monaco-editor/react', () => ({
  __esModule: true,
  default: ({ value, onChange }: any) => (
    <textarea
      data-testid="canvas-editor"
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
    />
  ),
}));

import { CanvasPanel } from '../CanvasPanel';

interface CanvasMessage {
  type: string;
  data?: any;
}

describe('CanvasPanel', () => {
  let savedArtifacts: any[];
  let alertSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    savedArtifacts = [];
    delete (window as any).atom;

    server.resetHandlers();
    server.use(
      rest.post('/api/artifacts', async (req, res, ctx) => {
        savedArtifacts.push(req.body);
        return res(ctx.status(200), ctx.json({ id: 'art-new', version: 1 }));
      }),
      rest.post('/api/artifacts/update', async (req, res, ctx) => {
        savedArtifacts.push(req.body);
        return res(ctx.status(200), ctx.json({ id: (req.body as any).id, version: 9 }));
      })
    );
  });

  afterEach(() => {
    alertSpy?.mockRestore();
  });

  const send = (msg: CanvasMessage) => {
    const { rerender } = render(<CanvasPanel lastMessage={null} />);
    rerender(<CanvasPanel lastMessage={msg} />);
    return rerender;
  };

  it('renders nothing until a canvas message arrives', () => {
    render(<CanvasPanel lastMessage={null} />);
    expect(document.body.textContent).toBe('');
  });

  it('renders a markdown canvas with title, version and content', async () => {
    send({
      type: 'canvas:present',
      data: {
        action: 'present',
        component: 'markdown',
        title: 'Release Notes',
        data: '**Hello** world',
        id: 'art-1',
        version: 3,
      },
    });

    expect(await screen.findByText('Release Notes')).toBeInTheDocument();
    expect(screen.getByText('v3')).toBeInTheDocument();
    expect(screen.getByText('markdown')).toBeInTheDocument();
    expect(screen.getByTestId('canvas-editor')).toHaveValue('**Hello** world');
  });

  it('closes the canvas when the action is close', () => {
    const { rerender } = render(<CanvasPanel lastMessage={null} />);
    rerender(
      <CanvasPanel
        lastMessage={{
          type: 'canvas:update',
          data: { action: 'present', component: 'markdown', title: 'Doc', data: 'x', id: 'art-1' },
        }}
      />
    );
    expect(screen.getByText('Doc')).toBeInTheDocument();

    rerender(
      <CanvasPanel lastMessage={{ type: 'canvas:update', data: { action: 'close' } }} />
    );
    expect(screen.queryByText('Doc')).not.toBeInTheDocument();
  });

  it('editing content shows Save and POSTs a create artifact on save', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'markdown',
        title: 'Draft Doc',
        data: 'initial',
      },
    });

    const editor = await screen.findByTestId('canvas-editor');
    // no id → no "Synced to cloud" initially
    expect(screen.queryByText('Synced to cloud')).not.toBeInTheDocument();
    expect(screen.queryByText('Save Changes')).not.toBeInTheDocument();

    fireEvent.change(editor, { target: { value: 'updated content' } });

    expect(await screen.findByText('Save Changes')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Save Changes'));

    await waitFor(() => expect(savedArtifacts).toHaveLength(1));
    expect(savedArtifacts[0]).toEqual({
      id: undefined,
      name: 'Draft Doc',
      type: 'markdown',
      content: 'updated content',
      session_id: undefined,
    });

    // save success → synced indicator with new version
    expect(await screen.findByText('Synced to cloud')).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();
  });

  it('POSTs to the update endpoint when the canvas already has an id', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'markdown',
        title: 'Existing Doc',
        data: 'v1 content',
        id: 'art-1',
        version: 2,
      },
    });

    // id present + no changes → synced indicator
    expect(await screen.findByText('Synced to cloud')).toBeInTheDocument();

    fireEvent.change(await screen.findByTestId('canvas-editor'), {
      target: { value: 'v2 content' },
    });
    fireEvent.click(await screen.findByText('Save Changes'));

    await waitFor(() => expect(savedArtifacts).toHaveLength(1));
    expect(savedArtifacts[0]).toEqual({
      id: 'art-1',
      name: 'Existing Doc',
      type: 'markdown',
      content: 'v2 content',
      session_id: undefined,
    });
    expect(await screen.findByText('v9')).toBeInTheDocument();
  });

  it('renders an email canvas with editable metadata and sends via the policy API', async () => {
    alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {});
    const sentEmails: any[] = [];
    server.use(
      rest.post('*/api/canvas/email/send', async (req, res, ctx) => {
        sentEmails.push(req.body);
        return res(ctx.status(200), ctx.json({ success: true, status: 'sent' }));
      })
    );
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'email',
        title: 'Follow-up',
        data: { content: 'Hi there' },
        metadata: { to: 'boss@corp.com', subject: 'Q3 numbers' },
        id: 'mail-1',
        version: 1,
      },
    });

    expect(await screen.findByText('Follow-up')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('recipient@example.com')).toHaveValue('boss@corp.com');
    expect(screen.getByPlaceholderText('Email Subject')).toHaveValue('Q3 numbers');

    fireEvent.change(screen.getByPlaceholderText('Email Subject'), {
      target: { value: 'Q3 numbers v2' },
    });
    fireEvent.click(screen.getByText('Send'));

    // Send now posts the composed email through the deterministic policy
    // endpoint instead of the old stub alert.
    await waitFor(() => expect(sentEmails).toHaveLength(1));
    expect(sentEmails[0]).toMatchObject({
      to: ['boss@corp.com'],
      subject: 'Q3 numbers v2',
      body: 'Hi there',
      canvas_id: 'mail-1',
    });

    // Save embeds email metadata
    fireEvent.click(screen.getByText('Save Changes'));
    await waitFor(() => expect(savedArtifacts).toHaveLength(1));
    expect(savedArtifacts[0].metadata).toEqual({
      to: 'boss@corp.com',
      subject: 'Q3 numbers v2',
    });
  });

  it('renders a sheet canvas, edits a cell, adds a row, and saves the grid', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'sheet',
        title: 'Budget',
        data: [
          ['Revenue', '1000'],
          ['Costs', '400'],
        ],
        id: 'sheet-1',
      },
    });

    expect(await screen.findByText('Budget')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Revenue')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1000')).toBeInTheDocument();

    fireEvent.click(screen.getByText('+ Add New Row'));
    // 3 rows now
    const rows = document.querySelectorAll('tbody tr');
    expect(rows.length).toBe(4); // 3 data rows + add-row cell

    fireEvent.change(screen.getByDisplayValue('400'), { target: { value: '500' } });

    fireEvent.click(screen.getByText('Save Changes'));

    await waitFor(() => expect(savedArtifacts).toHaveLength(1));
    expect(savedArtifacts[0].type).toBe('sheet');
    expect(savedArtifacts[0].content).toBe(
      JSON.stringify([
        ['Revenue', '1000'],
        ['Costs', '500'],
        ['', ''],
      ])
    );
  });

  it('renders a snapshot canvas with the state tree JSON', async () => {
    send({
      type: 'canvas:present',
      data: {
        action: 'present',
        component: 'snapshot',
        title: 'Screen grab',
        data: { timestamp: '2026-08-07T10:00:00.000Z', source: 'browser', state: { url: 'https://x' } },
      },
    });

    expect(await screen.findByText('State Tree')).toBeInTheDocument();
    expect(screen.getByText(/Captured:/)).toBeInTheDocument();
    expect(screen.getByText(/Source: browser/)).toBeInTheDocument();
    expect(screen.getByText(/"url": "https:\/\/x"/)).toBeInTheDocument();
  });

  it('renders a browser_view canvas with the url and connecting state', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'browser_view',
        title: 'Live page',
        data: { url: 'https://example.com' },
      },
    });

    expect(await screen.findByText('Live page')).toBeInTheDocument();
    expect(screen.getByText('https://example.com')).toBeInTheDocument();
    expect(screen.getByText('Connecting to remote browser...')).toBeInTheDocument();
  });

  it('registers AI accessibility state for markdown canvases', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'markdown',
        title: 'Doc',
        data: '**Bold** text',
        id: 'art-1',
      },
    });

    await waitFor(() => {
      const state = (window as any).atom.canvas.getState('art-1');
      expect(state).toMatchObject({
        type: 'generic',
        component: 'markdown',
        title: 'Doc',
        text: '**Bold** text',
      });
      expect(state.html).toContain('<strong>Bold</strong>');
    });
  });

  it('registers AI accessibility state for code canvases (eval mapped to code)', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'eval',
        title: 'script.py',
        data: { language: 'python', content: 'x = 1' },
        id: 'code-1',
      },
    });

    await waitFor(() => {
      expect((window as any).atom.canvas.getState('code-1')).toEqual({
        type: 'coding',
        language: 'python',
        code: 'x = 1',
        filename: 'script.py',
      });
    });
  });

  it('registers AI accessibility state for sheet canvases with live cell edits', async () => {
    const rerender = send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'sheet',
        title: 'Sheet1',
        data: [['a', 'b']],
        id: 'sheet-1',
      },
    });

    await waitFor(() => {
      expect((window as any).atom.canvas.getState('sheet-1')).toEqual({
        type: 'sheets',
        cells: [['a', 'b']],
        sheetName: 'Sheet1',
        activeCell: null,
      });
    });

    fireEvent.change(screen.getByDisplayValue('a'), { target: { value: 'zed' } });

    await waitFor(() => {
      const state = (window as any).atom.canvas.getState('sheet-1');
      expect(state.cells).toEqual([['zed', 'b']]);
    });

    // rerender with a new message must not crash the registration
    rerender(
      <CanvasPanel
        lastMessage={{ type: 'canvas:update', data: { action: 'close' } }}
      />
    );
    await act(async () => {});
    expect((window as any).atom.canvas.getState('sheet-1')).toBeNull();
  });

  it('registers AI accessibility state for email canvases', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'email',
        title: 'Draft',
        data: { content: 'body text' },
        metadata: { to: 'a@b.c', subject: 'Hi' },
        id: 'mail-1',
      },
    });

    await waitFor(() => {
      expect((window as any).atom.canvas.getState('mail-1')).toEqual({
        type: 'email',
        to: 'a@b.c',
        subject: 'Hi',
        body: 'body text',
        draft: false,
      });
    });
  });

  it('closes the canvas when the X button is clicked', async () => {
    send({
      type: 'canvas:update',
      data: { action: 'present', component: 'markdown', title: 'Doc', data: 'x' },
    });
    expect(await screen.findByText('Doc')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Close canvas' }));
    expect(screen.queryByText('Doc')).not.toBeInTheDocument();
  });

  it('toggles preview mode for markdown canvases', async () => {
    send({
      type: 'canvas:update',
      data: { action: 'present', component: 'markdown', title: 'Doc', data: '**Bold** text' },
    });
    expect(await screen.findByText('Doc')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Preview Mode'));
    // rendered HTML via renderMarkdownSafe
    expect(screen.getByText('Bold')).toBeInTheDocument();
    expect(screen.queryByTestId('canvas-editor')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Edit Mode'));
    expect(screen.getByTestId('canvas-editor')).toBeInTheDocument();
  });

  it('registers AI accessibility state for document canvases', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'document',
        title: 'Doc',
        data: 'body text',
        id: 'doc-1',
      },
    });

    await waitFor(() => {
      expect((window as any).atom.canvas.getState('doc-1')).toEqual({
        type: 'docs',
        title: 'Doc',
        format: 'docx',
        sections: [{ heading: 'Content', body: 'body text' }],
      });
    });
  });

  it('registers AI accessibility state for status_panel canvases', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'status_panel',
        title: 'Status',
        data: 'All systems go',
        id: 'st-1',
      },
    });

    await waitFor(() => {
      expect((window as any).atom.canvas.getState('st-1')).toEqual({
        type: 'generic',
        component: 'status_panel',
        title: 'Status',
        text: 'All systems go',
      });
    });
  });

  it('tracks email body edits in the AI accessibility state', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'email',
        title: 'Draft',
        data: { content: 'body' },
        metadata: { to: 'a@b.c', subject: 'Hi' },
        id: 'mail-1',
      },
    });

    await waitFor(() => {
      expect((window as any).atom.canvas.getState('mail-1')).toMatchObject({
        type: 'email',
        body: 'body',
        draft: false,
      });
    });

    fireEvent.change(screen.getByTestId('canvas-editor'), { target: { value: 'body v2' } });

    await waitFor(() => {
      expect((window as any).atom.canvas.getState('mail-1')).toMatchObject({
        body: 'body v2',
        draft: true,
      });
    });
  });

  it('saves edited To metadata with the email artifact', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'email',
        title: 'Follow-up',
        data: { content: 'hi' },
        metadata: { to: 'old@corp.com', subject: 'Q3 numbers' },
        id: 'mail-2',
      },
    });

    expect(await screen.findByText('Follow-up')).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText('recipient@example.com'), {
      target: { value: 'new@corp.com' },
    });
    fireEvent.click(screen.getByText('Save Changes'));

    await waitFor(() => expect(savedArtifacts).toHaveLength(1));
    expect(savedArtifacts[0].metadata).toEqual({
      to: 'new@corp.com',
      subject: 'Q3 numbers',
    });
  });

  it('logs the error and re-enables Save when the artifact save fails', async () => {
    server.use(
      rest.post('/api/artifacts', (req, res, ctx) => res.networkError('boom'))
    );
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    send({
      type: 'canvas:update',
      data: { action: 'present', component: 'markdown', title: 'Doc', data: 'x' },
    });
    const editor = await screen.findByTestId('canvas-editor');
    fireEvent.change(editor, { target: { value: 'y' } });
    fireEvent.click(await screen.findByText('Save Changes'));

    await waitFor(() => expect(errorSpy).toHaveBeenCalled());
    expect(screen.queryByText('Synced to cloud')).not.toBeInTheDocument();
    expect(screen.getByText('Save Changes').closest('button')).not.toBeDisabled();

    errorSpy.mockRestore();
  });

  it('renders a browser_view canvas with a screenshot when provided', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'browser_view',
        title: 'Live page',
        data: { url: 'https://example.com', screenshot: 'aGVsbG8=' },
      },
    });

    expect(await screen.findByText('Live page')).toBeInTheDocument();
    const img = screen.getByAltText('Browser Snapshot');
    expect(img).toHaveAttribute('src', 'data:image/png;base64,aGVsbG8=');
    expect(screen.queryByText('Connecting to remote browser...')).not.toBeInTheDocument();
  });

  it('shows a no-data fallback for string components without data', async () => {
    send({
      type: 'canvas:update',
      data: { action: 'present', component: 'markdown', title: 'Doc' },
    });

    expect(await screen.findByText('No data to display')).toBeInTheDocument();
  });

  it('keeps the canvas open and unsynced when the save is rejected', async () => {
    server.use(
      rest.post('/api/artifacts', (req, res, ctx) => res(ctx.status(500), ctx.json({})))
    );

    send({
      type: 'canvas:update',
      data: { action: 'present', component: 'markdown', title: 'Doc', data: 'x' },
    });
    const editor = await screen.findByTestId('canvas-editor');
    fireEvent.change(editor, { target: { value: 'y' } });
    fireEvent.click(await screen.findByText('Save Changes'));

    await waitFor(() => expect(savedArtifacts).toHaveLength(0));
    expect(screen.getByText('Doc')).toBeInTheDocument();
    expect(screen.queryByText('Synced to cloud')).not.toBeInTheDocument();
    // save button re-enabled after the rejected request
    await waitFor(() =>
      expect(screen.getByText('Save Changes').closest('button')).not.toBeDisabled()
    );
  });

  it('renders the custom fallback for unknown components with raw data', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'custom',
        title: 'Widget',
        data: { foo: 'bar' },
      },
    });

    expect(await screen.findByText('Custom Component: custom')).toBeInTheDocument();
    expect(screen.getByText('Rendering raw data payload')).toBeInTheDocument();
    expect(screen.getByText(/"foo": "bar"/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: chart canvases, data resolution branches, form component
// ---------------------------------------------------------------------------
describe('CanvasPanel (extended coverage)', () => {
  const send = (msg: any) => {
    const { rerender } = render(<CanvasPanel lastMessage={null} />);
    rerender(<CanvasPanel lastMessage={msg} />);
    return rerender;
  };

  const chartRow = { label: 'Jan', value: 10 };

  it('renders a line_chart canvas from a raw array payload with canvas title', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'line_chart',
        title: 'Growth',
        data: [chartRow, { label: 'Feb', value: 20 }],
        id: 'line-1',
      },
    });

    // The chart title renders twice: header badge + chart canvas title,
    // proving resolveChartTitle fell through to the canvas title.
    expect((await screen.findAllByText('Growth')).length).toBeGreaterThan(1);
  });

  it('renders a bar_chart canvas from a {content: [...]} payload with embedded title', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'bar_chart',
        title: 'Ignored Canvas Title',
        data: { content: [chartRow, { label: 'Feb', value: 5 }], title: 'Embedded Title' },
        id: 'bar-1',
      },
    });

    // embedded data.title wins over the canvas title
    expect((await screen.findAllByText('Embedded Title')).length).toBeGreaterThan(0);
    // the header badge still shows the canvas title
    expect(screen.getByText('Ignored Canvas Title')).toBeInTheDocument();
  });

  it('renders a pie_chart canvas from a {data: [...]} payload', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'pie_chart',
        title: 'Split',
        data: { data: [{ name: 'A', value: 1 }, { name: 'B', value: 2 }] },
        id: 'pie-1',
      },
    });

    expect((await screen.findAllByText('Split')).length).toBeGreaterThan(0);
  });

  it('renders a chart title from a nested content.title', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'bar_chart',
        data: { content: { title: 'Nested Title', data: [chartRow] } },
        id: 'bar-2',
      },
    });

    expect(await screen.findByText('Nested Title')).toBeInTheDocument();
  });

  let submittedForms: any[] = [];

  it('renders a form canvas from a {content: {schema}} payload and submits it', async () => {
    submittedForms = [];
    server.use(
      rest.post('*/api/canvas/submit', (req, res, ctx) => {
        submittedForms.push(req.body);
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'form',
        title: 'Survey',
        data: {
          content: {
            title: 'Embedded Survey',
            schema: { fields: [{ name: 'q1', label: 'Question 1', type: 'text' }] },
          },
        },
        id: 'form-1',
      },
    });

    expect(await screen.findByText('Embedded Survey')).toBeInTheDocument();
    expect(screen.getByText('Question 1')).toBeInTheDocument();

    // submitting the form POSTs to /api/canvas/submit via the panel's
    // onSubmit handler
    const input = screen.getByLabelText(/Question 1/i);
    fireEvent.change(input, { target: { value: 'answer 1' } });
    fireEvent.click(screen.getByRole('button', { name: /submit/i }));
    await waitFor(() => {
      expect(submittedForms).toHaveLength(1);
    });
    expect(submittedForms[0]).toMatchObject({ canvas_id: 'form-1' });
  });

  it('logs and rethrows when the form submission fails', async () => {
    server.use(
      rest.post('*/api/canvas/submit', (req, res) => res.networkError('down'))
    );
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'form',
        title: 'Broken',
        data: { fields: [{ name: 'q', label: 'Q', type: 'text', required: false }] },
        id: 'form-3',
      },
    });

    const input = await screen.findByLabelText(/Q/i);
    fireEvent.change(input, { target: { value: 'x' } });
    fireEvent.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Form submission failed:', expect.anything());
    });
    errorSpy.mockRestore();
  });

  it('renders a form canvas from a top-level fields array', async () => {
    send({
      type: 'canvas:update',
      data: {
        action: 'present',
        component: 'form',
        title: 'Signup',
        data: { fields: [{ name: 'email', label: 'Email', type: 'email' }] },
        id: 'form-2',
      },
    });

    expect((await screen.findAllByText('Signup')).length).toBeGreaterThan(0);
    expect(screen.getByText('Email')).toBeInTheDocument();
  });

  it('shows the no-data fallback for chart canvases without data', async () => {
    send({
      type: 'canvas:update',
      data: { action: 'present', component: 'line_chart', title: 'Empty' },
    });

    expect(await screen.findByText('No data to display')).toBeInTheDocument();
  });
});
