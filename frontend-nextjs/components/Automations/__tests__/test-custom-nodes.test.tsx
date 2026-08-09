/**
 * CustomNodes Component Tests
 *
 * Tests verify the REAL node components in
 * components/Automations/CustomNodes.tsx:
 *
 * - All 16 node types registered in nodeTypes render their variants
 *   (defaults + custom data, isConnectable propagation, handle ids)
 * - PerformanceBadge (success + failure analytics)
 * - ActionNode: connection health check, test-step success/error/catch
 *   flows, retry config display/toggle, waitForInput + requiredInputs
 * - ConditionNode: expression / llm / code / visual variants
 * - Handle ids for branching nodes (true/false, loop_body/loop_done,
 *   approved/rejected)
 *
 * reactflow is mocked (Handle + Position only — the real one needs a
 * canvas/DOM measurement layer).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import {
  nodeTypes,
  TriggerNode,
  ActionNode,
  ConditionNode,
  AINode,
  DesktopNode,
  EmailNode,
  HttpNode,
  TimerNode,
  LoopNode,
  ApprovalNode,
  CodeNode,
  TableNode,
  SubFlowNode,
  FormInputNode,
  TableTriggerNode,
  ChatTriggerNode,
} from '../CustomNodes';

// ---------------------------------------------------------------------------
// reactflow mock — Handle renders a plain div exposing its props for
// assertions; Position is a constant map.
// ---------------------------------------------------------------------------
jest.mock('reactflow', () => {
  const React = jest.requireActual('react');
  return {
    __esModule: true,
    Handle: ({ id, type, position, isConnectable, className, style }: any) =>
      React.createElement('div', {
        'data-testid': id ? `handle-${id}` : 'handle',
        'data-handle-type': type,
        'data-handle-position': position,
        'data-connectable': String(isConnectable),
        'data-style': style ? JSON.stringify(style) : undefined,
        className,
      }),
    Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
  };
});

const mockFetch = jest.fn();

const renderNode = (Component: any, props: any = {}) =>
  render(<Component data={{}} isConnectable={true} {...props} />);

// Await the mount-time health check so its setState runs inside act().
const waitForConnected = (container: HTMLElement) =>
  waitFor(() =>
    expect(container.querySelector('.bg-green-500.rounded-full')).toBeInTheDocument()
  );

describe('CustomNodes — nodeTypes registry', () => {
  test('registers all 16 node types', () => {
    expect(Object.keys(nodeTypes).sort()).toEqual([
      'action',
      'ai_node',
      'approval',
      'chat_trigger',
      'code',
      'condition',
      'desktop',
      'email',
      'form_input',
      'http',
      'loop',
      'subflow',
      'table',
      'table_trigger',
      'timer',
      'trigger',
    ]);
  });

  test('every registered node renders without crashing on empty data', () => {
    Object.entries(nodeTypes).forEach(([key, Component]) => {
      const { container } = render(<Component data={{}} isConnectable={true} />);
      expect(container.querySelector('[data-testid^="handle"]')).toBeInTheDocument();
      container.remove();
    });
  });
});

describe('PerformanceBadge (via TriggerNode _analytics)', () => {
  test('renders success badge with duration for COMPLETED status', () => {
    const { container } = renderNode(TriggerNode, {
      data: { label: 'Webhook Trigger', _analytics: { duration: 1234, status: 'COMPLETED' } },
    });
    expect(container.innerHTML).toContain('bg-green-100');
    expect(container.innerHTML).toContain('1234ms');
  });

  test('renders success badge for lowercase "success" status', () => {
    const { container } = renderNode(TriggerNode, {
      data: { _analytics: { duration: 42, status: 'success' } },
    });
    expect(container.innerHTML).toContain('bg-green-100');
    expect(container.innerHTML).toContain('42ms');
  });

  test('renders failure badge for failed status', () => {
    const { container } = renderNode(TriggerNode, {
      data: { _analytics: { duration: 500, status: 'FAILED', error: 'boom' } },
    });
    expect(container.innerHTML).toContain('bg-red-100');
    expect(container.innerHTML).toContain('500ms');
  });

  test('renders no badge when analytics absent', () => {
    const { container } = renderNode(TriggerNode, { data: { label: 'Plain' } });
    expect(container.innerHTML).not.toMatch(/\d+ms/);
    expect(container.innerHTML).not.toContain('bg-green-100');
    expect(container.innerHTML).not.toContain('bg-red-100');
  });
});

describe('TriggerNode', () => {
  test('renders default label and connectable source handle', () => {
    const { container } = renderNode(TriggerNode, { data: {} });
    expect(screen.getByText('Trigger')).toBeInTheDocument();
    expect(screen.getByText('Webhook')).toBeInTheDocument();
    const handle = container.querySelector('[data-testid="handle"]');
    expect(handle).toHaveAttribute('data-handle-type', 'source');
    expect(handle).toHaveAttribute('data-connectable', 'true');
  });

  test('renders custom label, integration badge and input schema', () => {
    const { container } = renderNode(TriggerNode, {
      data: { label: 'Slack New Message', integration: 'Slack', schema: { user: 'string' } },
    });
    expect(screen.getByText('Slack New Message')).toBeInTheDocument();
    expect(screen.getByText('Slack')).toBeInTheDocument();
    expect(screen.getByText('Input Schema:')).toBeInTheDocument();
    expect(container.innerHTML).toContain('"user"');
    expect(container.innerHTML).toContain('"string"');
  });

  test('propagates isConnectable={false} to the handle', () => {
    const { container } = renderNode(TriggerNode, { data: {}, isConnectable: false });
    expect(container.querySelector('[data-testid="handle"]')).toHaveAttribute('data-connectable', 'false');
  });
});

describe('ActionNode', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({ ok: true } as Response);
    global.fetch = mockFetch as any;
    window.open = jest.fn();
  });

  test('renders service title, action label, source and target handles', async () => {
    const { container } = renderNode(ActionNode, {
      data: { service: 'Slack', action: 'Post Message' },
    });
    expect(screen.getByText('Slack')).toBeInTheDocument();
    expect(screen.getByText('Post Message')).toBeInTheDocument();
    const handles = container.querySelectorAll('[data-testid="handle"]');
    expect(handles).toHaveLength(2);
    expect(handles[0]).toHaveAttribute('data-handle-type', 'target');
    expect(handles[1]).toHaveAttribute('data-handle-type', 'source');
    await waitForConnected(container);
  });

  test('uses service branding color for known service and default for unknown', async () => {
    const known = renderNode(ActionNode, { data: { service: 'Slack' } });
    expect(known.container.innerHTML).toContain('border-l-[#4A154B]');
    await waitForConnected(known.container);
    known.unmount();

    const unknown = renderNode(ActionNode, { data: { service: 'MysteryApp' } });
    expect(unknown.container.innerHTML).toContain('border-l-green-500');
    await waitForConnected(unknown.container);
    unknown.unmount();
  });

  test('shows green connection dot when health check succeeds', async () => {
    mockFetch.mockResolvedValue({ ok: true } as Response);
    const { container } = renderNode(ActionNode, { data: { service: 'Slack', serviceId: 'slack' } });
    expect(mockFetch).toHaveBeenCalledWith('/api/integrations/slack/health');
    await waitFor(() => {
      expect(container.querySelector('.bg-green-500.rounded-full')).toBeInTheDocument();
    });
    expect(screen.queryByText('Connect')).not.toBeInTheDocument();
  });

  test('shows Connect button when health check fails', async () => {
    mockFetch.mockResolvedValue({ ok: false } as Response);
    renderNode(ActionNode, { data: { service: 'Slack', serviceId: 'slack' } });
    const connectBtn = await screen.findByText('Connect');
    expect(connectBtn).toBeInTheDocument();
  });

  test('shows Connect button when health check rejects', async () => {
    mockFetch.mockRejectedValue(new Error('network down'));
    renderNode(ActionNode, { data: { service: 'Slack', serviceId: 'slack' } });
    const connectBtn = await screen.findByText('Connect');
    expect(connectBtn).toBeInTheDocument();
  });

  test('Connect button opens the integration page in a new tab', async () => {
    mockFetch.mockResolvedValue({ ok: false } as Response);
    renderNode(ActionNode, { data: { service: 'Google Drive', serviceId: 'google-drive' } });
    const connectBtn = await screen.findByText('Connect');
    fireEvent.click(connectBtn);
    expect(window.open).toHaveBeenCalledWith('/integrations/google-drive', '_blank');
  });

  test('skips health check when no service is provided', () => {
    renderNode(ActionNode, { data: { action: 'execute' } });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  test('test-step success shows duration and resets to idle after 3s', async () => {
    jest.useFakeTimers();
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({ duration_ms: 250 }) } as any);
    renderNode(ActionNode, { data: { serviceId: 'slack', action: 'execute' } });

    const testBtn = screen.getByRole('button', { name: /Test Step/i });
    fireEvent.click(testBtn);

    expect(screen.getByText('Testing...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Testing/i })).toBeDisabled();

    await act(async () => { await Promise.resolve(); });
    expect(screen.getByText('Success (250ms)')).toBeInTheDocument();

    act(() => { jest.advanceTimersByTime(3000); });
    expect(screen.getByRole('button', { name: /Test Step/i })).toBeInTheDocument();
    jest.useRealTimers();
  });

  test('test-step failure (non-ok response) shows Failed', async () => {
    mockFetch.mockResolvedValue({ ok: false, json: async () => ({ error: 'nope' }) } as any);
    renderNode(ActionNode, { data: { serviceId: 'slack' } });
    fireEvent.click(screen.getByRole('button', { name: /Test Step/i }));
    expect(await screen.findByText('Failed')).toBeInTheDocument();
  });

  test('test-step network error shows Failed', async () => {
    mockFetch.mockRejectedValue(new Error('boom'));
    renderNode(ActionNode, { data: { serviceId: 'slack' } });
    fireEvent.click(screen.getByRole('button', { name: /Test Step/i }));
    expect(await screen.findByText('Failed')).toBeInTheDocument();
  });

  test('success without duration_ms shows plain Success', async () => {
    mockFetch.mockResolvedValue({ ok: true, json: async () => ({}) } as any);
    renderNode(ActionNode, { data: { serviceId: 'slack' } });
    fireEvent.click(screen.getByRole('button', { name: /Test Step/i }));
    expect(await screen.findByText('Success')).toBeInTheDocument();
    expect(screen.queryByText(/Success \(\d+ms\)/)).not.toBeInTheDocument();
  });

  test('renders description when provided', async () => {
    const { container } = renderNode(ActionNode, { data: { service: 'Slack', description: 'Posts to #general' } });
    expect(screen.getByText('Posts to #general')).toBeInTheDocument();
    await waitForConnected(container);
  });

  test('renders waiting-for inputs and pause icon when waitForInput', async () => {
    const { container } = renderNode(ActionNode, {
      data: { service: 'Slack', waitForInput: true, requiredInputs: ['Email', 'Subject'] },
    });
    expect(screen.getByText('Waiting for:')).toBeInTheDocument();
    expect(screen.getByText('Email, Subject')).toBeInTheDocument();
    expect(container.innerHTML).toContain('text-amber-500');
    await waitForConnected(container);
  });

  test('shows auto-retry config when enabled (maxRetries + exponential)', async () => {
    const { container } = renderNode(ActionNode, {
      data: {
        service: 'Slack',
        retryConfig: { enabled: true, maxRetries: 5, retryDelayMs: 2000, exponentialBackoff: true },
      },
    });
    expect(screen.getByText('Auto-retry: 5x')).toBeInTheDocument();
    expect(screen.getByText('(exponential)')).toBeInTheDocument();
    await waitForConnected(container);
  });

  test('hides auto-retry config when disabled (default)', async () => {
    const { container } = renderNode(ActionNode, { data: { service: 'Slack' } });
    expect(screen.queryByText(/Auto-retry:/)).not.toBeInTheDocument();
    await waitForConnected(container);
  });

  test('toggles retry config detail panel', async () => {
    const { container } = renderNode(ActionNode, {
      data: {
        service: 'Slack',
        retryConfig: { enabled: false, maxRetries: 3, retryDelayMs: 1000, exponentialBackoff: false },
      },
    });
    expect(screen.queryByText('Max retries:')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Configure retries/i }));
    expect(screen.getByText('Max retries:')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('1000ms')).toBeInTheDocument();
    expect(screen.getByText('No')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Hide retry config/i }));
    expect(screen.queryByText('Max retries:')).not.toBeInTheDocument();
    await waitForConnected(container);
  });
});

describe('ConditionNode', () => {
  test('renders expression variant (default) with condition text and TRUE/FALSE labels', () => {
    const { container } = renderNode(ConditionNode, { data: { condition: 'If x > y' } });
    expect(screen.getByText('Condition')).toBeInTheDocument();
    expect(screen.getByText('If x > y')).toBeInTheDocument();
    expect(screen.getByText('TRUE')).toBeInTheDocument();
    expect(screen.getByText('FALSE')).toBeInTheDocument();
    const sourceHandles = container.querySelectorAll('[data-handle-type="source"]');
    expect(sourceHandles).toHaveLength(2);
    expect(container.querySelector('[data-testid="handle-true"]')).toHaveAttribute('data-handle-position', 'bottom');
    expect(container.querySelector('[data-testid="handle-false"]')).toHaveAttribute('data-handle-position', 'bottom');
  });

  test('renders llm variant with LLM badge and prompt', () => {
    const { container } = renderNode(ConditionNode, {
      data: { conditionType: 'llm', prompt: 'Is this positive?' },
    });
    expect(screen.getByText('LLM')).toBeInTheDocument();
    expect(screen.getByText(/Is this positive\?/)).toBeInTheDocument();
    expect(container.innerHTML).toContain('bg-purple-50');
  });

  test('renders llm variant with default prompt when absent', () => {
    renderNode(ConditionNode, { data: { conditionType: 'llm' } });
    expect(screen.getByText(/Is sentiment positive\?/)).toBeInTheDocument();
  });

  test('renders code variant with code block and AI Gen button', () => {
    const { container } = renderNode(ConditionNode, {
      data: { conditionType: 'code', code: 'return a > b;' },
    });
    expect(screen.getByText('Code')).toBeInTheDocument();
    expect(screen.getByText('return a > b;')).toBeInTheDocument();
    expect(screen.getByText('AI Gen')).toBeInTheDocument();
    expect(container.innerHTML).toContain('bg-slate-900');
  });

  test('renders code variant with placeholder code when absent', () => {
    renderNode(ConditionNode, { data: { conditionType: 'code' } });
    expect(screen.getByText(/Write code here/)).toBeInTheDocument();
  });

  test('renders visual variant with field/op/value expression', () => {
    const { container } = renderNode(ConditionNode, {
      data: { conditionType: 'visual', field: 'Age', op: '>=', value: '18' },
    });
    expect(screen.getByText('Builder')).toBeInTheDocument();
    expect(screen.getByText('Age')).toBeInTheDocument();
    expect(screen.getByText('>=')).toBeInTheDocument();
    expect(screen.getByText('18')).toBeInTheDocument();
    expect(container.innerHTML).toContain('bg-green-50');
  });

  test('renders visual variant with defaults when absent and falls back to operator', () => {
    renderNode(ConditionNode, { data: { conditionType: 'visual', operator: '!=' } });
    expect(screen.getByText('Field')).toBeInTheDocument();
    expect(screen.getByText('!=')).toBeInTheDocument();
    expect(screen.getByText('Value')).toBeInTheDocument();
  });
});

describe('AINode', () => {
  test('renders defaults when no model/prompt', () => {
    renderNode(AINode, { data: {} });
    expect(screen.getByText('AI Processing')).toBeInTheDocument();
    expect(screen.getByText(/GPT-4/)).toBeInTheDocument();
    expect(screen.getByText('Summarize input...')).toBeInTheDocument();
  });

  test('renders custom model and prompt', () => {
    const { container } = renderNode(AINode, { data: { model: 'Claude 3.5', prompt: 'Extract entities' } });
    expect(screen.getByText(/Claude 3\.5/)).toBeInTheDocument();
    expect(screen.getByText('Extract entities')).toBeInTheDocument();
    expect(container.querySelector('[data-handle-type="target"]')).toBeInTheDocument();
    expect(container.querySelector('[data-handle-type="source"]')).toBeInTheDocument();
  });
});

describe('DesktopNode', () => {
  test('renders defaults and custom app/action', () => {
    const { container } = renderNode(DesktopNode, { data: {} });
    expect(screen.getByText('Desktop Action')).toBeInTheDocument();
    expect(screen.getByText('Application')).toBeInTheDocument();
    expect(screen.getByText('Open')).toBeInTheDocument();
    expect(container.querySelector('[data-handle-type="target"]')).toBeInTheDocument();
    expect(container.querySelector('[data-handle-type="source"]')).toBeInTheDocument();
  });

  test('renders custom app and action', () => {
    renderNode(DesktopNode, { data: { app: 'Excel', action: 'Open workbook' } });
    expect(screen.getByText('Excel')).toBeInTheDocument();
    expect(screen.getByText('Open workbook')).toBeInTheDocument();
  });
});

describe('EmailNode', () => {
  test('renders defaults and custom recipient/subject', () => {
    renderNode(EmailNode, { data: {} });
    expect(screen.getByText(/recipient@email\.com/)).toBeInTheDocument();
    expect(screen.getByText(/Email Subject/)).toBeInTheDocument();

    const { unmount } = renderNode(EmailNode, { data: { recipient: 'a@b.com', subject: 'Hello' } });
    expect(screen.getByText(/a@b\.com/)).toBeInTheDocument();
    expect(screen.getByText(/Hello/)).toBeInTheDocument();
    unmount();
  });
});

describe('HttpNode', () => {
  test('renders GET default with green badge class', () => {
    const { container } = renderNode(HttpNode, { data: {} });
    expect(screen.getByText('GET')).toBeInTheDocument();
    expect(screen.getByText(/api\.example\.com/)).toBeInTheDocument();
    expect(container.innerHTML).toContain('bg-green-100');
  });

  test('renders POST method styling', () => {
    const { container } = renderNode(HttpNode, { data: { method: 'POST', url: 'https://x.io' } });
    expect(screen.getByText('POST')).toBeInTheDocument();
    expect(screen.getByText('https://x.io')).toBeInTheDocument();
    expect(container.innerHTML).toContain('bg-blue-100');
  });

  test('renders unknown method with gray fallback styling', () => {
    const { container } = renderNode(HttpNode, { data: { method: 'OPTIONS' } });
    expect(screen.getByText('OPTIONS')).toBeInTheDocument();
    expect(container.innerHTML).toContain('bg-gray-100');
  });
});

describe('TimerNode', () => {
  test('renders defaults and custom duration/unit', () => {
    renderNode(TimerNode, { data: {} });
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('minutes')).toBeInTheDocument();

    const { unmount } = renderNode(TimerNode, { data: { duration: '10', unit: 'seconds' } });
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('seconds')).toBeInTheDocument();
    unmount();
  });
});

describe('LoopNode', () => {
  test('renders defaults with iterateOver placeholder and dual handles', () => {
    const { container } = renderNode(LoopNode, { data: {} });
    expect(screen.getByText('Loop')).toBeInTheDocument();
    expect(screen.getByText(/previousStep\.items/)).toBeInTheDocument();
    expect(screen.getByText('Body')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="handle-loop_body"]')).toHaveAttribute('data-handle-type', 'source');
    expect(container.querySelector('[data-testid="handle-loop_done"]')).toHaveAttribute('data-handle-type', 'source');
  });

  test('renders custom iterateOver and maxIterations', () => {
    renderNode(LoopNode, { data: { iterateOver: '{{users}}', maxIterations: 7 } });
    expect(screen.getByText(/users/)).toBeInTheDocument();
    expect(screen.getByText('Max: 7 iterations')).toBeInTheDocument();
  });
});

describe('ApprovalNode', () => {
  test('renders defaults, message, timeout, approvers and dual handles', () => {
    const { container } = renderNode(ApprovalNode, {
      data: { message: 'Approve invoice #42', timeout: '24h', approvers: 'Finance Team' },
    });
    expect(screen.getByText('Wait for Approval')).toBeInTheDocument();
    expect(screen.getByText('Approve invoice #42')).toBeInTheDocument();
    expect(screen.getByText(/Timeout: 24h/)).toBeInTheDocument();
    expect(screen.getByText(/Approvers: Finance Team/)).toBeInTheDocument();
    expect(screen.getByText('Workflow pauses until approved')).toBeInTheDocument();
    expect(screen.getByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('Rejected')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="handle-approved"]')).toHaveAttribute('data-handle-type', 'source');
    expect(container.querySelector('[data-testid="handle-rejected"]')).toHaveAttribute('data-handle-type', 'source');
  });

  test('renders default waiting message when absent', () => {
    renderNode(ApprovalNode, { data: {} });
    expect(screen.getByText('Waiting for human approval')).toBeInTheDocument();
  });
});

describe('CodeNode', () => {
  test('renders defaults: placeholder code, TypeScript badge, Ask AI button', () => {
    const { container } = renderNode(CodeNode, { data: {} });
    expect(screen.getByText('Code')).toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
    expect(screen.getByText(/Write your code here/)).toBeInTheDocument();
    expect(screen.getByText('Ask AI to write code')).toBeInTheDocument();
    expect(container.querySelector('[data-handle-type="target"]')).toBeInTheDocument();
    expect(container.querySelector('[data-handle-type="source"]')).toBeInTheDocument();
  });

  test('renders custom code, language and npm packages', () => {
    renderNode(CodeNode, {
      data: { code: 'return 42;', language: 'Python', npmPackages: ['axios', 'lodash'] },
    });
    expect(screen.getByText('return 42;')).toBeInTheDocument();
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText(/axios, lodash/)).toBeInTheDocument();
  });
});

describe('TableNode', () => {
  test('renders defaults and custom action/table', () => {
    renderNode(TableNode, { data: {} });
    expect(screen.getByText('Tables')).toBeInTheDocument();
    expect(screen.getByText('Insert Row')).toBeInTheDocument();
    expect(screen.getByText('Select table')).toBeInTheDocument();

    const { unmount } = renderNode(TableNode, { data: { action: 'Update Row', tableName: 'leads' } });
    expect(screen.getByText('Update Row')).toBeInTheDocument();
    expect(screen.getByText('leads')).toBeInTheDocument();
    unmount();
  });
});

describe('SubFlowNode', () => {
  test('renders sync badge by default', () => {
    renderNode(SubFlowNode, { data: {} });
    expect(screen.getByText('Sub Flow')).toBeInTheDocument();
    expect(screen.getByText('Sync')).toBeInTheDocument();
    expect(screen.getByText('Select flow')).toBeInTheDocument();
    expect(screen.queryByText('Fire and forget')).not.toBeInTheDocument();
  });

  test('renders async badge, flowName and description + fire-and-forget note', () => {
    renderNode(SubFlowNode, { data: { async: true, flowName: 'Onboard User', description: 'Sends welcome email' } });
    expect(screen.getByText('Async')).toBeInTheDocument();
    expect(screen.getByText('Onboard User')).toBeInTheDocument();
    expect(screen.getByText('Sends welcome email')).toBeInTheDocument();
    expect(screen.getByText('Fire and forget')).toBeInTheDocument();
  });
});

describe('FormInputNode', () => {
  const fields = [
    { name: 'email', type: 'text', label: 'Email' },
    { name: 'notes', type: 'textarea', label: 'Notes', required: true },
  ];

  test('renders default single field when fields absent', () => {
    renderNode(FormInputNode, { data: {} });
    expect(screen.getByText('Form Input')).toBeInTheDocument();
    expect(screen.getByText('text:')).toBeInTheDocument();
    expect(screen.getByText('Input 1')).toBeInTheDocument();
    expect(screen.getByText(/Collect user input via form/)).toBeInTheDocument();
  });

  test('renders fields with required markers', () => {
    renderNode(FormInputNode, { data: { fields, description: 'Fill the form' } });
    expect(screen.getByText('Fill the form')).toBeInTheDocument();
    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Notes')).toBeInTheDocument();
    expect(screen.getByText('*')).toBeInTheDocument();
  });

  test('caps field preview at 3 and shows "+N more fields"', () => {
    const manyFields = Array.from({ length: 5 }, (_, i) => ({ name: `f${i}`, type: 'text', label: `Field ${i}` }));
    renderNode(FormInputNode, { data: { fields: manyFields } });
    expect(screen.getByText('+2 more fields')).toBeInTheDocument();
    expect(screen.queryByText('Field 3')).not.toBeInTheDocument();
    expect(screen.queryByText('Field 4')).not.toBeInTheDocument();
  });

  test('renders assignTo and timeoutHours', () => {
    renderNode(FormInputNode, { data: { fields, assignTo: 'ops@atom.ai', timeoutHours: 48 } });
    expect(screen.getByText(/Assigned to: ops@atom\.ai/)).toBeInTheDocument();
    expect(screen.getByText(/Timeout: 48h/)).toBeInTheDocument();
  });
});

describe('TableTriggerNode', () => {
  test('renders row_created default with event label and table', () => {
    const { container } = renderNode(TableTriggerNode, { data: { tableName: 'orders' } });
    expect(screen.getByText('Table Trigger')).toBeInTheDocument();
    expect(screen.getByText('Row Created')).toBeInTheDocument();
    expect(screen.getByText('orders')).toBeInTheDocument();
    expect(container.innerHTML).toContain('bg-green-500');
  });

  test('renders each event type label + fallback for unknown', () => {
    const cases: Array<[string, string]> = [
      ['row_updated', 'Row Updated'],
      ['row_deleted', 'Row Deleted'],
      ['any_change', 'Any Change'],
      ['bogus_event', 'Row Created'],
    ];
    cases.forEach(([eventType, label]) => {
      const { unmount } = renderNode(TableTriggerNode, { data: { eventType } });
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    });
  });

  test('renders filter count when filters present, hides otherwise', () => {
    const { unmount } = renderNode(TableTriggerNode, { data: { filters: [{ col: 'x' }, { col: 'y' }] } });
    expect(screen.getByText('Filters:')).toBeInTheDocument();
    expect(screen.getByText('2 condition(s)')).toBeInTheDocument();
    unmount();

    renderNode(TableTriggerNode, { data: {} });
    expect(screen.queryByText('2 condition(s)')).not.toBeInTheDocument();
    expect(screen.queryByText('Filters:')).not.toBeInTheDocument();
  });
});

describe('ChatTriggerNode', () => {
  test('renders "Any message" when no keywords', () => {
    renderNode(ChatTriggerNode, { data: {} });
    expect(screen.getByText('Chat Trigger')).toBeInTheDocument();
    expect(screen.getByText('Any message')).toBeInTheDocument();
  });

  test('renders up to 3 keyword badges and "+N" overflow', () => {
    renderNode(ChatTriggerNode, { data: { keywords: ['hi', 'hello', 'hey', 'yo', 'sup'] } });
    expect(screen.getByText('hi')).toBeInTheDocument();
    expect(screen.getByText('hello')).toBeInTheDocument();
    expect(screen.getByText('hey')).toBeInTheDocument();
    expect(screen.getByText('+2')).toBeInTheDocument();
    expect(screen.queryByText('yo')).not.toBeInTheDocument();
    expect(screen.queryByText('Any message')).not.toBeInTheDocument();
  });

  test('renders exactly 3 keywords without overflow note', () => {
    renderNode(ChatTriggerNode, { data: { keywords: ['a', 'b', 'c'] } });
    expect(screen.getByText('a')).toBeInTheDocument();
    expect(screen.getByText('b')).toBeInTheDocument();
    expect(screen.getByText('c')).toBeInTheDocument();
    expect(screen.queryByText(/^\+/)).not.toBeInTheDocument();
  });

  test('renders channel and userFilter', () => {
    const { container } = renderNode(ChatTriggerNode, {
      data: { keywords: [], channel: '#sales', userFilter: 'user@corp.com' },
    });
    expect(screen.getByText('Channel:')).toBeInTheDocument();
    expect(container.innerHTML).toContain('#sales');
    expect(screen.getByText('user@corp.com')).toBeInTheDocument();
  });
});
