/**
 * CanvasHost Component Tests
 *
 * Tests verify CanvasHost renders and reacts to canvas:present, canvas:update,
 * and action:close message types. Covers email metadata, sheet data, and save behavior.
 *
 * Source: components/chat/canvas-host.tsx (93 lines, 0% coverage)
 */

import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { CanvasHost } from '../canvas-host';

// Mock marked to avoid ESM import issues
jest.mock('marked', () => ({
  marked: {
    parse: jest.fn((s: string) => s),
  },
}));

// Mock Monaco editor to avoid heavy import
jest.mock('@monaco-editor/react', () => ({
  __esModule: true,
  default: ({ value, onChange }: any) => (
    <div data-testid="mock-editor">
      <textarea
        data-testid="editor-content"
        defaultValue={value}
        onChange={(e) => onChange?.(e.target.value)}
      />
    </div>
  ),
}));

// Mock the chart canvases and interactive form (heavy children)
jest.mock('@/components/canvas/LineChart', () => ({
  LineChartCanvas: ({ data, title }: any) => (
    <div data-testid="line-chart">
      line-title:{title} rows:{data.length}
    </div>
  ),
}));
jest.mock('@/components/canvas/BarChart', () => ({
  BarChartCanvas: ({ data, title }: any) => (
    <div data-testid="bar-chart">
      bar-title:{title} rows:{data.length}
    </div>
  ),
}));
jest.mock('@/components/canvas/PieChart', () => ({
  PieChartCanvas: ({ data, title }: any) => (
    <div data-testid="pie-chart">
      pie-title:{title} rows:{data.length}
    </div>
  ),
}));
jest.mock('@/components/canvas/InteractiveForm', () => ({
  InteractiveForm: ({ fields, title, onSubmit }: any) => (
    <div data-testid="interactive-form">
      form-title:{title} fields:{fields.length}
      <button
        onClick={() => {
          // Swallow rejections: the component rethrows submission errors on
          // purpose and the unhandled rejection would fail the test run.
          Promise.resolve(onSubmit({ name: 'x' })).catch(() => {});
        }}
      >
        submit-form
      </button>
    </div>
  ),
}));

const mockApiPost = jest.fn();
const mockApiPut = jest.fn();
jest.mock('@/lib/api', () => ({
  apiClient: {
    post: (...args: any[]) => mockApiPost(...args),
    put: (...args: any[]) => mockApiPut(...args),
  },
}));

// Use the mockFetch that setup.ts exports on global scope
const getMockFetch = () => (global as any).mockFetch as jest.Mock;

describe('CanvasHost', () => {
  beforeEach(() => {
    // jest config has clearMocks, resetMocks, restoreMocks so we need to re-setup fetch spy
    jest.spyOn(global, 'fetch').mockResolvedValue(
      (global as any).createMockResponse() as any
    );
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  // Test 1: renders nothing when lastMessage is null
  test('renders nothing when lastMessage is null', () => {
    const { container } = render(<CanvasHost lastMessage={null} />);
    expect(container.innerHTML).toBe('');
  });

  // Test 2: renders markdown canvas on canvas:present message
  test('renders markdown canvas on canvas:present message', () => {
    const message = {
      type: 'canvas:present',
      data: {
        component: 'markdown',
        title: 'Test Doc',
        data: { content: '# Hello World' },
      },
    };

    render(<CanvasHost lastMessage={message} />);

    expect(screen.getByText('Test Doc')).toBeInTheDocument();
    expect(screen.getByText('markdown')).toBeInTheDocument();
  });

  // Test 3: renders code component on eval type
  test('renders code component on eval type', () => {
    const message = {
      type: 'canvas:update',
      data: {
        component: 'eval',
        title: 'Code',
        data: { content: 'print("hello")' },
      },
    };

    render(<CanvasHost lastMessage={message} />);

    expect(screen.getByText('Code')).toBeInTheDocument();
    expect(screen.getByText('code')).toBeInTheDocument();
  });

  // Test 4: closes canvas on action:close
  test('closes canvas on action:close', () => {
    const { rerender } = render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: { component: 'markdown', title: 'Test', data: { content: 'Hello' } },
        }}
      />
    );

    expect(screen.getByText('Test')).toBeInTheDocument();

    // Rerender with close action
    rerender(
      <CanvasHost
        lastMessage={{
          type: 'canvas:update',
          data: { action: 'close' },
        }}
      />
    );

    expect(screen.queryByText('Test')).not.toBeInTheDocument();
  });

  // Test 5: handles email component metadata
  test('handles email component metadata', () => {
    const message = {
      type: 'canvas:present',
      data: {
        component: 'email',
        title: 'New Email',
        data: { content: 'Hello via email' },
        metadata: { to: 'test@example.com', subject: 'Test Subject' },
      },
    };

    render(<CanvasHost lastMessage={message} />);

    expect(screen.getByText('New Email')).toBeInTheDocument();
    expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Test Subject')).toBeInTheDocument();
  });

  // Test 6: handles sheet component data
  test('handles sheet component data with rows', () => {
    const message = {
      type: 'canvas:present',
      data: {
        component: 'sheet',
        title: 'Sheet 1',
        data: { rows: [['a', 'b'], ['c', 'd']] },
      },
    };

    render(<CanvasHost lastMessage={message} />);

    expect(screen.getByText('Sheet 1')).toBeInTheDocument();
    expect(screen.getByText('sheet')).toBeInTheDocument();
    // Sheet has input fields for each cell
    expect(screen.getByDisplayValue('a')).toBeInTheDocument();
    expect(screen.getByDisplayValue('b')).toBeInTheDocument();
  });

  // Test 7: handleSave triggers save API call
  test('handleSave triggers save API call', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch').mockResolvedValue(
      (global as any).createMockResponse({
        ok: true,
        json: async () => ({ id: 'artifact-1', version: 2 }),
      }) as any
    );

    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: {
            component: 'sheet',
            title: 'Sheet',
            data: { rows: [['x', 'y']] },
          },
        }}
      />
    );

    const saveButton = screen.getByText('Save Changes');
    expect(saveButton).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(saveButton);
    });

    expect(fetchSpy).toHaveBeenCalled();
    const callUrl = fetchSpy.mock.calls[0][0];
    expect(callUrl).toContain('/api/artifacts');
  });

  // Test 8: handleSave does nothing when state is null
  test('handleSave does nothing when state is null', () => {
    const fetchSpy = jest.spyOn(global, 'fetch');

    // No canvas message passed - state remains null
    render(<CanvasHost lastMessage={null} />);

    // Save button should not exist since canvas is not open
    expect(screen.queryByText('Save Changes')).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: every canvas component type, preview mode, save variants
// ---------------------------------------------------------------------------
describe('CanvasHost (extended coverage)', () => {
  let errorSpy: jest.SpyInstance;

  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(global, 'fetch').mockResolvedValue(
      (global as any).createMockResponse() as any
    );
    mockApiPost.mockReset();
    mockApiPost.mockResolvedValue({ ok: true });
  });

  afterEach(() => {
    errorSpy.mockRestore();
    jest.restoreAllMocks();
  });

  const canvasMessage = (overrides: Record<string, unknown> = {}) => ({
    type: 'canvas:present',
    data: {
      component: 'markdown',
      title: 'Canvas',
      data: { content: '# Hello' },
      ...overrides,
    },
  });

  test('renders chart canvases resolving data from all payload shapes', () => {
    const { rerender } = render(
      <CanvasHost
        lastMessage={canvasMessage({
          component: 'line_chart',
          data: [{ x: 1 }, { x: 2 }],
        })}
      />
    );
    // raw array data + canvasTitle fallback
    expect(screen.getByTestId('line-chart')).toHaveTextContent(
      'line-title:Canvas rows:2'
    );

    // {data: [...]} shape with explicit title
    rerender(
      <CanvasHost
        lastMessage={canvasMessage({
          component: 'bar_chart',
          data: { title: 'Revenue', data: [{ y: 1 }] },
        })}
      />
    );
    expect(screen.getByTestId('bar-chart')).toHaveTextContent(
      'bar-title:Revenue rows:1'
    );

    // {content: [...]} shape (PUT update flow)
    rerender(
      <CanvasHost
        lastMessage={canvasMessage({
          component: 'pie_chart',
          data: { title: 'FromContent', content: [{ z: 3 }] },
        })}
      />
    );
    expect(screen.getByTestId('pie-chart')).toHaveTextContent(
      'pie-title:FromContent rows:1'
    );
  });

  test('renders a form canvas and submits through the api client', async () => {
    render(
      <CanvasHost
        lastMessage={canvasMessage({
          component: 'form',
          title: 'Signup',
          data: { schema: { fields: [{ name: 'email' }] } },
        })}
      />
    );

    expect(screen.getByTestId('interactive-form')).toHaveTextContent(
      'form-title:Signup fields:1'
    );

    fireEvent.click(screen.getByText('submit-form'));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        '/api/canvas/submit',
        expect.objectContaining({ form_data: { name: 'x' } })
      );
    });
  });

  test('unwraps {content: {...}} form payloads and unwrapped fields', () => {
    const { rerender } = render(
      <CanvasHost
        lastMessage={canvasMessage({
          component: 'form',
          data: { content: { fields: [{ name: 'a' }, { name: 'b' }] } },
        })}
      />
    );
    expect(screen.getByTestId('interactive-form')).toHaveTextContent('fields:2');

    rerender(
      <CanvasHost
        lastMessage={canvasMessage({
          component: 'form',
          data: { fields: [{ name: 'only' }] },
        })}
      />
    );
    expect(screen.getByTestId('interactive-form')).toHaveTextContent('fields:1');
  });

  test('form submission failures are logged and rethrown', async () => {
    mockApiPost.mockRejectedValue(new Error('post failed'));

    render(
      <CanvasHost
        lastMessage={canvasMessage({
          component: 'form',
          data: { fields: [{ name: 'a' }] },
        })}
      />
    );

    fireEvent.click(screen.getByText('submit-form'));

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith(
        'Form submission failed:',
        expect.any(Error)
      );
    });
  });

  test('email canvas: editing metadata marks unsaved, Send posts to the policy-gated email API, save posts metadata', async () => {
    const alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {});
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchSpy = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(
        (global as any).createMockResponse({
          ok: true,
          json: async () => ({ id: 'artifact-2', version: 5 }),
        }) as any
      );
    // The Send action goes through the real policy-gated endpoint
    // (/api/canvas/email/send) — apiClient is mocked at the module level.
    mockApiPost.mockResolvedValue({ data: { success: true, status: 'sent' } });

    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: {
            id: 'canvas-9',
            component: 'email',
            title: 'Draft',
            data: { content: 'Body text' },
            metadata: { to: 'a@b.com', subject: 'Hi' },
          },
        }}
      />
    );

    // editing the To field marks the canvas dirty
    fireEvent.change(screen.getByPlaceholderText('recipient@example.com'), {
      target: { value: 'c@d.com' },
    });

    const send = screen.getByRole('button', { name: /send/i });
    await act(async () => {
      fireEvent.click(send);
    });
    // The confirm click is the policy authorization for the send.
    expect(confirmSpy).toHaveBeenCalledWith('Send email to c@d.com?');
    expect(mockApiPost).toHaveBeenCalledWith('/api/canvas/email/send', {
      to: ['c@d.com'],
      cc: [],
      subject: 'Hi',
      body: 'Body text',
      canvas_id: 'canvas-9',
    });
    expect(alertSpy).toHaveBeenCalledWith('Email sent.');

    await act(async () => {
      fireEvent.click(screen.getByText('Save Changes'));
    });

    // Email persists to the canvas audit trail (PUT /api/canvas/{id}) with
    // the full {to, cc, subject, body} dict — not the legacy artifacts
    // store, which loses To/Cc/Subject on refresh. cc comes from the
    // present payload (this canvas has none) and stays empty.
    expect(mockApiPut).toHaveBeenCalledWith(
      '/api/canvas/canvas-9?canvas_type=email&title=Draft',
      JSON.stringify({ to: 'c@d.com', cc: '', subject: 'Hi', body: 'Body text' }),
      expect.objectContaining({ headers: { 'Content-Type': 'application/json' } }),
    );

    alertSpy.mockRestore();
    confirmSpy.mockRestore();
  });

  test('sheet canvas: cell edits, add row, and save with sheet payload', async () => {
    const fetchSpy = jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(
        (global as any).createMockResponse({
          ok: true,
          json: async () => ({ id: 'artifact-3', version: 1 }),
        }) as any
      );

    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: {
            component: 'sheet',
            title: 'Grid',
            data: [
              ['h1', 'h2'],
              ['v1', 'v2'],
            ],
          },
        }}
      />
    );

    // edit a cell
    fireEvent.change(screen.getByDisplayValue('v1'), { target: { value: 'edited' } });
    expect(screen.getByDisplayValue('edited')).toBeInTheDocument();

    // add a row
    fireEvent.click(screen.getByText('+ Add New Row'));
    const newCell = screen.getAllByRole('textbox');
    expect(newCell.length).toBeGreaterThan(4);

    await act(async () => {
      fireEvent.click(screen.getByText('Save Changes'));
    });

    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toContain('/api/artifacts');
    expect(String(init.body)).toContain('edited');
  });

  test('save failures are logged without crashing', async () => {
    jest.spyOn(global, 'fetch').mockRejectedValue(new Error('save failed'));

    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: { component: 'sheet', title: 'S', data: { rows: [['a']] } },
        }}
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByText('Save Changes'));
    });

    expect(errorSpy).toHaveBeenCalledWith('Error saving artifact:', expect.any(Error));
  });

  test('markdown preview mode renders sanitized html and toggles back', () => {
    render(<CanvasHost lastMessage={canvasMessage({ component: 'markdown' })} />);

    fireEvent.click(screen.getByText('Preview Mode'));
    expect(screen.getByText('Edit Mode')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Edit Mode'));
    expect(screen.getByText('Preview Mode')).toBeInTheDocument();
    expect(screen.getByTestId('mock-editor')).toBeInTheDocument();
  });

  test('renders snapshot canvas with metadata chips and state tree', () => {
    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: {
            component: 'snapshot',
            title: 'Snap',
            data: { timestamp: '2026-08-14T10:00:00Z', source: 'web', state: { a: 1 } },
          },
        }}
      />
    );

    expect(screen.getByText(/Captured:/i)).toBeInTheDocument();
    expect(screen.getByText(/Source: web/i)).toBeInTheDocument();
    expect(screen.getByText(/"a": 1/)).toBeInTheDocument();
  });

  test('renders browser_view canvas with and without a screenshot', () => {
    const { rerender } = render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: {
            component: 'browser_view',
            title: 'Browser',
            data: { url: 'https://example.com', screenshot: 'data:image/png;base64,abc' },
          },
        }}
      />
    );

    expect(screen.getByText('https://example.com')).toBeInTheDocument();
    expect(screen.getByAltText('Browser Snapshot')).toBeInTheDocument();

    rerender(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: {
            component: 'browser_view',
            title: 'Browser',
            data: { url: '' },
          },
        }}
      />
    );
    expect(screen.getByText('Connecting to remote browser...')).toBeInTheDocument();
    expect(screen.getByText('about:blank')).toBeInTheDocument();
  });

  test('renders unknown component types via the custom fallback', () => {
    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: { component: 'status_panel', title: 'Status', data: 'All good' },
        }}
      />
    );
    expect(screen.getByText('status_panel')).toBeInTheDocument();

    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: { component: 'custom_thing', title: 'Custom', data: { payload: 42 } },
        }}
      />
    );
    expect(screen.getByText('Custom Component: custom_thing')).toBeInTheDocument();
    expect(screen.getByText(/"payload": 42/)).toBeInTheDocument();
  });

  test('shows version chip and synced indicator for saved canvases', () => {
    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: {
            id: 'canvas-77',
            canvas_id: 'ignored-canvas-id',
            version: 3,
            component: 'document',
            title: 'Doc',
            data: { content: '# Doc' },
          },
        }}
      />
    );

    expect(screen.getByText('v3')).toBeInTheDocument();
    expect(screen.getByText('Synced to cloud')).toBeInTheDocument();
    // documents expose the Preview Mode toggle too
    expect(screen.getByText('Preview Mode')).toBeInTheDocument();
  });

  test('renders "No data to display" for data-less components', () => {
    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: { component: 'markdown', title: 'Empty', data: undefined },
        }}
      />
    );

    expect(screen.getByText('No data to display')).toBeInTheDocument();
  });

  test('editor changes mark the canvas dirty and enable save', async () => {
    jest
      .spyOn(global, 'fetch')
      .mockResolvedValue(
        (global as any).createMockResponse({
          ok: true,
          json: async () => ({ id: 'artifact-4', version: 2 }),
        }) as any
      );

    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: { component: 'code', title: 'Snippet', data: { content: 'let x = 1;' } },
        }}
      />
    );

    expect(screen.queryByText('Save Changes')).not.toBeInTheDocument();

    fireEvent.change(screen.getByTestId('editor-content'), {
      target: { value: 'let x = 2;' },
    });

    await act(async () => {
      fireEvent.click(screen.getByText('Save Changes'));
    });
    expect(global.fetch).toHaveBeenCalled();
  });
});

describe('CanvasHost event-frame guard (draft-clobber regression)', () => {
  // Regression 2026-08-31: the email_send status broadcast was applied as
  // canvas content — the drafted email vanished from the panel, replaced by
  // {status, payload} JSON. Event frames must never render as content.
  const sendStatusFrame = {
    type: 'canvas:update',
    data: {
      action: 'email_send',
      canvas_id: 'c-email-1',
      canvas_type: 'email',
      component: 'email',
      data: { status: 'failed', payload: { to: ['mark@x.ca'], cc: [], subject: 'Re: Quote' } },
    },
  };

  test('ignores an email_send status frame entirely (no content clobber)', () => {
    const { container } = render(<CanvasHost lastMessage={sendStatusFrame} />);
    // The status payload must not appear as rendered canvas content
    expect(container.innerHTML).not.toContain('email_send');
    expect(container.innerHTML).not.toContain('"failed"');
    expect(container.innerHTML).toBe('');
  });

  test('a real content frame after the status frame still renders', () => {
    const { rerender } = render(<CanvasHost lastMessage={sendStatusFrame} />);
    rerender(
      <CanvasHost
        lastMessage={{
          type: 'canvas:update',
          data: {
            action: 'update',
            canvas_id: 'c-email-1',
            component: 'email',
            title: 'Draft',
            data: { to: 'mark@x.ca', cc: '', subject: 'Re: Quote', body: 'Hi Mark,' },
          },
        }}
      />
    );
    expect(screen.getByText('Draft')).toBeInTheDocument();
  });
});
