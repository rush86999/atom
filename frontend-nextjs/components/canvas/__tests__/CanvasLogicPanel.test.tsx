/**
 * CanvasLogicPanel Component Tests (components/canvas/CanvasLogicPanel.tsx)
 *
 * Tests verify the real CanvasLogicPanel (P7 server-side Python logic panel):
 * - shows the loading state before GET /api/canvas/:id/logic resolves
 * - loads existing logic source into the editor
 * - 404 on load leaves an empty source instead of crashing
 * - Save PUTs { source, language: "python", agent_id } to /api/canvas/:id/logic
 * - Run saves first, then POSTs /api/canvas/:id/logic/run and renders the
 *   stdout / stderr / exit code result block
 * - save/run failures surface the backend detail message
 * - switching canvasId refetches the logic
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';

jest.mock('@monaco-editor/react', () => ({
  __esModule: true,
  default: ({ value, onChange }: any) => (
    <textarea
      data-testid="logic-editor"
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
    />
  ),
}));

const apiClientMock = {
  get: jest.fn(),
  put: jest.fn(),
  post: jest.fn(),
  delete: jest.fn(),
};
jest.mock('@/lib/api', () => ({ apiClient: apiClientMock }));

import { CanvasLogicPanel } from '../CanvasLogicPanel';

const get = apiClientMock.get as jest.Mock;
const put = apiClientMock.put as jest.Mock;
const post = apiClientMock.post as jest.Mock;

const runResult = {
  success: true,
  data: {
    success: true,
    stdout: 'Hello from sandbox\n',
    stderr: '',
    exit_code: 0,
  },
};

describe('CanvasLogicPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows the loading state then renders the loaded logic source', async () => {
    get.mockResolvedValueOnce({
      data: { success: true, data: { source: 'print("hi")' } },
    });

    render(<CanvasLogicPanel canvasId="c-1" />);

    expect(screen.getByText('Loading canvas logic…')).toBeInTheDocument();

    const editor = await screen.findByTestId('logic-editor');
    expect(editor).toHaveValue('print("hi")');
    expect(screen.getByText('Server Logic (Python)')).toBeInTheDocument();
    expect(get).toHaveBeenCalledWith('/api/canvas/c-1/logic');
  });

  it('starts with an empty source when the canvas has no logic (404)', async () => {
    get.mockRejectedValueOnce({ response: { status: 404 } });

    render(<CanvasLogicPanel canvasId="c-1" />);

    const editor = await screen.findByTestId('logic-editor');
    expect(editor).toHaveValue('');
  });

  it('saves the edited source with language and agent_id on Save', async () => {
    get.mockResolvedValueOnce({ data: { success: true, data: { source: 'x = 1' } } });
    put.mockResolvedValueOnce({ data: { success: true } });

    render(<CanvasLogicPanel canvasId="c-1" agentId="agent-9" />);
    const editor = await screen.findByTestId('logic-editor');

    fireEvent.change(editor, { target: { value: 'x = 2' } });
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(put).toHaveBeenCalledWith('/api/canvas/c-1/logic', {
        source: 'x = 2',
        language: 'python',
        agent_id: 'agent-9',
      });
    });
  });

  it('shows the backend error detail when saving fails', async () => {
    get.mockResolvedValueOnce({ data: { success: true, data: { source: '' } } });
    put.mockRejectedValueOnce({
      response: { data: { detail: 'Governance: AUTONOMOUS agent required' } },
    });

    render(<CanvasLogicPanel canvasId="c-1" />);
    await screen.findByTestId('logic-editor');

    fireEvent.click(screen.getByText('Save'));

    expect(
      await screen.findByText('Governance: AUTONOMOUS agent required')
    ).toBeInTheDocument();
  });

  it('saves then runs the logic and renders stdout and exit code', async () => {
    get.mockResolvedValueOnce({ data: { success: true, data: { source: '' } } });
    put.mockResolvedValueOnce({ data: { success: true } });
    post.mockResolvedValueOnce({ data: runResult });

    render(<CanvasLogicPanel canvasId="c-1" agentId="agent-9" />);
    const editor = await screen.findByTestId('logic-editor');

    fireEvent.change(editor, { target: { value: 'print("Hello from sandbox")' } });
    fireEvent.click(screen.getByText('Run'));

    // save-before-run
    await waitFor(() => {
      expect(put).toHaveBeenCalledWith('/api/canvas/c-1/logic', {
        source: 'print("Hello from sandbox")',
        language: 'python',
        agent_id: 'agent-9',
      });
    });
    expect(post).toHaveBeenCalledWith('/api/canvas/c-1/logic/run', {
      inputs: {},
      agent_id: 'agent-9',
    });

    expect(await screen.findByText('Hello from sandbox')).toBeInTheDocument();
    expect(screen.getByText('exit code: 0')).toBeInTheDocument();
  });

  it('renders stderr in red output when the run reports errors', async () => {
    get.mockResolvedValueOnce({ data: { success: true, data: { source: '' } } });
    put.mockResolvedValueOnce({ data: { success: true } });
    post.mockResolvedValueOnce({
      data: {
        success: true,
        data: {
          success: false,
          stdout: '',
          stderr: 'ZeroDivisionError: division by zero',
          exit_code: 1,
        },
      },
    });

    render(<CanvasLogicPanel canvasId="c-1" />);
    await screen.findByTestId('logic-editor');

    fireEvent.click(screen.getByText('Run'));

    expect(await screen.findByText('ZeroDivisionError: division by zero')).toBeInTheDocument();
    expect(screen.getByText('exit code: 1')).toBeInTheDocument();
  });

  it('shows the error detail when the run request fails', async () => {
    get.mockResolvedValueOnce({ data: { success: true, data: { source: '' } } });
    put.mockResolvedValueOnce({ data: { success: true } });
    post.mockRejectedValueOnce({ response: { data: { detail: 'Sandbox timeout' } } });

    render(<CanvasLogicPanel canvasId="c-1" />);
    await screen.findByTestId('logic-editor');

    fireEvent.click(screen.getByText('Run'));

    expect(await screen.findByText('Sandbox timeout')).toBeInTheDocument();
  });

  it('shows a fallback error message when the save fails without a backend detail', async () => {
    get.mockResolvedValueOnce({ data: { success: true, data: { source: '' } } });
    put.mockRejectedValueOnce(new Error('network down'));

    render(<CanvasLogicPanel canvasId="c-1" />);
    await screen.findByTestId('logic-editor');

    fireEvent.click(screen.getByText('Save'));

    expect(await screen.findByText('Failed to save logic')).toBeInTheDocument();
  });

  it('shows a fallback error message when the run fails without a backend detail', async () => {
    get.mockResolvedValueOnce({ data: { success: true, data: { source: '' } } });
    put.mockResolvedValueOnce({ data: { success: true } });
    post.mockRejectedValueOnce(new Error('boom'));

    render(<CanvasLogicPanel canvasId="c-1" />);
    await screen.findByTestId('logic-editor');

    fireEvent.click(screen.getByText('Run'));

    expect(await screen.findByText('Failed to run logic')).toBeInTheDocument();
  });

  it('ignores a late fetch response after unmount', async () => {
    let resolveGet: (v: any) => void;
    get.mockReturnValueOnce(
      new Promise((r) => {
        resolveGet = r;
      })
    );

    const { unmount } = render(<CanvasLogicPanel canvasId="c-1" />);
    expect(screen.getByText('Loading canvas logic…')).toBeInTheDocument();

    unmount();
    resolveGet!({ data: { success: true, data: { source: 'late' } } });
    await act(async () => {});
    expect(screen.queryByTestId('logic-editor')).not.toBeInTheDocument();
  });

  it('refetches logic when the canvasId changes', async () => {
    get.mockResolvedValueOnce({ data: { success: true, data: { source: 'a' } } });
    get.mockResolvedValueOnce({ data: { success: true, data: { source: 'b' } } });

    const { rerender } = render(<CanvasLogicPanel canvasId="c-1" />);
    await screen.findByTestId('logic-editor');

    rerender(<CanvasLogicPanel canvasId="c-2" />);

    await waitFor(() => {
      expect(get).toHaveBeenCalledWith('/api/canvas/c-2/logic');
    });
    const editor = await screen.findByTestId('logic-editor');
    await waitFor(() => expect(editor).toHaveValue('b'));
  });
});
