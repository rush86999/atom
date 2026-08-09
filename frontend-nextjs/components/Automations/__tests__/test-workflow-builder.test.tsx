/**
 * WorkflowBuilder Component Tests
 *
 * Tests verify the REAL WorkflowBuilder component
 * (components/Automations/WorkflowBuilder.tsx, a DEFAULT export):
 *
 * - Empty state + header + step/connection counters
 * - Toolbar node creation (Condition/Loop/Code/AI/Approval/Delay)
 * - PiecesSidebar append flow (action + trigger) and edge-insertion flow
 * - ReactFlow onConnect / onNodesDelete / onEdgesDelete / onNodeDragStop
 * - Node config sidebar open/update/close
 * - Save (with and without onSave prop)
 * - Undo/redo buttons + Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y keyboard shortcuts
 * - Performance mode (no workflowId gate, heatmap fetch, analytics injection)
 * - Optimize panel (success / failure / error paths)
 * - AI Copilot chat (multi-node NLU, single-node fallback, keyword paths,
 *   NLU-failure fallback, empty-input guard)
 * - Smart suggestions, logs toggle, sidebar toggle, workflowId injection,
 *   undo-history sync
 * - Regression: unique node ids after mid-list deletion (BUG-039)
 * - Regression: nodes without `data` must not crash optimize/analytics
 *
 * reactflow is mocked (the real one needs a canvas/DOM measurement layer);
 * the mock captures latest props + state setters so tests can drive
 * onConnect/onNodeClick/onNodesDelete/onEdgesDelete/onNodeDragStop.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import WorkflowBuilder from '../WorkflowBuilder';

// ---------------------------------------------------------------------------
// reactflow mock — self-contained factory; test API exposed via __testApi.
// useNodesState/useEdgesState keep REAL component state so node/edge flows
// behave like the real canvas.
// ---------------------------------------------------------------------------
jest.mock('reactflow', () => {
  const React = jest.requireActual('react');

  const api: any = {
    flowProps: null,
    setNodes: null,
    setEdges: null,
  };

  const ReactFlowMock = (props: any) => {
    api.flowProps = props;
    return React.createElement(
      'div',
      { 'data-testid': 'reactflow-canvas' },
      props.children
    );
  };

  return {
    __esModule: true,
    __testApi: api,
    default: ReactFlowMock,
    ReactFlow: ReactFlowMock,
    ReactFlowProvider: ({ children }: any) =>
      React.createElement(React.Fragment, null, children),
    Background: () => null,
    Controls: () => null,
    addEdge: (params: any, edges: any[]) => [...edges, { ...params }],
    useNodesState: (initial: any) => {
      const [nodes, setNodes] = React.useState(initial || []);
      api.setNodes = setNodes;
      return [nodes, setNodes, jest.fn()];
    },
    useEdgesState: (initial: any) => {
      const [edges, setEdges] = React.useState(initial || []);
      api.setEdges = setEdges;
      return [edges, setEdges, jest.fn()];
    },
    useKeyPress: () => false,
  };
});

// ---------------------------------------------------------------------------
// useUndoRedo mock — controllable canUndo/canRedo + history.present.
// ---------------------------------------------------------------------------
jest.mock('@/hooks/useUndoRedo', () => {
  const api: any = {
    value: {
      undo: jest.fn(),
      redo: jest.fn(),
      takeSnapshot: jest.fn(),
      canUndo: false,
      canRedo: false,
      history: { past: [], present: null, future: [] },
      resetHistory: jest.fn(),
    },
  };
  return { useUndoRedo: () => api.value, __testApi: api };
});

// ---------------------------------------------------------------------------
// ui/use-toast — file-level mock overrides the global setup one so the toast
// fn is assertable via __mockToast.
// ---------------------------------------------------------------------------
jest.mock('@/components/ui/use-toast', () => {
  const mockToast = jest.fn();
  return {
    useToast: () => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
    ToastProvider: ({ children }: any) => children,
    __mockToast: mockToast,
  };
});

// ---------------------------------------------------------------------------
// Sub-component mocks — render minimal surfaces that exercise the real
// callback contracts (onSelectPiece / onSuggestionClick / onUpdateNode ...).
// ---------------------------------------------------------------------------
jest.mock('../PiecesSidebar', () => {
  const React = jest.requireActual('react');
  const api: any = { props: null };

  const actionPiece: any = {
    id: 'slack',
    name: 'Slack',
    icon: () => null,
    color: '#000000',
    category: 'messaging',
    actions: [{ id: 'post', name: 'Post Message', description: 'Post a message' }],
    triggers: [],
  };
  const triggerPiece: any = {
    id: 'gmail',
    name: 'Gmail',
    icon: () => null,
    color: '#000000',
    category: 'email',
    actions: [],
    triggers: [{ id: 'new_email', name: 'New Email', description: 'On new email' }],
  };

  const MockPiecesSidebar = (props: any) => {
    api.props = props;
    return React.createElement(
      'div',
      { 'data-testid': 'pieces-sidebar' },
      React.createElement(
        'button',
        {
          type: 'button',
          'data-testid': 'select-slack-action',
          onClick: () =>
            props.onSelectPiece(
              actionPiece,
              'action',
              actionPiece.actions[0]
            ),
        },
        'Select Slack Piece'
      ),
      React.createElement(
        'button',
        {
          type: 'button',
          'data-testid': 'select-gmail-trigger',
          onClick: () =>
            props.onSelectPiece(
              triggerPiece,
              'trigger',
              triggerPiece.triggers[0]
            ),
        },
        'Select Gmail Trigger'
      )
    );
  };

  return { __esModule: true, default: MockPiecesSidebar, __testApi: api };
});

jest.mock('../SmartSuggestions', () => {
  const React = jest.requireActual('react');
  const api: any = { props: null };

  const MockSmartSuggestions = (props: any) => {
    api.props = props;
    return React.createElement(
      'div',
      { 'data-testid': 'smart-suggestions' },
      React.createElement(
        'button',
        {
          type: 'button',
          'data-testid': 'fire-suggestion',
          onClick: () =>
            props.onSuggestionClick({
              id: 's1',
              title: 'Add Condition',
              description: 'Branch the flow',
              type: 'condition',
              confidence: 0.8,
              reason: 'Filtering is common',
              icon: () => null,
            }),
        },
        'Suggest Condition'
      )
    );
  };

  return {
    __esModule: true,
    default: MockSmartSuggestions,
    __testApi: api,
  };
});

jest.mock('../NodeConfigSidebar', () => {
  const React = jest.requireActual('react');
  const api: any = { props: null };

  const MockNodeConfigSidebar = (props: any) => {
    api.props = props;
    return React.createElement(
      'div',
      { 'data-testid': 'node-config-sidebar' },
      React.createElement(
        'span',
        { 'data-testid': 'selected-node-label' },
        String(props.selectedNode?.data?.label ?? 'none')
      ),
      React.createElement(
        'button',
        {
          type: 'button',
          'data-testid': 'update-node',
          onClick: () =>
            props.onUpdateNode(props.selectedNode.id, {
              label: 'Updated Label',
              service: 'test',
            }),
        },
        'Update Node'
      ),
      React.createElement(
        'button',
        {
          type: 'button',
          'data-testid': 'close-config',
          onClick: () => props.onClose(),
        },
        'Close Config'
      )
    );
  };

  return { __esModule: true, default: MockNodeConfigSidebar, __testApi: api };
});

jest.mock('../LogsSidebar', () => {
  const React = jest.requireActual('react');
  return {
    LogsSidebar: (props: any) =>
      React.createElement(
        'div',
        { 'data-testid': 'logs-sidebar' },
        React.createElement('span', null, `Logs for ${props.workflowId}`),
        React.createElement(
          'button',
          {
            type: 'button',
            'data-testid': 'close-logs',
            onClick: () => props.onClose(),
          },
          'Close Logs'
        )
      ),
  };
});

jest.mock('../OptimizationPanel', () => {
  const React = jest.requireActual('react');
  const api: any = { props: null };
  const MockOptimizationPanel = (props: any) => {
    api.props = props;
    return React.createElement('div', { 'data-testid': 'optimization-panel' });
  };
  return { __esModule: true, default: MockOptimizationPanel, __testApi: api };
});

jest.mock('../AddStepEdge', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('../CustomNodes', () => ({ nodeTypes: {} }));

jest.mock('@/components/Voice/VoiceInput', () => {
  const React = jest.requireActual('react');
  const api: any = { props: null };
  const MockVoiceInput = (props: any) => {
    api.props = props;
    return React.createElement(
      'button',
      {
        type: 'button',
        'data-testid': 'voice-transcript',
        onClick: () => props.onTranscriptChange('clear the workflow via voice'),
      },
      'Voice'
    );
  };
  return { VoiceInput: MockVoiceInput, __testApi: api };
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const rfApi = () => (jest.requireMock('reactflow') as any).__testApi;
const undoRedoApi = () =>
  (jest.requireMock('@/hooks/useUndoRedo') as any).__testApi;
const optPanelApi = () =>
  (jest.requireMock('../OptimizationPanel') as any).__testApi;
const smartApi = () =>
  (jest.requireMock('../SmartSuggestions') as any).__testApi;
const toastMock = () =>
  (jest.requireMock('@/components/ui/use-toast') as any).__mockToast as jest.Mock;

const jsonResponse = (body: any, ok = true) => ({
  ok,
  status: ok ? 200 : 500,
  json: async () => body,
});

const getFlowProps = () => rfApi().flowProps as any;

const addToolbarNode = (label: string) => {
  fireEvent.click(screen.getByRole('button', { name: label }));
};

const simulateNodeDelete = (deletedIds: string[]) => {
  const api = rfApi();
  act(() => {
    api.setNodes((nds: any[]) =>
      nds.filter((n: any) => !deletedIds.includes(n.id))
    );
  });
  act(() => {
    getFlowProps().onNodesDelete(deletedIds.map((id) => ({ id })));
  });
};

describe('WorkflowBuilder', () => {
  let fetchSpy: jest.SpyInstance;

  beforeEach(() => {
    fetchSpy = jest
      .spyOn(global as any, 'fetch')
      .mockResolvedValue(jsonResponse({}));
    undoRedoApi().value = {
      undo: jest.fn(),
      redo: jest.fn(),
      takeSnapshot: jest.fn(),
      canUndo: false,
      canRedo: false,
      history: { past: [], present: null, future: [] },
      resetHistory: jest.fn(),
    };
  });

  // ------------------------------------------------------------------
  // Empty state / rendering
  // ------------------------------------------------------------------
  it('renders header, empty-state hint, and default pieces sidebar', () => {
    render(<WorkflowBuilder />);

    expect(
      screen.getByRole('heading', { name: 'AI Workflow Builder' })
    ).toBeInTheDocument();
    expect(screen.getByText('Start Building Your Workflow')).toBeInTheDocument();
    expect(screen.getByText('0 steps • 0 connections')).toBeInTheDocument();
    expect(screen.getByTestId('pieces-sidebar')).toBeInTheDocument();
    expect(screen.queryByTestId('smart-suggestions')).not.toBeInTheDocument();
    expect(screen.queryByTestId('node-config-sidebar')).not.toBeInTheDocument();
    expect(screen.queryByTestId('logs-sidebar')).not.toBeInTheDocument();
    expect(getFlowProps().nodes).toHaveLength(0);
    expect(getFlowProps().edges).toHaveLength(0);
  });

  // ------------------------------------------------------------------
  // Toolbar node creation
  // ------------------------------------------------------------------
  it('adds a Condition node from the toolbar and updates counters', () => {
    render(<WorkflowBuilder />);

    addToolbarNode('Condition');

    expect(screen.queryByText('Start Building Your Workflow')).not.toBeInTheDocument();
    expect(screen.getByText('1 steps • 0 connections')).toBeInTheDocument();
    const nodes = getFlowProps().nodes;
    expect(nodes).toHaveLength(1);
    expect(nodes[0]).toMatchObject({
      id: '1',
      type: 'condition',
      data: { label: 'Condition', condition: 'If true' },
    });
    expect(undoRedoApi().value.takeSnapshot).toHaveBeenCalledWith(
      expect.objectContaining({ nodes: expect.any(Array) })
    );
    expect(screen.getByTestId('smart-suggestions')).toBeInTheDocument();
  });

  it('adds each toolbar node type with the right default data', () => {
    render(<WorkflowBuilder />);

    const cases: Array<[string, string, string]> = [
      ['Loop', 'loop', 'Loop'],
      ['Code', 'code', 'Code'],
      ['AI', 'ai_node', 'AI Processing'],
      ['Approval', 'approval', 'Wait for Approval'],
      ['Delay', 'timer', 'Delay'],
    ];

    for (const [buttonLabel, type, dataLabel] of cases) {
      addToolbarNode(buttonLabel);
      const nodes = getFlowProps().nodes;
      const node = nodes[nodes.length - 1];
      expect(node.type).toBe(type);
      expect(node.data.label).toBe(dataLabel);
    }

    expect(screen.getByText('5 steps • 0 connections')).toBeInTheDocument();
    // ids stay unique even after many adds
    const ids = getFlowProps().nodes.map((n: any) => n.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  // ------------------------------------------------------------------
  // PiecesSidebar append flow
  // ------------------------------------------------------------------
  it('appends an action node connected to the previous node', () => {
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');

    fireEvent.click(screen.getByTestId('select-slack-action'));

    expect(screen.getByText('2 steps • 1 connections')).toBeInTheDocument();
    const nodes = getFlowProps().nodes;
    expect(nodes).toHaveLength(2);
    expect(nodes[1]).toMatchObject({
      type: 'action',
      data: {
        label: 'Post Message',
        service: 'Slack',
        serviceId: 'slack',
        action: 'post',
      },
    });
    const edges = getFlowProps().edges;
    expect(edges).toHaveLength(1);
    expect(edges[0]).toMatchObject({ source: '1', target: nodes[1].id });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Added Slack' })
    );
  });

  it('appends a trigger node without an edge on an empty canvas', () => {
    render(<WorkflowBuilder />);

    fireEvent.click(screen.getByTestId('select-gmail-trigger'));

    expect(screen.getByText('1 steps • 0 connections')).toBeInTheDocument();
    const nodes = getFlowProps().nodes;
    expect(nodes).toHaveLength(1);
    expect(nodes[0].type).toBe('trigger');
    expect(nodes[0].data.service).toBe('Gmail');
    expect(getFlowProps().edges).toHaveLength(0);
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Added Gmail',
        description: 'Trigger: New Email',
      })
    );
  });

  // ------------------------------------------------------------------
  // onConnect
  // ------------------------------------------------------------------
  it('adds an addStepEdge when connecting two nodes', () => {
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');
    addToolbarNode('Loop');

    act(() => {
      getFlowProps().onConnect({ source: '1', target: '2', id: 'e1-2' });
    });

    expect(screen.getByText('2 steps • 1 connections')).toBeInTheDocument();
    expect(getFlowProps().edges).toHaveLength(1);
    expect(getFlowProps().edges[0]).toMatchObject({
      id: 'e1-2',
      source: '1',
      target: '2',
      type: 'addStepEdge',
    });
    expect(undoRedoApi().value.takeSnapshot).toHaveBeenCalledWith(
      expect.objectContaining({ edges: expect.any(Array) })
    );
  });

  // ------------------------------------------------------------------
  // Edge-insertion flow (add-step between two nodes)
  // ------------------------------------------------------------------
  it('inserts a piece between connected nodes via the edge add-step handler', () => {
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');
    addToolbarNode('Loop');
    act(() => {
      getFlowProps().onConnect({ source: '1', target: '2', id: 'e1-2' });
    });

    // Trigger the edge's onAddStep (what AddStepEdge calls in production)
    const edge = getFlowProps().edges[0];
    expect(typeof edge.data.onAddStep).toBe('function');
    act(() => {
      edge.data.onAddStep('e1-2');
    });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Add Step' })
    );

    fireEvent.click(screen.getByTestId('select-slack-action'));

    expect(screen.getByText('3 steps • 2 connections')).toBeInTheDocument();
    const nodes = getFlowProps().nodes;
    const inserted = nodes.find((n: any) => n.data.service === 'Slack');
    expect(inserted).toBeDefined();
    expect(inserted.position.x).toBeGreaterThan(0);
    const edges = getFlowProps().edges;
    expect(edges).toHaveLength(2);
    expect(edges[0]).toMatchObject({ source: '1', target: inserted.id });
    expect(edges[1]).toMatchObject({ source: inserted.id, target: '2' });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Inserted Slack' })
    );
  });

  // ------------------------------------------------------------------
  // Node config sidebar
  // ------------------------------------------------------------------
  it('opens config sidebar on node click, updates node data, and closes', () => {
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');

    act(() => {
      getFlowProps().onNodeClick({} as any, getFlowProps().nodes[0]);
    });

    expect(screen.getByTestId('node-config-sidebar')).toBeInTheDocument();
    expect(screen.getByTestId('selected-node-label')).toHaveTextContent('Condition');

    fireEvent.click(screen.getByTestId('update-node'));
    expect(screen.getByTestId('selected-node-label')).toHaveTextContent('Updated Label');
    expect(getFlowProps().nodes[0].data).toMatchObject({ label: 'Updated Label' });

    fireEvent.click(screen.getByTestId('close-config'));
    expect(screen.queryByTestId('node-config-sidebar')).not.toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // Save
  // ------------------------------------------------------------------
  it('calls onSave with the current nodes and edges', () => {
    const onSave = jest.fn();
    render(<WorkflowBuilder onSave={onSave} />);
    addToolbarNode('Condition');
    addToolbarNode('Loop');
    act(() => {
      getFlowProps().onConnect({ source: '1', target: '2', id: 'e1-2' });
    });

    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    expect(onSave).toHaveBeenCalledTimes(1);
    const payload = onSave.mock.calls[0][0];
    expect(payload.nodes).toHaveLength(2);
    expect(payload.edges).toHaveLength(1);
  });

  it('shows a local-save toast when no onSave prop is provided', () => {
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');

    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Workflow Saved (Local)',
        description: 'Saved 1 nodes and 0 connections.',
      })
    );
  });

  // ------------------------------------------------------------------
  // Undo / Redo
  // ------------------------------------------------------------------
  it('disables undo/redo when history is empty and enables when available', () => {
    const { rerender } = render(<WorkflowBuilder />);

    expect(screen.getByTitle('Undo (Ctrl+Z)')).toBeDisabled();
    expect(screen.getByTitle('Redo (Ctrl+Shift+Z)')).toBeDisabled();

    undoRedoApi().value.canUndo = true;
    undoRedoApi().value.canRedo = true;
    rerender(<WorkflowBuilder />);

    fireEvent.click(screen.getByTitle('Undo (Ctrl+Z)'));
    fireEvent.click(screen.getByTitle('Redo (Ctrl+Shift+Z)'));

    expect(undoRedoApi().value.undo).toHaveBeenCalledTimes(1);
    expect(undoRedoApi().value.redo).toHaveBeenCalledTimes(1);
  });

  it('handles Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y keyboard shortcuts', () => {
    render(<WorkflowBuilder />);

    fireEvent.keyDown(window, { key: 'z', ctrlKey: true });
    fireEvent.keyDown(window, { key: 'z', ctrlKey: true, shiftKey: true });
    fireEvent.keyDown(window, { key: 'y', ctrlKey: true });
    // metaKey (mac) triggers undo too — but unrelated keys must not
    fireEvent.keyDown(window, { key: 'z', ctrlKey: true, metaKey: true });
    fireEvent.keyDown(window, { key: 'q', ctrlKey: true });

    expect(undoRedoApi().value.undo).toHaveBeenCalledTimes(2);
    expect(undoRedoApi().value.redo).toHaveBeenCalledTimes(2);
  });

  // ------------------------------------------------------------------
  // Performance mode
  // ------------------------------------------------------------------
  it('blocks performance mode without a workflowId', () => {
    render(<WorkflowBuilder />);

    fireEvent.click(screen.getByRole('button', { name: /performance/i }));

    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Performance Unavailable' })
    );
    expect(screen.getByRole('button', { name: /performance/i })).toHaveTextContent('Performance');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('fetches the heatmap and injects _analytics into nodes', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ '1': { avg_duration: 250, status: 'red' } })
    );
    render(
      <WorkflowBuilder
        workflowId="wf-1"
        initialData={{
          nodes: [
            {
              id: '1',
              type: 'action',
              position: { x: 0, y: 0 },
              data: { label: 'Slack Action', action: 'post' },
            },
          ],
          edges: [],
        }}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /performance/i }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith('/api/analytics/workflows/wf-1/heatmap');
    });
    await waitFor(() => {
      expect(getFlowProps().nodes[0].data._analytics).toEqual({
        duration: 250,
        status: 'error',
      });
    });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Performance Mode' })
    );

    // Toggling off clears the injected analytics
    fireEvent.click(screen.getByRole('button', { name: /performance on/i }));
    await waitFor(() => {
      expect(getFlowProps().nodes[0].data._analytics).toBeUndefined();
    });
  });

  it('survives a failed heatmap fetch', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, false));
    render(
      <WorkflowBuilder
        workflowId="wf-1"
        initialData={{
          nodes: [
            {
              id: '1',
              type: 'action',
              position: { x: 0, y: 0 },
              data: { label: 'Slack Action' },
            },
          ],
          edges: [],
        }}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /performance/i }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalled();
    });
    expect(getFlowProps().nodes[0].data._analytics).toBeUndefined();
  });

  // ------------------------------------------------------------------
  // Optimize
  // ------------------------------------------------------------------
  it('posts the workflow payload and renders suggestions', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ suggestions: [{ id: 's1', title: 'Add Slack' }] })
    );
    render(
      <WorkflowBuilder
        workflowId="wf-7"
        initialData={{
          nodes: [
            {
              id: '1',
              type: 'trigger',
              position: { x: 0, y: 0 },
              data: { label: 'Webhook' },
            },
            {
              id: '2',
              type: 'action',
              position: { x: 0, y: 100 },
              data: { label: 'Slack Action', service: 'slack' },
            },
          ],
          edges: [
            { id: 'e1-2', source: '1', target: '2', type: 'addStepEdge' },
          ],
        }}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /optimize/i }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/workflows/optimize',
        expect.objectContaining({ method: 'POST' })
      );
    });
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body.workflow_id).toBe('wf-7');
    expect(body.steps).toEqual([
      {
        step_id: '1',
        step_type: 'trigger',
        description: 'Webhook',
        parameters: expect.objectContaining({ label: 'Webhook', id: '1', _workflowId: 'wf-7' }),
        next_steps: ['2'],
      },
      {
        step_id: '2',
        step_type: 'action',
        description: 'Slack Action',
        parameters: expect.objectContaining({ label: 'Slack Action', service: 'slack' }),
        next_steps: [],
      },
    ]);

    await waitFor(() => {
      expect(optPanelApi().props.open).toBe(true);
      expect(optPanelApi().props.isLoading).toBe(false);
      expect(optPanelApi().props.suggestions).toEqual([
        { id: 's1', title: 'Add Slack' },
      ]);
    });
  });

  it('uses preview workflow id and toasts on optimize failure', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, false));
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');

    fireEvent.click(screen.getByRole('button', { name: /optimize/i }));

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Optimization Failed' })
      );
    });
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body.workflow_id).toBe('preview');
  });

  it('toasts an optimization error when the request throws', async () => {
    fetchSpy.mockRejectedValueOnce(new Error('network down'));
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');

    fireEvent.click(screen.getByRole('button', { name: /optimize/i }));

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Optimization Error',
          description: 'Error: network down',
        })
      );
    });
    expect(optPanelApi().props.isLoading).toBe(false);
  });

  // ------------------------------------------------------------------
  // AI Copilot chat
  // ------------------------------------------------------------------
  const typeMessage = (text: string) => {
    fireEvent.change(screen.getByPlaceholderText(/e\.g\.,/), {
      target: { value: text },
    });
  };

  it('generates a multi-step workflow from NLU actions', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({
        primaryGoal: 'workflow',
        extractedParameters: { service: 'slack' },
        rawSubAgentResponses: {
          workflow: { actions: [{ service: 'slack' }, { service: 'gmail' }] },
        },
      })
    );
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');

    typeMessage('create a workflow with slack then gmail');
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/agent/nlu',
        expect.objectContaining({ method: 'POST' })
      );
    });
    await waitFor(() => {
      expect(screen.getByText('2 steps • 1 connections')).toBeInTheDocument();
    });

    const nodes = getFlowProps().nodes;
    expect(nodes).toHaveLength(2);
    expect(nodes[0].type).toBe('trigger');
    expect(nodes[0].data.label).toBe('Slack Trigger');
    expect(nodes[1].type).toBe('action');
    expect(nodes[1].data.label).toBe('Gmail Action');
    expect(getFlowProps().edges).toHaveLength(1);
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'AI Copilot',
        description: 'Generated 2 steps workflow.',
      })
    );
    // input is cleared after processing
    expect((screen.getByPlaceholderText(/e\.g\.,/) as HTMLInputElement).value).toBe('');
  });

  it('falls back to a single service node when NLU returns no actions', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({
        primaryGoal: 'workflow',
        extractedParameters: { service: 'gmail' },
      })
    );
    render(<WorkflowBuilder />);

    typeMessage('post to gmail');
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));

    await waitFor(() => {
      expect(screen.getByText('1 steps • 0 connections')).toBeInTheDocument();
    });
    const nodes = getFlowProps().nodes;
    expect(nodes[0]).toMatchObject({
      type: 'action',
      data: { label: 'Gmail Action', service: 'Gmail' },
    });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'Added Gmail node via NLU.' })
    );
  });

  it('clears the workflow from a chat keyword', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ primaryGoal: 'chat', extractedParameters: {} })
    );
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');
    addToolbarNode('Loop');

    typeMessage('clear everything');
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));

    await waitFor(() => {
      expect(screen.getByText('0 steps • 0 connections')).toBeInTheDocument();
    });
    expect(getFlowProps().nodes).toHaveLength(0);
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'Cleared workflow.' })
    );
  });

  it('maps chat keywords to desktop, ai, and condition nodes', async () => {
    const nlu = { primaryGoal: 'chat', extractedParameters: {} };
    render(<WorkflowBuilder />);

    for (const [message, nodeType, label] of [
      ['add a desktop automation', 'desktop', 'Desktop Action'],
      ['analyze this with ai', 'ai_node', 'AI Processing'],
      ['add condition if overdue', 'condition', 'Condition'],
    ] as Array<[string, string, string]>) {
      fetchSpy.mockResolvedValueOnce(jsonResponse(nlu));
      typeMessage(message);
      fireEvent.click(screen.getByRole('button', { name: /generate/i }));
      await waitFor(() => {
        const nodes = getFlowProps().nodes;
        expect(nodes[nodes.length - 1].type).toBe(nodeType);
        expect(nodes[nodes.length - 1].data.label).toBe(label);
      });
    }
  });

  it('shows the intent toast for unrecognized messages', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ primaryGoal: 'chat', extractedParameters: {} })
    );
    render(<WorkflowBuilder />);

    typeMessage('hello there');
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          description: 'Intent: chat | Service: general. Try specifying a service like Slack, GMail, or GitHub.',
        })
      );
    });
  });

  it('uses keyword fallbacks when NLU fails', async () => {
    render(<WorkflowBuilder />);

    fetchSpy.mockRejectedValueOnce(new Error('nlu down'));
    typeMessage('add slack');
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));
    await waitFor(() => {
      expect(getFlowProps().nodes).toHaveLength(1);
      expect(getFlowProps().nodes[0].data.label).toBe('Slack Action');
    });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'Added Slack node (fallback).' })
    );

    fetchSpy.mockRejectedValueOnce(new Error('nlu down'));
    typeMessage('add desktop');
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));
    await waitFor(() => {
      expect(getFlowProps().nodes).toHaveLength(2);
      expect(getFlowProps().nodes[1].data.label).toBe('Desktop Action');
    });

    fetchSpy.mockRejectedValueOnce(new Error('nlu down'));
    typeMessage('clear');
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));
    await waitFor(() => {
      expect(getFlowProps().nodes).toHaveLength(0);
    });

    fetchSpy.mockRejectedValueOnce(new Error('nlu down'));
    typeMessage('something random');
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));
    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          description: "NLU unavailable. Try 'Add Slack' or 'Clear'.",
        })
      );
    });
  });

  it('sets the chat input from the voice transcript component', async () => {
    fetchSpy.mockResolvedValueOnce(
      jsonResponse({ primaryGoal: 'chat', extractedParameters: {} })
    );
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');

    fireEvent.click(screen.getByTestId('voice-transcript'));
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));

    await waitFor(() => {
      expect(screen.getByText('0 steps • 0 connections')).toBeInTheDocument();
    });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ description: 'Cleared workflow.' })
    );
  });

  it('ignores empty chat submissions', () => {
    render(<WorkflowBuilder />);

    typeMessage('   ');
    fireEvent.click(screen.getByRole('button', { name: /generate/i }));

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  // ------------------------------------------------------------------
  // Smart suggestions
  // ------------------------------------------------------------------
  it('adds a node from a smart suggestion', () => {
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');

    expect(smartApi().props.nodes).toHaveLength(1);
    expect(smartApi().props.edges).toHaveLength(0);

    fireEvent.click(screen.getByTestId('fire-suggestion'));

    expect(screen.getByText('2 steps • 0 connections')).toBeInTheDocument();
    const nodes = getFlowProps().nodes;
    expect(nodes[nodes.length - 1].type).toBe('condition');
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Added Add Condition' })
    );
  });

  // ------------------------------------------------------------------
  // Node/edge deletion + drag
  // ------------------------------------------------------------------
  it('prunes dangling edges when a node is deleted', () => {
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');
    addToolbarNode('Loop');
    act(() => {
      getFlowProps().onConnect({ source: '1', target: '2', id: 'e1-2' });
    });

    simulateNodeDelete(['1']);

    expect(screen.getByText('1 steps • 0 connections')).toBeInTheDocument();
    expect(getFlowProps().edges).toHaveLength(0);
    expect(undoRedoApi().value.takeSnapshot).toHaveBeenCalledWith(
      expect.objectContaining({ edges: [] })
    );
  });

  it('snapshots after edge deletion and node drag', () => {
    render(<WorkflowBuilder />);
    addToolbarNode('Condition');
    addToolbarNode('Loop');
    act(() => {
      getFlowProps().onConnect({ source: '1', target: '2', id: 'e1-2' });
    });
    undoRedoApi().value.takeSnapshot.mockClear();

    act(() => {
      getFlowProps().onEdgesDelete([{ id: 'e1-2' }]);
    });
    expect(undoRedoApi().value.takeSnapshot).toHaveBeenCalledWith(
      expect.objectContaining({ nodes: expect.any(Array) })
    );

    undoRedoApi().value.takeSnapshot.mockClear();
    act(() => {
      getFlowProps().onNodeDragStop({} as any, getFlowProps().nodes[0]);
    });
    expect(undoRedoApi().value.takeSnapshot).toHaveBeenCalled();
  });

  // ------------------------------------------------------------------
  // workflowId injection + history sync
  // ------------------------------------------------------------------
  it('injects workflowId and node id into every node', () => {
    render(
      <WorkflowBuilder
        workflowId="wf-9"
        initialData={{
          nodes: [
            {
              id: '1',
              type: 'action',
              position: { x: 0, y: 0 },
              data: { label: 'Slack Action' },
            },
          ],
          edges: [],
        }}
      />
    );

    expect(getFlowProps().nodes[0].data._workflowId).toBe('wf-9');
    expect(getFlowProps().nodes[0].data.id).toBe('1');

    addToolbarNode('Condition');
    expect(getFlowProps().nodes[1].data._workflowId).toBe('wf-9');
    expect(getFlowProps().nodes[1].data.id).toBe('2');
  });

  it('syncs nodes and edges from undo history.present', () => {
    undoRedoApi().value.history.present = {
      nodes: [
        {
          id: '99',
          type: 'action',
          position: { x: 0, y: 0 },
          data: { label: 'Restored' },
        },
      ],
      edges: [],
    };
    render(<WorkflowBuilder />);

    expect(getFlowProps().nodes).toHaveLength(1);
    expect(getFlowProps().nodes[0].id).toBe('99');
    expect(screen.getByText('1 steps • 0 connections')).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // Logs + sidebar toggles
  // ------------------------------------------------------------------
  it('toggles the logs panel only when a workflowId exists', () => {
    const { rerender } = render(<WorkflowBuilder />);
    // Toggling ON without a workflowId must not render the panel
    fireEvent.click(screen.getByRole('button', { name: /^logs$/i }));
    expect(screen.queryByTestId('logs-sidebar')).not.toBeInTheDocument();

    // State persists across rerender: panel appears once a workflowId exists
    rerender(<WorkflowBuilder workflowId="wf-1" />);
    expect(screen.getByTestId('logs-sidebar')).toBeInTheDocument();
    expect(screen.getByText('Logs for wf-1')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('close-logs'));
    expect(screen.queryByTestId('logs-sidebar')).not.toBeInTheDocument();
  });

  it('toggles the pieces sidebar', () => {
    render(<WorkflowBuilder />);
    expect(screen.getByTestId('pieces-sidebar')).toBeInTheDocument();

    // The sidebar toggle is the first toolbar button (PanelLeftClose icon);
    // locate it via its lucide icon class to stay robust.
    const toggle = document
      .querySelector('.lucide-panel-left-close')!
      .closest('button')!;
    fireEvent.click(toggle);
    expect(screen.queryByTestId('pieces-sidebar')).not.toBeInTheDocument();

    const reopen = document
      .querySelector('.lucide-panel-left')!
      .closest('button')!;
    fireEvent.click(reopen);
    expect(screen.getByTestId('pieces-sidebar')).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // Regressions
  // ------------------------------------------------------------------
  it('keeps node ids unique after deleting a middle node (BUG-039)', () => {
    render(
      <WorkflowBuilder
        initialData={{
          nodes: [
            {
              id: '1',
              type: 'action',
              position: { x: 0, y: 0 },
              data: { label: 'A' },
            },
            {
              id: '2',
              type: 'action',
              position: { x: 0, y: 100 },
              data: { label: 'B' },
            },
            {
              id: '3',
              type: 'action',
              position: { x: 0, y: 200 },
              data: { label: 'C' },
            },
          ],
          edges: [
            { id: 'e1-2', source: '1', target: '2' },
            { id: 'e2-3', source: '2', target: '3' },
          ],
        }}
      />
    );

    simulateNodeDelete(['2']);

    addToolbarNode('Condition');

    const ids = getFlowProps().nodes.map((n: any) => n.id);
    expect(new Set(ids).size).toBe(ids.length);
    // The new node must not reuse the id of the still-present node "3"
    expect(ids).toContain('4');
    expect(ids.filter((id: string) => id === '3')).toHaveLength(1);
  });

  it('does not crash on optimize or analytics when nodes lack data', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse({}));
    render(
      <WorkflowBuilder
        workflowId="wf-1"
        initialData={{
          nodes: [
            {
              id: '1',
              type: 'action',
              position: { x: 0, y: 0 },
            } as any,
          ],
          edges: [],
        }}
      />
    );

    // Optimize builds a payload from data-less nodes
    fireEvent.click(screen.getByRole('button', { name: /optimize/i }));
    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/workflows/optimize',
        expect.anything()
      );
    });
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body.steps[0].description).toBe('1');

    // Performance analytics injection also survives data-less nodes
    fetchSpy.mockResolvedValueOnce(jsonResponse({}));
    fireEvent.click(screen.getByRole('button', { name: /performance/i }));
    await waitFor(() => {
      expect(
        fetchSpy.mock.calls.some(
          ([url]: any) => url === '/api/analytics/workflows/wf-1/heatmap'
        )
      ).toBe(true);
    });
    expect(getFlowProps().nodes[0].data._analytics).toBeUndefined();
  });
});
