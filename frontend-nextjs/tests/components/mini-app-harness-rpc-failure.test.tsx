/**
 * MiniAppHarness — RPC failure-consumer integration (actual component render).
 *
 * The shared RPC client throws on a body-level `success: false` and preserves
 * the action's typed result as `RpcError.actionResult`. The harness knows the
 * mini-app result schema and must render the already-exposed safe handler
 * error for those semantic failures, while keeping HTTP/network/unknown
 * failures on the generic RpcError message (never raw transport/server text).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MiniAppHarness } from '@/components/canvas/MiniAppHarness';
import { apiClient } from '@/lib/api';
import { rpc } from '@/lib/rpc-client';

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

jest.mock('@/lib/api', () => ({
  apiClient: { get: jest.fn(), put: jest.fn(), post: jest.fn(), delete: jest.fn() },
}));

jest.mock('@/lib/rpc-client', () => ({
  rpc: { call: jest.fn(), listActions: jest.fn() },
}));

const apiClientMock = apiClient as unknown as {
  get: jest.Mock;
  put: jest.Mock;
  post: jest.Mock;
  delete: jest.Mock;
};
const rpcMock = rpc as unknown as { call: jest.Mock; listActions: jest.Mock };

const renderHarness = () => render(<MiniAppHarness canvasId="canvas-1" />);
const expand = () => fireEvent.click(screen.getByText('Mini-App Harness'));

/** Scaffold a draft so Dev-Run / Publish / Install are enabled. */
async function scaffoldDraft() {
  rpcMock.call.mockImplementation(async (action: string) => {
    if (action === 'mini_app_scaffold') {
      return { success: true, app_id: 'app-1', canvas_id: 'bp-1', logic_source: 'state = {}' };
    }
    if (action === 'mini_app_list') return { success: true, apps: [] };
    throw new Error(`unexpected action: ${action}`);
  });
  renderHarness();
  expand();
  await waitFor(() => expect(screen.getByTestId('logic-editor')).toBeInTheDocument());
  fireEvent.click(screen.getByText('Scaffold'));
  await waitFor(() => expect(screen.getByText('app-1')).toBeInTheDocument());
}

function semanticRpcError(action: string, actionResult: Record<string, unknown>) {
  return Object.assign(new Error(`Action '${action}' failed`), {
    action,
    actionResult,
  });
}

describe('MiniAppHarness RPC failure consumer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    apiClientMock.get.mockResolvedValue({ data: { success: true, data: { source: '' } } });
    apiClientMock.put.mockResolvedValue({ data: { success: true } });
  });

  it('renders the already-exposed SyntaxError from a semantic dev-run failure', async () => {
    await scaffoldDraft();
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === 'mini_app_dev_run') {
        throw semanticRpcError('mini_app_dev_run', {
          success: false,
          error: 'SyntaxError: invalid syntax (<unknown>, line 1)',
        });
      }
      throw new Error(`unexpected action: ${action}`);
    });

    fireEvent.click(screen.getByText('Dev-Run (dry)'));

    await waitFor(() =>
      expect(
        screen.getByText('SyntaxError: invalid syntax (<unknown>, line 1)')
      ).toBeInTheDocument()
    );
    // The generic outer message must not replace the actionable handler error.
    expect(screen.queryByText("Action 'mini_app_dev_run' failed")).not.toBeInTheDocument();
  });

  it('renders the sanitized runtime-unavailable handler error from a semantic dev-run failure', async () => {
    await scaffoldDraft();
    const unavailable =
      'Mini-app runtime unavailable on this host. Probe mini_app_status and see docs/deployment/FIRECRACKER_HOST_SETUP.md.';
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === 'mini_app_dev_run') {
        throw semanticRpcError('mini_app_dev_run', {
          success: false,
          error: unavailable,
        });
      }
      throw new Error(`unexpected action: ${action}`);
    });

    fireEvent.click(screen.getByText('Dev-Run (dry)'));

    await waitFor(() => expect(screen.getByText(unavailable)).toBeInTheDocument());
  });

  it('renders a semantic install failure (never-published app) through the install catch', async () => {
    await scaffoldDraft();
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === 'mini_app_install') {
        throw semanticRpcError('mini_app_install', {
          success: false,
          error: 'Mini-app is not published; publish before installing',
        });
      }
      throw new Error(`unexpected action: ${action}`);
    });

    fireEvent.click(screen.getByText('Install'));

    await waitFor(() =>
      expect(
        screen.getByText('Mini-app is not published; publish before installing')
      ).toBeInTheDocument()
    );
  });

  it('keeps HTTP 500 transport detail generic and never renders it', async () => {
    await scaffoldDraft();
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === 'mini_app_dev_run') {
        throw Object.assign(new Error('RPC call failed'), {
          action,
          status: 500,
          details: { error: 'internal-store-path-/private/detail' },
        });
      }
      throw new Error(`unexpected action: ${action}`);
    });

    fireEvent.click(screen.getByText('Dev-Run (dry)'));

    await waitFor(() => expect(screen.getByText('RPC call failed')).toBeInTheDocument());
    expect(screen.queryByText(/internal-store-path/)).not.toBeInTheDocument();
  });

  it('does not use an actionResult error when the handler did not report failure', async () => {
    await scaffoldDraft();
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === 'mini_app_publish') {
        throw Object.assign(new Error("Action 'mini_app_publish' failed"), {
          action,
          // Not a typed failure — must not become user-facing business copy.
          actionResult: { success: true, error: 'raw-not-a-failure' },
        });
      }
      throw new Error(`unexpected action: ${action}`);
    });

    fireEvent.click(screen.getByText('Publish'));

    await waitFor(() =>
      expect(screen.getByText("Action 'mini_app_publish' failed")).toBeInTheDocument()
    );
    expect(screen.queryByText('raw-not-a-failure')).not.toBeInTheDocument();
  });

  it('still renders a successful dev-run result (positive twin)', async () => {
    await scaffoldDraft();
    rpcMock.call.mockImplementation(async (action: string) => {
      if (action === 'mini_app_dev_run') {
        return {
          success: true,
          stdout: 'hello from run',
          stderr: '',
          exit_code: 0,
          state_changed: true,
          version: 3,
          state: { runs: 1 },
          proposed_ops: [{ op: 'set', key: 'runs' }],
        };
      }
      throw new Error(`unexpected action: ${action}`);
    });

    fireEvent.click(screen.getByText('Dev-Run (dry)'));

    await waitFor(() => expect(screen.getByText('hello from run')).toBeInTheDocument());
    expect(screen.getByText(/exit code: 0 · state_changed: true/)).toBeInTheDocument();
    expect(screen.getByText(/"state": \{/)).toBeInTheDocument();
    expect(screen.getByText(/Live instance state \(v3\)/)).toBeInTheDocument();
  });
});
