/**
 * WorkflowAutomation Component Tests
 *
 * Tests verify the real WorkflowAutomation component:
 * - Initial data loading (templates, workflows, executions, services)
 * - Template execution flow via the modal
 * - Workflow listing and Run flow
 * - Execution listing, details, cancel, resume, and time-travel fork
 * - Services listing
 * - Visual Builder toggle
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Notes on the real component:
 * - The project's shadcn Tabs is a CUSTOM implementation (plain <button>,
 *   no role="tab"), so tabs are queried as buttons.
 * - Progress is a custom <div> (no role="progressbar").
 * - WorkflowBuilder is mocked because the real one pulls in heavy canvas deps.
 *
 * Source: components/WorkflowAutomation.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import WorkflowAutomation from '@/components/WorkflowAutomation';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

// File-level router mock (overrides tests/setup.ts) with a mutable query so
// the URL-draft effect (router.query.draft) can be driven per test.
const mockRouter = {
  route: '/automation',
  pathname: '/automation',
  query: {} as Record<string, any>,
  asPath: '/automation',
  push: jest.fn(() => Promise.resolve(true)),
  replace: jest.fn(() => Promise.resolve(true)),
  reload: jest.fn(),
  back: jest.fn(),
  prefetch: jest.fn().mockResolvedValue(undefined),
  beforePopState: jest.fn(),
  events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
};
jest.mock('next/router', () => ({
  useRouter: () => mockRouter,
  default: { useRouter: () => mockRouter },
}));

// File-level use-toast mock (overrides tests/setup.ts) so toast calls can be
// asserted (error/success paths).
const mockToast = jest.fn();
const mockDismissToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): { toast: jest.Mock; dismiss: jest.Mock; toasts: any[] } => ({
    toast: mockToast,
    dismiss: mockDismissToast,
    toasts: [],
  }),
  ToastProvider: ({ children }: { children: any }) => children,
}));

// Mock WorkflowBuilder (heavy canvas component; only rendered in builder view)
jest.mock('@/components/Automations/WorkflowBuilder', () => {
  return function MockWorkflowBuilder(props: any) {
    const sampleData = {
      nodes: [
        {
          id: 'n1',
          type: 'action',
          position: { x: 0, y: 0 },
          data: { label: 'Send Email', service: 'email', action: 'send' },
        },
      ],
      edges: [] as any[],
    };
    // A fresh builder uses the sample graph; a builder opened from saved data
    // saves the graph it was given so round-trips can be exercised.
    const dataToSave = props.initialData || sampleData;
    const [reason, setReason] = React.useState('');
    return (
      <div data-testid="workflow-builder">
        <div>Workflow Builder</div>
        <div data-testid="builder-initial-data">
          {JSON.stringify(props.initialData)}
        </div>
        <label htmlFor="mock-workflow-save-reason">Save reason</label>
        <input
          id="mock-workflow-save-reason"
          data-testid="mock-workflow-save-reason"
          placeholder="Reason for change"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <button
          disabled={props.saving}
          onClick={() => props.onSave(dataToSave, { reason })}
        >
          Save
        </button>
        <button onClick={props.onCancel}>Cancel</button>
      </div>
    );
  };
});

const workflowHandlers = [
  rest.get('/api/workflow-templates/', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json([
        {
          template_id: 't1',
          name: 'Email Digest',
          description: 'Send a daily email digest',
          category: 'email',
          icon: 'mail',
          steps: [
            { id: 's1', type: 'trigger', service: 'schedule', action: 'daily', parameters: {}, name: 'Daily Trigger' },
            { id: 's2', type: 'action', service: 'email', action: 'send', parameters: {}, name: 'Send Email' },
          ],
          input_schema: { type: 'object', properties: {}, required: [] },
        },
      ])
    );
  }),

  rest.get('/api/v1/workflows/workflows', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        workflows: [
          {
            id: 'w1',
            name: 'Onboarding Flow',
            description: 'New hire onboarding',
            steps: [
              { id: 'ws1', type: 'trigger', service: 'slack', action: 'post', parameters: {}, name: 'Post to Slack' },
            ],
            input_schema: { type: 'object', properties: {}, required: [] },
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
            steps_count: 1,
          },
        ],
      })
    );
  }),

  // Real backend route: /api/v1/workflow-ui/executions (workflow_ui_endpoints.py)
  rest.get('/api/v1/workflow-ui/executions', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        executions: [
          {
            execution_id: 'e1',
            workflow_id: 'w1',
            status: 'running',
            start_time: '2024-01-01T00:00:00Z',
            current_step: 1,
            total_steps: 2,
            results: { step1: { foo: 'bar' } },
          },
          {
            execution_id: 'e2',
            workflow_id: 'w1',
            status: 'completed',
            start_time: '2024-01-01T00:00:00Z',
            end_time: '2024-01-01T00:05:00Z',
            current_step: 2,
            total_steps: 2,
          },
          {
            execution_id: 'e3',
            workflow_id: 'w1',
            status: 'paused',
            start_time: '2024-01-01T00:00:00Z',
            current_step: 1,
            total_steps: 3,
          },
        ],
      })
    );
  }),

  // Real backend route: /api/v1/workflow-ui/services (workflow_ui_endpoints.py)
  rest.get('/api/v1/workflow-ui/services', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        services: {
          email: { name: 'email', actions: ['send', 'draft'], description: 'Send and draft emails' },
          slack: { name: 'slack', actions: ['post', 'react'], description: 'Post to Slack' },
        },
      })
    );
  }),

  // Real backend route: POST /api/v1/workflows/workflows/{workflow_id}/execute
  // (core/workflow_endpoints.py). workflow_id lives in the PATH; body is the
  // raw input data; response is ExecutionResult (no `success` field).
  rest.post('/api/v1/workflows/workflows/:workflow_id/execute', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        execution_id: 'e4',
        workflow_id: req.params.workflow_id,
        status: 'running',
        started_at: '2024-01-01T00:00:00Z',
        results: [],
        errors: [],
      })
    );
  }),

  // Real backend route: POST /api/v1/workflow-ui/executions/{id}/cancel
  rest.post('/api/v1/workflow-ui/executions/:id/cancel', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  // Real backend route: POST /api/v1/workflows/workflows/{id}/resume
  rest.post('/api/v1/workflows/workflows/:id/resume', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ status: 'resumed', execution_id: req.params.id })
    );
  }),

  rest.post('/api/time-travel/workflows/:id/fork', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, new_execution_id: 'e-forked' }));
  }),
];

// Icon-only buttons (Eye icon in executions, etc.) have no accessible text.
const getIconButtons = () =>
  screen
    .getAllByRole('button')
    .filter((b) => b.querySelector('svg') && !(b.textContent || '').trim());

describe('WorkflowAutomation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRouter.query = {};
    server.resetHandlers();
    server.use(...workflowHandlers);
  });

  // Test 1: renders component
  test('renders component', async () => {
    render(<WorkflowAutomation />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /workflow automation/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: displays the main tab triggers (custom Tabs renders plain buttons)
  test('displays main tab buttons', async () => {
    render(<WorkflowAutomation />);

    await screen.findByRole('heading', { name: /workflow automation/i });

    expect(screen.getByRole('button', { name: 'Templates' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'My Workflows' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Executions' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Services' })).toBeInTheDocument();
  });

  // Test 3: shows template cards on the default templates tab
  test('shows template cards on the default templates tab', async () => {
    render(<WorkflowAutomation />);

    await waitFor(() => {
      expect(screen.getByText('Email Digest')).toBeInTheDocument();
    });
  });

  // Test 4: opens the template execution modal
  test('opens template execution modal', async () => {
    render(<WorkflowAutomation />);

    const useTemplateButton = await screen.findByRole('button', {
      name: /use template/i,
    });
    fireEvent.click(useTemplateButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: /use template: email digest/i })
      ).toBeInTheDocument();
    });
  });

  // Test 5: executes a template workflow (POST /api/v1/workflows/workflows/{id}/execute)
  test('executes a template workflow', async () => {
    const executePosts: any[] = [];
    server.use(
      rest.post('/api/v1/workflows/workflows/:workflow_id/execute', (req, res, ctx) => {
        executePosts.push({ workflow_id: req.params.workflow_id, body: req.body });
        return res(
          ctx.status(200),
          ctx.json({
            execution_id: 'e4',
            workflow_id: req.params.workflow_id,
            status: 'running',
            started_at: '2024-01-01T00:00:00Z',
            results: [],
            errors: [],
          })
        );
      })
    );

    render(<WorkflowAutomation />);

    const useTemplateButton = await screen.findByRole('button', {
      name: /use template/i,
    });
    fireEvent.click(useTemplateButton);

    const executeButton = await screen.findByRole('button', {
      name: /execute workflow/i,
    });
    fireEvent.click(executeButton);

    await waitFor(() => {
      expect(executePosts.some((b) => b.workflow_id === 't1')).toBe(true);
    });
  });

  // Test 6: displays workflows on the My Workflows tab
  test('displays workflows on the My Workflows tab', async () => {
    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));

    await waitFor(() => {
      expect(screen.getByText('Onboarding Flow')).toBeInTheDocument();
    });
  });

  // Test 7: opens workflow execution modal via Run button
  test('opens workflow execution modal via Run button', async () => {
    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));

    const runButton = await screen.findByRole('button', { name: 'Run' });
    fireEvent.click(runButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', {
          name: /execute workflow: onboarding flow/i,
        })
      ).toBeInTheDocument();
    });
  });

  // Test 8: shows empty state when there are no workflows
  test('shows empty state when there are no workflows', async () => {
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, workflows: [] }));
      })
    );

    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));

    await waitFor(() => {
      expect(screen.getByText('No workflows yet')).toBeInTheDocument();
    });
  });

  // Test 9: displays executions and progress on the Executions tab
  test('displays executions and progress on the Executions tab', async () => {
    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    await waitFor(() => {
      expect(screen.getByText('running')).toBeInTheDocument();
      expect(screen.getByText('completed')).toBeInTheDocument();
      expect(screen.getByText('paused')).toBeInTheDocument();
      expect(screen.getByText('1/2')).toBeInTheDocument();
    });
  });

  // Test 10: opens execution details modal via the eye button
  test('opens execution details modal', async () => {
    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    const eyeButtons = await screen.findByText('running').then(() =>
      getIconButtons()
    );
    fireEvent.click(eyeButtons[0]); // first execution (running, has results)

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /execution details/i })
      ).toBeInTheDocument();
      expect(screen.getByText(/execution id: e1/i)).toBeInTheDocument();
    });
  });

  // Test 11: opens the time-travel fork modal from execution details
  test('opens fork modal from execution details', async () => {
    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    await screen.findByText('running');
    fireEvent.click(getIconButtons()[0]); // open details for e1 (has results)

    // Radix Accordion: the Fork button lives inside the item content, which is
    // only mounted once the "Step: step1" trigger is expanded.
    const stepTrigger = await screen.findByRole('button', {
      name: /step: step1/i,
    });
    fireEvent.click(stepTrigger);

    const forkButton = await screen.findByRole('button', {
      name: /fork & time travel/i,
    });
    fireEvent.click(forkButton);

    await waitFor(() => {
      expect(
        screen.getByText(/time travel: fork from step step1/i)
      ).toBeInTheDocument();
    });
  });

  // Test 12: cancels a running execution
  test('cancels a running execution', async () => {
    const cancelledIds: any[] = [];
    server.use(
      rest.post('/api/v1/workflow-ui/executions/:id/cancel', (req, res, ctx) => {
        cancelledIds.push(req.params.id);
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    const cancelButton = await screen.findByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(cancelledIds).toContain('e1');
    });
  });

  // Test 13: opens resume modal for a paused execution
  test('opens resume modal for a paused execution', async () => {
    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    const resumeButton = await screen.findByRole('button', { name: 'Resume' });
    fireEvent.click(resumeButton);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /resume execution/i })
      ).toBeInTheDocument();
    });
  });

  // Test 14: displays services on the Services tab
  test('displays services on the Services tab', async () => {
    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Services' }));

    await waitFor(() => {
      expect(screen.getByText('email')).toBeInTheDocument();
      expect(screen.getByText('slack')).toBeInTheDocument();
    });
  });

  // Test 15: toggles Visual Builder view and back
  test('switches to builder view and back', async () => {
    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');

    const builderButton = screen.getByRole('button', {
      name: /visual builder/i,
    });
    fireEvent.click(builderButton);

    await waitFor(() => {
      expect(screen.getByTestId('workflow-builder')).toBeInTheDocument();
    });

    const classicButton = screen.getByRole('button', {
      name: /classic view/i,
    });
    fireEvent.click(classicButton);

    await waitFor(() => {
      expect(screen.queryByTestId('workflow-builder')).not.toBeInTheDocument();
    });
  });

  // Test 16: "Create Workflow" should open the Visual Builder for a NEW
  // workflow (fresh canvas), NOT the "Execute Workflow" modal. Regression:
  // the button wired to setIsCreateModalOpen(true), which opened the execution
  // modal with selectedWorkflow=null -> "Execute Workflow: undefined" title,
  // empty body, and a dead Execute button.
  test('Create Workflow button opens the visual builder for a new workflow', async () => {
    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');

    fireEvent.click(screen.getByRole('button', { name: /create workflow/i }));

    await waitFor(() => {
      expect(screen.getByTestId('workflow-builder')).toBeInTheDocument();
    });

    // Builder is in fresh state (not pre-populated from a selected workflow).
    expect(
      screen.queryByRole('heading', { name: /execute workflow: undefined/i })
    ).not.toBeInTheDocument();
  });

  // Test 17: saving from the Visual Builder must POST to the durable v1 store
  // (/api/v1/workflows/workflows) so the workflow persists and appears in "My
  // Workflows". Regression: it posted to /api/v1/workflow-ui/definitions which
  // wrote to an in-memory mock — the workflow never appeared in the list.
  test('saves a builder workflow and shows it in My Workflows', async () => {
    let savedPayload: any = null;
    server.use(
      rest.post('/api/v1/workflows/workflows', (req, res, ctx) => {
        savedPayload = req.body;
        return res(
          ctx.status(200),
          ctx.json({
            id: 'new-wf-1',
            name: savedPayload.name,
            description: savedPayload.description,
            version: '1.0',
            nodes: savedPayload.nodes,
            connections: savedPayload.connections,
            triggers: [],
            enabled: true,
            createdAt: '2024-01-01T00:00:00Z',
            updatedAt: '2024-01-01T00:00:00Z',
          })
        );
      }),
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) => {
        const list: any[] = [
          {
            id: 'w1',
            name: 'Onboarding Flow',
            description: 'New hire onboarding',
            steps: [],
            input_schema: { type: 'object', properties: {}, required: [] },
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
            steps_count: 0,
          },
        ];
        if (savedPayload) {
          list.push({
            id: 'new-wf-1',
            name: savedPayload.name,
            description: savedPayload.description,
            steps: [],
            input_schema: {},
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
            steps_count: 0,
          });
        }
        return res(ctx.status(200), ctx.json(list));
      })
    );

    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');

    // Open the Visual Builder and click Save (mock passes node-based data).
    fireEvent.click(screen.getByRole('button', { name: /visual builder/i }));
    await screen.findByTestId('workflow-builder');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    // The save must hit the durable v1 endpoint with a node-based payload.
    await waitFor(() => {
      expect(savedPayload).not.toBeNull();
      expect(savedPayload.nodes[0].title).toBe('Send Email');
      expect(savedPayload.nodes[0].config.service).toBe('email');
      // A fresh canvas uses the backend defaults rather than inventing triggers.
      expect(savedPayload.triggers).toEqual([]);
      expect(savedPayload.enabled).toBe(true);
    });

    // Switch back to Classic View and confirm the saved workflow shows up.
    fireEvent.click(screen.getByRole('button', { name: /classic view/i }));
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    await screen.findByText(/visual workflow/i);
  });

  // Test 18: node-based (graph) workflows — the durable /workflows store shape
  // ({nodes, connections}, no `steps`) — must render a non-zero steps badge and
  // open in the Visual Builder WITHOUT crashing. Regression: the builder-edit
  // path called selectedWorkflow.steps.map, which threw on a node-based
  // workflow (no `steps`), and the badge showed "0 steps".
  test('renders node-based workflows and opens them in the builder', async () => {
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([
            {
              id: 'node-wf',
              name: 'Node Graph Workflow',
              description: 'Saved from the visual builder',
              version: '1.0',
              nodes: [
                { id: 'n1', type: 'trigger', title: 'Daily Trigger', description: '', position: { x: 0, y: 0 }, config: { service: 'schedule', action: 'daily', parameters: {} }, connections: [] },
                { id: 'n2', type: 'action', title: 'Send Email', description: '', position: { x: 0, y: 200 }, config: { service: 'email', action: 'send', parameters: {} }, connections: [] },
              ],
              connections: [{ id: 'c1', source: 'n1', target: 'n2' }],
              triggers: [],
              enabled: true,
            },
          ])
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));

    // Node-based workflow renders with a non-zero steps badge (nodes.length).
    await screen.findByText('Node Graph Workflow');
    expect(screen.getByText('2 steps')).toBeInTheDocument();

    // Run selects the workflow; opening the Visual Builder must not crash.
    fireEvent.click(screen.getByRole('button', { name: 'Run' }));
    await screen.findByRole('heading', {
      name: /execute workflow: node graph workflow/i,
    });

    fireEvent.click(screen.getByRole('button', { name: /visual builder/i }));
    expect(
      await screen.findByTestId('workflow-builder')
    ).toBeInTheDocument();
  });

  // Test 18b: reopening a saved graph preserves flat and nested node config,
  // the node description/action, and the connection condition string.
  test('round-trips saved node config and connection conditions into the builder', async () => {
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([
            {
              id: 'roundtrip-wf',
              name: 'Round Trip Workflow',
              description: 'Saved graph',
              version: '1.0',
              nodes: [
                {
                  id: 'n1',
                  type: 'action',
                  title: 'Send Email',
                  description: 'Notify the customer',
                  position: { x: 10, y: 20 },
                  config: {
                    service: 'email',
                    action: 'send',
                    subject: 'Hello',
                    priority: 3,
                    parameters: { cc: 'team@example.com' },
                  },
                  connections: [],
                },
                {
                  id: 'n2',
                  type: 'action',
                  title: 'Post Slack',
                  description: '',
                  position: { x: 10, y: 220 },
                  config: {
                    service: 'slack',
                    action: 'post',
                    parameters: { channel: '#general', retries: 2 },
                  },
                  connections: [],
                },
              ],
              connections: [
                { id: 'c1', source: 'n1', target: 'n2', condition: 'priority > 1' },
              ],
              triggers: ['schedule.daily'],
              enabled: false,
            },
          ])
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run' }));
    await screen.findByRole('heading', {
      name: /execute workflow: round trip workflow/i,
    });
    fireEvent.click(screen.getByRole('button', { name: /visual builder/i }));

    await waitFor(() => {
      const initialData = JSON.parse(
        screen.getByTestId('builder-initial-data').textContent || 'null'
      );
      const first = initialData.nodes.find((n: any) => n.id === 'n1');
      const second = initialData.nodes.find((n: any) => n.id === 'n2');

      expect(first.data).toEqual(
        expect.objectContaining({
          label: 'Send Email',
          description: 'Notify the customer',
          service: 'email',
          action: 'send',
          subject: 'Hello',
          priority: 3,
          cc: 'team@example.com',
        })
      );
      expect(second.data).toEqual(
        expect.objectContaining({
          label: 'Post Slack',
          service: 'slack',
          action: 'post',
          channel: '#general',
          retries: 2,
        })
      );
      expect(initialData.edges).toEqual([
        {
          id: 'c1',
          source: 'n1',
          target: 'n2',
          type: 'addStepEdge',
          data: { condition: 'priority > 1' },
        },
      ]);
    });
  });

  // Test 18c: saving a reused graph POSTs a create (there is no update
  // contract), but preserves the saved triggers/enabled verbatim, plus node
  // descriptions/config and connection conditions.
  test('preserves persisted triggers, enabled and edge conditions when re-saving', async () => {
    let savedPayload: any = null;
    let savedMethod = '';
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([
            {
              id: 'reused-wf',
              name: 'Reused Workflow',
              description: 'Existing graph',
              version: '1.0',
              nodes: [
                {
                  id: 'n1',
                  type: 'action',
                  title: 'Send Email',
                  description: 'Notify the customer',
                  position: { x: 10, y: 20 },
                  config: {
                    service: 'email',
                    action: 'send',
                    parameters: { subject: 'Hello', priority: 3, cc: 'team@example.com' },
                    continue_on_error: true,
                    timeout: 30,
                    input_schema: { type: 'object' },
                    output_schema: { type: 'object' },
                  },
                  connections: [],
                },
                {
                  id: 'n2',
                  type: 'action',
                  title: 'Post Slack',
                  description: 'Tell the team',
                  position: { x: 10, y: 220 },
                  config: { service: 'slack', action: 'post', channel: '#general' },
                  connections: [],
                },
              ],
              connections: [
                { id: 'c1', source: 'n1', target: 'n2', condition: 'priority > 1' },
              ],
              triggers: ['schedule.daily', 'webhook.received'],
              enabled: false,
            },
          ])
        );
      }),
      rest.post('/api/v1/workflows/workflows', (req, res, ctx) => {
        savedMethod = req.method;
        savedPayload = req.body;
        return res(
          ctx.status(200),
          ctx.json({
            id: 'created-from-reused-wf',
            name: savedPayload.name,
            description: savedPayload.description,
            nodes: savedPayload.nodes,
            connections: savedPayload.connections,
            triggers: savedPayload.triggers,
            enabled: savedPayload.enabled,
          })
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run' }));
    await screen.findByRole('heading', {
      name: /execute workflow: reused workflow/i,
    });
    fireEvent.click(screen.getByRole('button', { name: /visual builder/i }));
    await screen.findByTestId('workflow-builder');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(savedPayload).not.toBeNull();
    });

    expect(savedMethod).toBe('POST');
    expect(savedPayload.id).toBeUndefined();
    expect(savedPayload.triggers).toEqual(['schedule.daily', 'webhook.received']);
    expect(savedPayload.enabled).toBe(false);

    const first = savedPayload.nodes.find((n: any) => n.id === 'n1');
    const second = savedPayload.nodes.find((n: any) => n.id === 'n2');
    expect(first.description).toBe('Notify the customer');
    expect(first.config).toEqual(
      expect.objectContaining({
        service: 'email',
        action: 'send',
        continue_on_error: true,
        timeout: 30,
        input_schema: { type: 'object' },
        output_schema: { type: 'object' },
        parameters: {
          subject: 'Hello',
          priority: 3,
          cc: 'team@example.com',
        },
      })
    );
    expect(second.description).toBe('Tell the team');
    expect(second.config).toEqual(
      expect.objectContaining({
        service: 'slack',
        action: 'post',
        parameters: { channel: '#general' },
      })
    );
    expect(savedPayload.connections).toEqual([
      { id: 'c1', source: 'n1', target: 'n2', condition: 'priority > 1' },
    ]);
  });

  // Test 18d: the card Edit action loads the canonical workflow by ID and saves
  // in place with PUT, using the loaded revision, audit reason, and preserved
  // graph/config/settings.
  test('edits a saved visual workflow in place with revision and reason', async () => {
    const detailWorkflow = {
      id: 'edit-wf',
      name: 'Saved Display Name',
      description: 'Persisted description',
      version: '2.1',
      revision: 7,
      nodes: [
        {
          id: 'n1',
          type: 'action',
          title: 'Send Email',
          description: 'Notify the customer',
          position: { x: 10, y: 20 },
          config: {
            service: 'email',
            action: 'send',
            parameters: { subject: 'Hello', priority: 3, cc: 'team@example.com' },
            continue_on_error: true,
            timeout: 30,
            input_schema: { type: 'object' },
            output_schema: { type: 'object' },
          },
          connections: [],
        },
        {
          id: 'n2',
          type: 'action',
          title: 'Post Slack',
          description: 'Tell the team',
          position: { x: 10, y: 220 },
          config: { service: 'slack', action: 'post', parameters: { channel: '#general' } },
          connections: [],
        },
      ],
      connections: [
        { id: 'c1', source: 'n1', target: 'n2', condition: 'priority > 1' },
      ],
      triggers: ['schedule.daily'],
      enabled: false,
    };
    let detailGets = 0;
    let postCalls = 0;
    const puts: any[] = [];
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([
            {
              ...detailWorkflow,
              name: 'Stale List Name',
              revision: 1,
              nodes: [
                {
                  ...detailWorkflow.nodes[0],
                  title: 'Stale List Node',
                  config: { service: 'email', action: 'send', parameters: {} },
                },
              ],
              connections: [],
            },
          ])
        );
      }),
      rest.get('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) => {
        detailGets += 1;
        expect(req.params.workflow_id).toBe('edit-wf');
        return res(ctx.status(200), ctx.json(detailWorkflow));
      }),
      rest.post('/api/v1/workflows/workflows', (req, res, ctx) => {
        postCalls += 1;
        return res(ctx.status(500), ctx.json({ detail: 'unexpected create' }));
      }),
      rest.put('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) => {
        puts.push({
          id: req.params.workflow_id,
          url: req.url?.toString(),
          method: req.method,
          body: req.body,
        });
        return res(
          ctx.status(200),
          ctx.json({
            ...detailWorkflow,
            ...req.body,
            id: 'edit-wf',
            revision: 8,
          })
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    await screen.findByText('Stale List Name');

    fireEvent.click(screen.getByRole('button', { name: 'Edit workflow' }));

    await waitFor(() => {
      expect(detailGets).toBe(1);
      const initialData = JSON.parse(
        screen.getByTestId('builder-initial-data').textContent || 'null'
      );
      expect(initialData.nodes[0].data).toEqual(
        expect.objectContaining({
          label: 'Send Email',
          description: 'Notify the customer',
          service: 'email',
          action: 'send',
          subject: 'Hello',
          priority: 3,
          cc: 'team@example.com',
          continue_on_error: true,
          timeout: 30,
          input_schema: { type: 'object' },
          output_schema: { type: 'object' },
        })
      );
      expect(initialData.edges).toEqual([
        {
          id: 'c1',
          source: 'n1',
          target: 'n2',
          type: 'addStepEdge',
          data: { condition: 'priority > 1' },
        },
      ]);
    });

    fireEvent.change(screen.getByLabelText('Save reason'), {
      target: { value: 'Fix recipient' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(puts).toHaveLength(1);
    });

    expect(puts[0].id).toBe('edit-wf');
    expect(puts[0].method).toBe('PUT');
    expect(puts[0].url).toContain('/api/v1/workflows/workflows/edit-wf');
    expect(puts[0].body).toEqual(
      expect.objectContaining({
        revision: 7,
        reason: 'Fix recipient',
        name: 'Saved Display Name',
        description: 'Persisted description',
        version: '2.1',
        triggers: ['schedule.daily'],
        enabled: false,
      })
    );
    expect(puts[0].body.id).toBeUndefined();
    expect(puts[0].body.nodes[0].config).toEqual(
      expect.objectContaining({
        service: 'email',
        action: 'send',
        continue_on_error: true,
        timeout: 30,
        input_schema: { type: 'object' },
        output_schema: { type: 'object' },
        parameters: {
          subject: 'Hello',
          priority: 3,
          cc: 'team@example.com',
        },
      })
    );
    expect(puts[0].body.connections).toEqual([
      { id: 'c1', source: 'n1', target: 'n2', condition: 'priority > 1' },
    ]);
    expect(postCalls).toBe(0);

    // The successful response's same ID and new revision are used by the next
    // save on the same URL.
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Workflow Updated' })
      );
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Save' })).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => {
      expect(puts).toHaveLength(2);
    });
    expect(puts[1].id).toBe('edit-wf');
    expect(puts[1].body.revision).toBe(8);
    expect(postCalls).toBe(0);
  });

  test('preserves registered event binding at config root across revision saves and reopen', async () => {
    const binding = { connection_id: 'connection-one', source: 'synthetic-mail',
      event_type: 'message.created', enabled: true };
    let stored: any = {
      id: 'event-workflow', name: 'Saved Event Route', description: 'Route source events',
      version: '1', revision: 7, enabled: true, triggers: ['event'],
      event_subscriptions: [{ id: 'trigger-one', ...binding }],
      nodes: [{ id: 'trigger-one', type: 'trigger', title: 'New message',
        description: 'Saved source', position: { x: 0, y: 0 }, connections: [],
        config: { service: 'synthetic-mail', action: 'message.created',
          event_subscription: binding, parameters: {} } }], connections: [],
    };
    const puts: any[] = [];
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) =>
        res(ctx.json([stored]))),
      rest.get('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) =>
        res(ctx.json(stored))),
      rest.put('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) => {
        puts.push(req.body);
        stored = { ...stored, ...(req.body as any), revision: stored.revision + 1 };
        return res(ctx.json(stored));
      }),
    );
    const mounted = render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    await screen.findByText('Saved Event Route');
    fireEvent.click(screen.getByRole('button', { name: 'Edit workflow' }));
    await screen.findByTestId('builder-initial-data');
    fireEvent.change(screen.getByLabelText('Save reason'), {
      target: { value: 'Keep source binding' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0].revision).toBe(7);
    expect(puts[0].nodes[0].id).toBe('trigger-one');
    expect(puts[0].nodes[0].config.event_subscription).toEqual(binding);
    expect(puts[0].nodes[0].config.parameters.event_subscription).toBeUndefined();
    mounted.unmount();
    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    await screen.findByText('Saved Event Route');
    fireEvent.click(screen.getByRole('button', { name: 'Edit workflow' }));
    await screen.findByTestId('builder-initial-data');
    fireEvent.change(screen.getByLabelText('Save reason'), { target: { value: 'Reopen saved event' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(puts).toHaveLength(2));
    expect(puts[1].revision).toBe(8);
    expect(puts[1].nodes[0].config.event_subscription).toEqual(binding);
    expect(puts[1].nodes[0].config.parameters.event_subscription).toBeUndefined();
  });

  // Test 18e: a stale revision (409) must keep the local graph visible and
  // point the user at an explicit reload instead of silently overwriting.
  test('keeps local changes and shows reload guidance on a stale 409', async () => {
    const detailWorkflow = {
      id: 'stale-wf',
      name: 'Stale Workflow',
      description: 'Existing graph',
      version: '1.0',
      revision: 3,
      nodes: [
        {
          id: 'n1',
          type: 'action',
          title: 'Send Email',
          description: '',
          position: { x: 0, y: 0 },
          config: { service: 'email', action: 'send', parameters: { subject: 'Hello' } },
          connections: [],
        },
      ],
      connections: [],
      triggers: ['schedule.daily'],
      enabled: true,
    };
    let detailGets = 0;
    let putCalls = 0;
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([detailWorkflow]))
      ),
      rest.get('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) => {
        detailGets += 1;
        return res(
          ctx.status(200),
          ctx.json({ ...detailWorkflow, revision: detailGets === 1 ? 3 : 4 })
        );
      }),
      rest.put('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) => {
        putCalls += 1;
        return res(
          ctx.status(409),
          ctx.json({
            detail: {
              error: 'revision_conflict',
              current_revision: 4,
              message: 'Workflow revision is stale',
            },
          })
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    await screen.findByText('Stale Workflow');
    fireEvent.click(screen.getByRole('button', { name: 'Edit workflow' }));

    await screen.findByTestId('workflow-builder');
    await waitFor(() => expect(detailGets).toBe(1));

    const initialDataBefore = screen.getByTestId('builder-initial-data').textContent;
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(screen.getByText(/your local changes are still here/i)).toBeInTheDocument();
    });
    expect(putCalls).toBe(1);
    expect(screen.getByTestId('workflow-builder')).toBeInTheDocument();
    expect(screen.getByTestId('builder-initial-data').textContent).toBe(
      initialDataBefore
    );
    expect(
      screen.getByRole('button', { name: /reload latest/i })
    ).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Reload required' })
    );

    // Reload guidance performs the GET again and clears the conflict state.
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /reload latest/i })
      ).not.toBeDisabled();
    });
    fireEvent.click(screen.getByRole('button', { name: /reload latest/i }));
    await waitFor(() => expect(detailGets).toBe(2));
    await waitFor(() => {
      expect(screen.queryByTestId('builder-save-error')).not.toBeInTheDocument();
    });
  });

  // Test 18f: while a save is pending, further Save clicks must not issue a
  // duplicate PUT for the same edit session.
  test('does not duplicate a pending same-ID save', async () => {
    const detailWorkflow = {
      id: 'dup-wf',
      name: 'Duplicate Guard',
      description: '',
      version: '1.0',
      revision: 2,
      nodes: [
        {
          id: 'n1',
          type: 'action',
          title: 'Send Email',
          description: '',
          position: { x: 0, y: 0 },
          config: { service: 'email', action: 'send', parameters: {} },
          connections: [],
        },
      ],
      connections: [],
      triggers: [],
      enabled: true,
    };
    let putCalls = 0;
    let releasePut: (() => void) | null = null;
    const putGate = new Promise<void>((resolve) => {
      releasePut = resolve;
    });
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([detailWorkflow]))
      ),
      rest.get('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) =>
        res(ctx.status(200), ctx.json(detailWorkflow))
      ),
      rest.put('/api/v1/workflows/workflows/:workflow_id', async (req, res, ctx) => {
        putCalls += 1;
        await putGate;
        return res(
          ctx.status(200),
          ctx.json({ ...detailWorkflow, revision: 3 })
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    await screen.findByText('Duplicate Guard');
    fireEvent.click(screen.getByRole('button', { name: 'Edit workflow' }));
    await screen.findByTestId('workflow-builder');

    const save = screen.getByRole('button', { name: 'Save' });
    fireEvent.click(save);
    fireEvent.click(save);
    fireEvent.click(save);

    await waitFor(() => expect(putCalls).toBe(1));
    expect(putCalls).toBe(1);

    await act(async () => {
      releasePut?.();
    });
    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Workflow Updated' })
      );
    });
    expect(putCalls).toBe(1);
  });

  // Test 18g: reopening a saved workflow must surface only the persisted
  // correction history returned by the canonical GET, in a collapsed section.
  test('shows persisted change history when reopening a saved workflow', async () => {
    const detailWorkflow = {
      id: 'history-wf',
      name: 'History Workflow',
      description: 'Has persisted audit entries',
      version: '1.0',
      revision: 5,
      nodes: [
        {
          id: 'n1',
          type: 'action',
          title: 'Send Email',
          description: '',
          position: { x: 0, y: 0 },
          config: { service: 'email', action: 'send', parameters: {} },
          connections: [],
        },
      ],
      connections: [],
      triggers: [],
      enabled: true,
      corrections: [
        {
          who: 'alex@example.com',
          when: '2024-02-03T04:05:06Z',
          reason: 'Corrected recipient',
          before_revision: 4,
          after_revision: 5,
        },
      ],
    };

    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) => {
        // The list projection is stale and does not carry corrections; the
        // canonical detail GET must supply the history when the card is opened.
        const listWorkflow: any = { ...detailWorkflow, revision: 1 };
        delete listWorkflow.corrections;
        return res(ctx.status(200), ctx.json([listWorkflow]));
      }),
      rest.get('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) => {
        expect(req.params.workflow_id).toBe('history-wf');
        return res(ctx.status(200), ctx.json(detailWorkflow));
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    await screen.findByText('History Workflow');

    fireEvent.click(screen.getByRole('button', { name: 'Edit workflow' }));
    await screen.findByTestId('workflow-builder');

    const history = await screen.findByTestId('workflow-change-history');
    expect(history).not.toHaveAttribute('open');

    fireEvent.click(within(history).getByText('Change history'));

    expect(within(history).getByText('Reason')).toBeInTheDocument();
    expect(within(history).getByText('Actor')).toBeInTheDocument();
    expect(within(history).getByText('Time')).toBeInTheDocument();
    expect(within(history).getByText('Revisions')).toBeInTheDocument();
    expect(within(history).getByText('Corrected recipient')).toBeInTheDocument();
    expect(within(history).getByText('alex@example.com')).toBeInTheDocument();
    expect(
      within(history).getByText('2024-02-03T04:05:06Z')
    ).toBeInTheDocument();
    expect(within(history).getByText(/4\s*→\s*5/)).toBeInTheDocument();

    // Reopening the same saved workflow loads the same persisted history from
    // the canonical GET again (no local sample/fallback data).
    fireEvent.click(screen.getByRole('button', { name: /classic view/i }));
    await screen.findByText('History Workflow');
    fireEvent.click(screen.getByRole('button', { name: 'Edit workflow' }));
    await screen.findByTestId('workflow-builder');

    const reopenedHistory = await screen.findByTestId('workflow-change-history');
    fireEvent.click(within(reopenedHistory).getByText('Change history'));
    expect(
      within(reopenedHistory).getByText('Corrected recipient')
    ).toBeInTheDocument();
    expect(
      within(reopenedHistory).getByText('alex@example.com')
    ).toBeInTheDocument();
  });

  // Test 18h: a successful PUT returns the authoritative corrections; the
  // collapsed history must be refreshed with the newly persisted entry without
  // reopening the workflow or opening another modal.
  test('updates change history after a successful save', async () => {
    const initialCorrections = [
      {
        who: 'alex@example.com',
        when: '2024-02-03T04:05:06Z',
        reason: 'Initial correction',
        before_revision: 4,
        after_revision: 5,
      },
    ];
    const detailWorkflow = {
      id: 'history-save-wf',
      name: 'History Save Workflow',
      description: 'Has persisted audit entries',
      version: '1.0',
      revision: 5,
      nodes: [
        {
          id: 'n1',
          type: 'action',
          title: 'Send Email',
          description: '',
          position: { x: 0, y: 0 },
          config: { service: 'email', action: 'send', parameters: {} },
          connections: [],
        },
      ],
      connections: [],
      triggers: [],
      enabled: true,
      corrections: initialCorrections,
    };
    const puts: any[] = [];
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([detailWorkflow]))
      ),
      rest.get('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) =>
        res(ctx.status(200), ctx.json(detailWorkflow))
      ),
      rest.put('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) => {
        puts.push({ id: req.params.workflow_id, body: req.body });
        const nextCorrection = {
          who: 'sam@example.com',
          when: '2024-02-04T05:06:07Z',
          reason: req.body.reason,
          before_revision: 5,
          after_revision: 6,
        };
        return res(
          ctx.status(200),
          ctx.json({
            ...detailWorkflow,
            ...req.body,
            id: 'history-save-wf',
            revision: 6,
            corrections: [...initialCorrections, nextCorrection],
          })
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    await screen.findByText('History Save Workflow');
    fireEvent.click(screen.getByRole('button', { name: 'Edit workflow' }));
    await screen.findByTestId('workflow-builder');

    const history = await screen.findByTestId('workflow-change-history');
    fireEvent.click(within(history).getByText('Change history'));
    expect(within(history).getByText('Initial correction')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Save reason'), {
      target: { value: 'Fix recipient' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0].id).toBe('history-save-wf');
    expect(puts[0].body.reason).toBe('Fix recipient');

    await waitFor(() => {
      expect(within(history).getByText('Fix recipient')).toBeInTheDocument();
    });
    expect(within(history).getByText('sam@example.com')).toBeInTheDocument();
    expect(
      within(history).getByText('2024-02-04T05:06:07Z')
    ).toBeInTheDocument();
    expect(within(history).getByText(/5\s*→\s*6/)).toBeInTheDocument();
  });

  // Test 18i: the saved-card Edit action and the builder reason field must be
  // usable by their real accessible names, not by icon/DOM heuristics.
  test('exposes the saved card edit action and reason field by accessible labels', async () => {
    const detailWorkflow = {
      id: 'accessible-wf',
      name: 'Accessible Workflow',
      description: '',
      version: '1.0',
      revision: 1,
      nodes: [
        {
          id: 'n1',
          type: 'action',
          title: 'Send Email',
          description: '',
          position: { x: 0, y: 0 },
          config: { service: 'email', action: 'send', parameters: {} },
          connections: [],
        },
      ],
      connections: [],
      triggers: [],
      enabled: true,
    };

    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) =>
        res(ctx.status(200), ctx.json([detailWorkflow]))
      ),
      rest.get('/api/v1/workflows/workflows/:workflow_id', (req, res, ctx) =>
        res(ctx.status(200), ctx.json(detailWorkflow))
      )
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    await screen.findByText('Accessible Workflow');

    const editButton = screen.getByRole('button', { name: 'Edit workflow' });
    expect(editButton).toBeInTheDocument();
    expect(editButton).toHaveAttribute('title', 'Edit Accessible Workflow');
    fireEvent.click(editButton);

    const reasonInput = await screen.findByLabelText('Save reason');
    expect(reasonInput).toHaveAttribute('id', 'mock-workflow-save-reason');
    expect(reasonInput).not.toHaveAttribute('aria-label');
    const nativeLabel = document.querySelector(
      'label[for="mock-workflow-save-reason"]'
    );
    expect(nativeLabel).not.toBeNull();
    expect(nativeLabel).toHaveTextContent('Save reason');
  });

  // Test 19: triggerNew prop (>0) opens the Visual Builder for a fresh workflow
  test('triggerNew prop opens the visual builder', async () => {
    render(<WorkflowAutomation triggerNew={1} />);

    await waitFor(() => {
      expect(screen.getByTestId('workflow-builder')).toBeInTheDocument();
    });
    // Fresh canvas: no workflow selected.
    const initialData = JSON.parse(
      screen.getByTestId('builder-initial-data').textContent || 'null'
    );
    expect(initialData).toBeNull();
  });

  // Test 20: a `draft` URL query loads the draft into the builder, toasts, and
  // cleans the URL
  test('loads workflow draft from URL query', async () => {
    mockRouter.query.draft = JSON.stringify({
      nodes: [{ id: 'd1', type: 'trigger', data: { label: 'Draft Node' } }],
      edges: [],
    });

    render(<WorkflowAutomation />);

    await waitFor(() => {
      expect(screen.getByTestId('workflow-builder')).toBeInTheDocument();
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Draft Loaded' })
    );
    expect(mockRouter.replace).toHaveBeenCalledWith(
      '/automation',
      undefined,
      { shallow: true }
    );
  });

  // Test 21: AI generative create turns a prompt into a builder draft
  test('generates a workflow from an AI prompt', async () => {
    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');

    const promptInput = screen.getByLabelText(/ai workflow prompt/i);
    fireEvent.change(promptInput, { target: { value: 'Send a daily digest' } });
    fireEvent.click(screen.getByRole('button', { name: /generate with ai/i }));

    await waitFor(
      () => {
        expect(screen.getByTestId('workflow-builder')).toBeInTheDocument();
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({ title: 'Workflow Generated' })
        );
      },
      { timeout: 3000 }
    );

    const initialData = JSON.parse(
      screen.getByTestId('builder-initial-data').textContent || 'null'
    );
    expect(initialData.nodes).toHaveLength(3);
    // Trigger label is truncated to 15 chars of the prompt.
    expect(initialData.nodes[0].data.label).toBe('Start: Send a daily di...');
    expect(initialData.nodes[1].data.prompt).toBe('Analyze: Send a daily digest');
    expect(initialData.edges).toHaveLength(2);
  });

  // Test 22: when every initial fetch fails, each fetcher degrades gracefully
  // (per-fetch catch + console.error) and the component still renders
  test('degrades gracefully when every initial fetch fails', async () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    server.use(
      rest.get('/api/workflow-templates/', (req, res, ctx) => res.networkError('down')),
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) => res.networkError('down')),
      rest.get('/api/v1/workflow-ui/executions', (req, res, ctx) => res.networkError('down')),
      rest.get('/api/v1/workflow-ui/services', (req, res, ctx) => res.networkError('down'))
    );

    render(<WorkflowAutomation />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /workflow automation/i })
      ).toBeInTheDocument();
    });
    // Every fetcher hit its own catch (4 console.errors), no crash, no toast.
    expect(errorSpy).toHaveBeenCalled();
    expect(mockToast).not.toHaveBeenCalled();
    errorSpy.mockRestore();
  });

  // Test 23: a failed builder save surfaces an error toast (no id returned)
  test('shows error toast when builder save fails', async () => {
    server.use(
      rest.post('/api/v1/workflows/workflows', (req, res, ctx) =>
        res(ctx.status(500), ctx.json({ detail: 'boom' }))
      )
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');

    fireEvent.click(screen.getByRole('button', { name: /visual builder/i }));
    await screen.findByTestId('workflow-builder');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to save workflow',
          variant: 'error',
        })
      );
    });
  });

  // Test 24: execution without an execution_id in the response → error toast
  test('shows error toast when workflow execution fails', async () => {
    server.use(
      rest.post('/api/v1/workflows/workflows/:workflow_id/execute', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ status: 'error', error: 'nope' }))
      )
    );

    render(<WorkflowAutomation />);
    const useTemplateButton = await screen.findByRole('button', {
      name: /use template/i,
    });
    fireEvent.click(useTemplateButton);

    fireEvent.click(
      await screen.findByRole('button', { name: /execute workflow/i })
    );

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'nope',
          variant: 'error',
        })
      );
    });
  });

  // Test 25: cancel failure surfaces an error toast
  test('shows error toast when execution cancel fails', async () => {
    server.use(
      rest.post('/api/v1/workflow-ui/executions/:id/cancel', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: false, error: 'cannot' }))
      )
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    const cancelButton = await screen.findByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelButton);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to cancel execution',
          variant: 'error',
        })
      );
    });
  });

  // Test 26: full resume flow — add a missing parameter, resume, POST body
  test('resumes a paused execution with added parameters', async () => {
    const resumeBodies: any[] = [];
    server.use(
      rest.post('/api/v1/workflows/workflows/:id/resume', (req, res, ctx) => {
        resumeBodies.push({ id: req.params.id, body: req.body });
        return res(ctx.status(200), ctx.json({ status: 'resumed' }));
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    const resumeButton = await screen.findByRole('button', { name: 'Resume' });
    fireEvent.click(resumeButton);

    const dialog = await screen.findByRole('dialog');
    // Add a new parameter key.
    fireEvent.change(within(dialog).getByPlaceholderText(/new parameter key/i), {
      target: { value: 'token' },
    });
    fireEvent.click(
      within(dialog).getAllByRole('button').find((b) => b.querySelector('.lucide-plus'))!
    );
    // The key row appears with an editable value input.
    const valueInput = await within(dialog).findByPlaceholderText('Value');
    fireEvent.change(valueInput, { target: { value: 'abc' } });

    fireEvent.click(within(dialog).getByRole('button', { name: 'Resume' }));

    await waitFor(() => {
      expect(resumeBodies).toHaveLength(1);
      expect(resumeBodies[0].id).toBe('e3');
      expect(resumeBodies[0].body).toEqual({ token: 'abc' });
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Execution Resumed' })
      );
    });
    // Modal closes on success.
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: /resume execution/i })).not.toBeInTheDocument();
    });
  });

  // Test 27: resume failure surfaces an error toast and keeps the modal open
  test('shows error toast when resume fails', async () => {
    server.use(
      rest.post('/api/v1/workflows/workflows/:id/resume', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ status: 'pending', error: 'stuck' }))
      )
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    const resumeButton = await screen.findByRole('button', { name: 'Resume' });
    fireEvent.click(resumeButton);

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Resume' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to resume execution',
          variant: 'error',
        })
      );
    });
  });

  // Test 28: full time-travel fork flow — edit a variable, fork, POST body
  test('forks an execution with edited variables', async () => {
    const forkBodies: any[] = [];
    server.use(
      rest.post('/api/time-travel/workflows/:id/fork', (req, res, ctx) => {
        forkBodies.push({ id: req.params.id, body: req.body });
        return res(ctx.status(200), ctx.json({ new_execution_id: 'e-forked' }));
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));
    await screen.findByText('running');

    fireEvent.click(getIconButtons()[0]); // open details for e1 (has results)

    const stepTrigger = await screen.findByRole('button', {
      name: /step: step1/i,
    });
    fireEvent.click(stepTrigger);

    fireEvent.click(
      await screen.findByRole('button', { name: /fork & time travel/i })
    );

    // The fork modal opens on top of the execution details modal. Both use the
    // same dialog-content ids (custom Dialog portal), so locate by content.
    const forkDialog = await waitFor(() => {
      const dialogs = screen.getAllByRole('dialog');
      const fork = dialogs.find((d) =>
        within(d).queryByText(/time travel: fork from step step1/i)
      );
      expect(fork).toBeTruthy();
      return fork!;
    });

    // The step's captured variable (foo: "bar") is pre-filled; edit it to 123.
    const paramInput = within(forkDialog).getByLabelText('foo');
    expect(paramInput).toHaveValue('bar');
    fireEvent.change(paramInput, { target: { value: '123' } });

    fireEvent.click(within(forkDialog).getByRole('button', { name: /fork timeline/i }));

    await waitFor(() => {
      expect(forkBodies).toHaveLength(1);
      expect(forkBodies[0].id).toBe('e1');
      expect(forkBodies[0].body).toEqual({ step_id: 'step1', new_variables: { foo: 123 } });
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Timeline Forked! 🌌' })
      );
    });
    // Both modals close on success.
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  // Test 29: template modal renders every input field type (email/date/array/
  // string) and executes with the collected form data
  test('renders template input fields and executes with form data', async () => {
    const executeBodies: any[] = [];
    server.use(
      rest.get('/api/workflow-templates/', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([
            {
              template_id: 't-schema',
              name: 'Schema Template',
              description: 'Has input fields',
              category: 'email',
              icon: 'mail',
              steps: [
                { id: 's1', type: 'action', service: 'email', action: 'send', parameters: {}, name: 'Send' },
              ],
              input_schema: {
                type: 'object',
                properties: {
                  recipient: { type: 'string', format: 'email', title: 'Recipient Email', description: 'Who to send to' },
                  sendDate: { type: 'string', format: 'date', title: 'Send Date' },
                  tags: { type: 'array', title: 'Tags' },
                  subject: { type: 'string', title: 'Subject' },
                  priority: { type: 'number', title: 'Priority' },
                },
                required: ['recipient'],
              },
            },
          ])
        );
      }),
      rest.post('/api/v1/workflows/workflows/:workflow_id/execute', (req, res, ctx) => {
        executeBodies.push({ workflow_id: req.params.workflow_id, body: req.body });
        return res(
          ctx.status(200),
          ctx.json({ execution_id: 'e-schema', status: 'running' })
        );
      })
    );

    render(<WorkflowAutomation />);

    fireEvent.click(
      await screen.findByRole('button', { name: /use template/i })
    );
    const dialog = await screen.findByRole('dialog');

    // Required email field carries the asterisk.
    expect(within(dialog).getByText(/recipient email \*/i)).toBeInTheDocument();
    const emailInput = within(dialog).getByLabelText(/recipient email/i);
    expect(emailInput).toHaveAttribute('type', 'email');
    fireEvent.change(emailInput, { target: { value: 'a@b.com' } });

    const dateInput = within(dialog).getByLabelText(/send date/i);
    expect(dateInput).toHaveAttribute('type', 'date');
    fireEvent.change(dateInput, { target: { value: '2026-05-01' } });

    const tagsTextarea = within(dialog).getByLabelText('Tags');
    expect(tagsTextarea.tagName).toBe('TEXTAREA');
    fireEvent.change(tagsTextarea, { target: { value: 'x, y' } });

    fireEvent.change(within(dialog).getByLabelText('Subject'), {
      target: { value: 'Hello' },
    });

    // Non-string/array fields fall through to the default text input.
    const priorityInput = within(dialog).getByLabelText('Priority');
    expect(priorityInput).toHaveAttribute('type', 'text');
    fireEvent.change(priorityInput, { target: { value: '3' } });

    fireEvent.click(within(dialog).getByRole('button', { name: /execute workflow/i }));

    await waitFor(() => {
      expect(executeBodies).toHaveLength(1);
      expect(executeBodies[0].workflow_id).toBe('t-schema');
      expect(executeBodies[0].body).toEqual({
        recipient: 'a@b.com',
        sendDate: '2026-05-01',
        tags: ['x', 'y'],
        subject: 'Hello',
        priority: '3',
      });
    });
  });

  // Test 30: workflow Run modal renders input fields and executes with them
  test('renders workflow input fields and executes with form data', async () => {
    const executeBodies: any[] = [];
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([
            {
              id: 'w-schema',
              name: 'Schema Workflow',
              description: 'Has inputs',
              steps: [
                { id: 'ws1', type: 'action', service: 'email', action: 'send', parameters: {}, name: 'Send' },
              ],
              input_schema: {
                type: 'object',
                properties: {
                  subject: { type: 'string', title: 'Subject' },
                  priority: { type: 'string', title: 'Priority' },
                },
                required: [],
              },
              created_at: '2024-01-01T00:00:00Z',
              updated_at: '2024-01-01T00:00:00Z',
              steps_count: 1,
            },
          ])
        );
      }),
      rest.post('/api/v1/workflows/workflows/:workflow_id/execute', (req, res, ctx) => {
        executeBodies.push({ workflow_id: req.params.workflow_id, body: req.body });
        return res(
          ctx.status(200),
          ctx.json({ execution_id: 'e-w-schema', status: 'running' })
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));

    fireEvent.click(await screen.findByRole('button', { name: 'Run' }));
    const dialog = await screen.findByRole('dialog');
    expect(
      within(dialog).getByRole('heading', { name: /execute workflow: schema workflow/i })
    ).toBeInTheDocument();

    fireEvent.change(within(dialog).getByLabelText('Subject'), {
      target: { value: 'Quarterly' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /execute workflow/i }));

    await waitFor(() => {
      expect(executeBodies).toHaveLength(1);
      expect(executeBodies[0].workflow_id).toBe('w-schema');
      expect(executeBodies[0].body).toEqual({ subject: 'Quarterly' });
    });
  });

  // Test 31: failed/cancelled/pending execution statuses render their badges
  test('renders failed, cancelled and pending executions', async () => {
    server.use(
      rest.get('/api/v1/workflow-ui/executions', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            executions: [
              { execution_id: 'f1', workflow_id: 'w1', status: 'failed', start_time: '2024-01-01T00:00:00Z', current_step: 2, total_steps: 3 },
              { execution_id: 'c1', workflow_id: 'w1', status: 'cancelled', start_time: '2024-01-01T00:00:00Z', current_step: 1, total_steps: 3 },
              { execution_id: 'p1', workflow_id: 'w1', status: 'pending', start_time: '2024-01-01T00:00:00Z', current_step: 0, total_steps: 3 },
              { execution_id: 's1', workflow_id: 'w1', status: 'scheduled', start_time: '2024-01-01T00:00:00Z', current_step: 0, total_steps: 3 },
            ],
          })
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    await waitFor(() => {
      expect(screen.getByText('failed')).toBeInTheDocument();
      expect(screen.getByText('cancelled')).toBeInTheDocument();
      expect(screen.getByText('pending')).toBeInTheDocument();
      // Unknown status falls back to the gray badge.
      expect(screen.getByText('scheduled')).toBeInTheDocument();
    });
  });

  // Test 32: execution details modal surfaces step errors
  test('shows execution errors in the details modal', async () => {
    server.use(
      rest.get('/api/v1/workflow-ui/executions', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            executions: [
              {
                execution_id: 'err1',
                workflow_id: 'w1',
                status: 'failed',
                start_time: '2024-01-01T00:00:00Z',
                current_step: 2,
                total_steps: 2,
                errors: ['Step 2 crashed', 'Retries exhausted'],
                has_errors: true,
              },
            ],
          })
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    await screen.findByText('failed');
    fireEvent.click(getIconButtons()[0]);

    await waitFor(() => {
      expect(screen.getByText('Errors')).toBeInTheDocument();
      expect(screen.getByText('Step 2 crashed')).toBeInTheDocument();
      expect(screen.getByText('Retries exhausted')).toBeInTheDocument();
    });
  });

  // Test 33: active execution details sync with the polling refresh
  test('syncs open execution details with refreshed data', async () => {
    const baseExec = {
      execution_id: 'e1',
      workflow_id: 'w1',
      status: 'running' as const,
      start_time: '2024-01-01T00:00:00Z',
      current_step: 1,
      total_steps: 2,
    };
    let execs: any[] = [baseExec];

    server.use(
      rest.get('/api/v1/workflow-ui/executions', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, executions: execs }));
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    await screen.findByText('running');
    fireEvent.click(getIconButtons()[0]);
    expect(await screen.findByText(/step 1 of 2/i)).toBeInTheDocument();

    // Simulate the backend advancing the execution; polling (2s) must pick it
    // up and the open details modal must re-sync.
    act(() => {
      execs = [{ ...baseExec, current_step: 2 }];
    });

    await waitFor(
      () => {
        expect(screen.getByText(/step 2 of 2/i)).toBeInTheDocument();
      },
      { timeout: 7000 }
    );
  });

  // Test 34: services with more than 5 actions show "+N more"
  test('shows +N more for services with many actions', async () => {
    server.use(
      rest.get('/api/v1/workflow-ui/services', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            services: {
              email: {
                name: 'email',
                actions: ['send', 'draft', 'archive', 'reply', 'forward', 'schedule'],
                description: 'Email service',
              },
            },
          })
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Services' }));

    await waitFor(() => {
      expect(screen.getByText('+1 more')).toBeInTheDocument();
    });
    expect(screen.getByText('6 actions')).toBeInTheDocument();
  });

  // Test 35: service icons cover the remaining category branches
  test('renders icons for every service category', async () => {
    const categories = ['calendar', 'tasks', 'messages', 'email', 'documents', 'asana', 'dropbox', 'mystery'];
    server.use(
      rest.get('/api/workflow-templates/', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json(
            categories.map((category, i) => ({
              template_id: `t${i}`,
              name: `Template ${category}`,
              description: 'd',
              category,
              icon: 'x',
              steps: [] as any[],
              input_schema: { type: 'object', properties: {}, required: [] as any[] },
            }))
          )
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Template calendar');

    expect(document.querySelector('svg.text-blue-500')).toBeInTheDocument();   // calendar
    expect(document.querySelector('svg.text-green-500')).toBeInTheDocument();  // tasks
    expect(document.querySelector('svg.text-purple-500')).toBeInTheDocument(); // messages
    expect(document.querySelector('svg.text-red-500')).toBeInTheDocument();    // email
    expect(document.querySelector('svg.text-orange-500')).toBeInTheDocument(); // documents
    expect(document.querySelector('svg.text-teal-500')).toBeInTheDocument();   // asana/trello/notion
    expect(document.querySelector('svg.text-gray-500')).toBeInTheDocument();   // default
  });

  // Test 36: "Edit in Builder" on a template navigates to its editor
  test('Edit in Builder navigates to the template editor', async () => {
    render(<WorkflowAutomation />);
    const editButton = await screen.findByRole('button', {
      name: /edit in builder/i,
    });
    fireEvent.click(editButton);

    expect(mockRouter.push).toHaveBeenCalledWith('/workflows/editor/t1');
  });

  // Test 37: workflow edit button navigates to the workflow editor
  test('workflow edit button navigates to the editor', async () => {
    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    await screen.findByText('Onboarding Flow');

    fireEvent.click(screen.getByRole('button', { name: 'Edit workflow' }));
    expect(mockRouter.push).toHaveBeenCalledWith('/workflows/editor/w1');
  });

  // Test 38: step-based workflows linearize into builder nodes and edges
  test('step-based workflows map into builder nodes and edges', async () => {
    server.use(
      rest.get('/api/v1/workflows/workflows', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json([
            {
              id: 'step-wf',
              name: 'Step Workflow',
              description: 'Step based',
              steps: [
                { id: 'st1', type: 'trigger', service: 'schedule', action: 'daily', parameters: {}, name: 'Daily Trigger' },
                { id: 'st2', type: 'action', service: 'email', action: 'send', parameters: {}, name: 'Send Email' },
              ],
              input_schema: {},
              created_at: '2024-01-01T00:00:00Z',
              updated_at: '2024-01-01T00:00:00Z',
              steps_count: 2,
            },
          ])
        );
      })
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));

    fireEvent.click(await screen.findByRole('button', { name: 'Run' }));
    await screen.findByRole('heading', { name: /execute workflow: step workflow/i });
    fireEvent.click(screen.getByRole('button', { name: /visual builder/i }));

    await waitFor(() => {
      const initialData = JSON.parse(
        screen.getByTestId('builder-initial-data').textContent || 'null'
      );
      expect(initialData.nodes).toHaveLength(2);
      expect(initialData.nodes[0].data.label).toBe('Daily Trigger');
      expect(initialData.edges).toEqual([
        { id: 'est1-st2', source: 'st1', target: 'st2', type: 'addStepEdge' },
      ]);
    });
  });

  // Test 39: a single failed fetch degrades gracefully (no crash, no toast)
  test('degrades gracefully when templates fetch fails', async () => {
    server.use(
      rest.get('/api/workflow-templates/', (req, res, ctx) =>
        res(ctx.status(500), ctx.json({ detail: 'boom' }))
      )
    );

    render(<WorkflowAutomation />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /workflow automation/i })
      ).toBeInTheDocument();
    });
    // Templates tab shows an empty grid; no crash.
    expect(screen.queryByText('Email Digest')).not.toBeInTheDocument();
    expect(mockToast).not.toHaveBeenCalled();
  });

  // Test 40: an unparseable draft query logs an error and stays in classic view
  test('handles malformed draft query without crashing', async () => {
    const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockRouter.query.draft = '{not-json';

    render(<WorkflowAutomation />);

    await screen.findByText('Email Digest');
    expect(screen.queryByTestId('workflow-builder')).not.toBeInTheDocument();
    expect(errorSpy).toHaveBeenCalledWith('Failed to parse draft', expect.anything());
    errorSpy.mockRestore();
  });

  // Test 41: fork failure surfaces the time-travel error toast
  test('shows error toast when forking fails', async () => {
    server.use(
      rest.post('/api/time-travel/workflows/:id/fork', (req, res, ctx) =>
        res(ctx.status(500), ctx.json({ detail: 'boom' }))
      )
    );

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));
    await screen.findByText('running');

    fireEvent.click(getIconButtons()[0]); // open details for e1
    fireEvent.click(await screen.findByRole('button', { name: /step: step1/i }));
    fireEvent.click(
      await screen.findByRole('button', { name: /fork & time travel/i })
    );

    const dialogs = screen.getAllByRole('dialog');
    const forkDialog = dialogs.find((d) =>
      within(d).queryByText(/time travel: fork from step step1/i)
    )!;
    fireEvent.click(within(forkDialog).getByRole('button', { name: /fork timeline/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Time-Travel Failed',
          description: 'Could not fork timeline.',
          variant: 'error',
        })
      );
    });
  });

  // Test 42: every modal's cancel/close button closes it
  test('cancel buttons close their modals', async () => {
    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');

    // Template modal: Cancel.
    fireEvent.click(await screen.findByRole('button', { name: /use template/i }));
    let dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // Workflow Run modal: Cancel.
    fireEvent.click(screen.getByRole('button', { name: 'My Workflows' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Run' }));
    dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // Resume modal: Cancel.
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Resume' }));
    dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // Execution details: Close.
    fireEvent.click(getIconButtons()[0]);
    dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Close' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // Fork modal: Cancel.
    fireEvent.click(getIconButtons()[0]);
    fireEvent.click(await screen.findByRole('button', { name: /step: step1/i }));
    fireEvent.click(
      await screen.findByRole('button', { name: /fork & time travel/i })
    );
    const dialogs = screen.getAllByRole('dialog');
    const forkDialog = dialogs.find((d) =>
      within(d).queryByText(/time travel: fork from step step1/i)
    )!;
    fireEvent.click(within(forkDialog).getByRole('button', { name: 'Cancel' }));
    // Only the fork modal closes; the details modal underneath stays open.
    await waitFor(() => {
      expect(
        screen.queryByText(/time travel: fork from step step1/i)
      ).not.toBeInTheDocument();
    });
  });

  // Test 43: resume modal can remove an added parameter row
  test('resume modal removes added parameters', async () => {
    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));

    fireEvent.click(await screen.findByRole('button', { name: 'Resume' }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(within(dialog).getByPlaceholderText(/new parameter key/i), {
      target: { value: 'token' },
    });
    fireEvent.click(
      within(dialog).getAllByRole('button').find((b) => b.querySelector('.lucide-plus'))!
    );
    expect(await within(dialog).findByPlaceholderText('Value')).toBeInTheDocument();

    // Remove the row via its trash icon.
    fireEvent.click(
      within(dialog).getAllByRole('button').find((b) => b.querySelector('.lucide-trash-2'))!
    );
    await waitFor(() => {
      expect(within(dialog).queryByPlaceholderText('Value')).not.toBeInTheDocument();
    });
  });

  // Export: the parent modal owns its own fetch/blob/download handler. It must
  // use the same execution, never re-execute, and surface typed refusals.
  test('downloads completed execution results from the parent modal', async () => {
    let executeCalls = 0;
    server.use(
      rest.post('/api/v1/workflows/workflows/:workflow_id/execute', (req, res, ctx) => {
        executeCalls += 1;
        return res(ctx.status(200), ctx.json({ execution_id: 'unexpected' }));
      }),
      rest.get(
        '/api/v1/workflows/workflows/executions/e2/export',
        (req, res, ctx) =>
          res(
            ctx.status(200),
            ctx.set('Content-Type', 'application/json'),
            ctx.set(
              'Content-Disposition',
              'attachment; filename="workflow-w1-execution-e2.json"',
            ),
            ctx.body('{"schema":"atom.workflow.execution-result.v1"}'),
          ),
      ),
    );
    const createObjectURL = jest.fn(() => 'blob:parent-export');
    const revokeObjectURL = jest.fn();
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: createObjectURL,
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectURL,
    });
    let downloadedName = '';
    const clickSpy = jest
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        downloadedName = this.download;
      });

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));
    await screen.findByText('completed');
    fireEvent.click(getIconButtons()[1]); // e2, completed

    const button = await screen.findByRole('button', { name: /download results/i });
    expect(button).not.toBeDisabled();
    fireEvent.click(button);

    await waitFor(() => {
      expect(createObjectURL).toHaveBeenCalledTimes(1);
    });
    expect(downloadedName).toBe('workflow-w1-execution-e2.json');
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:parent-export');
    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(executeCalls).toBe(0);
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Results downloaded' }),
    );
    clickSpy.mockRestore();
  });

  test.each([
    [409, 'execution_not_completed', 'the execution is not complete'],
    [503, 'workflow_store_unreadable', 'the export store is unavailable'],
  ])('surfaces a typed %s refusal in the parent modal', async (status, code, message) => {
    server.use(
      rest.get(
        '/api/v1/workflows/workflows/executions/e2/export',
        (req, res, ctx) =>
          res(ctx.status(status), ctx.json({ detail: { error: code, message } })),
      ),
    );
    const createObjectURL = jest.fn();
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: createObjectURL,
    });

    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));
    await screen.findByText('completed');
    fireEvent.click(getIconButtons()[1]);

    fireEvent.click(
      await screen.findByRole('button', { name: /download results/i }),
    );
    await waitFor(() => {
      expect(screen.getByText(message)).toBeInTheDocument();
    });
    expect(screen.getByText('Download unavailable')).toBeInTheDocument();
    expect(createObjectURL).not.toHaveBeenCalled();
  });

  test('disables parent-modal download for a running execution', async () => {
    render(<WorkflowAutomation />);
    await screen.findByText('Email Digest');
    fireEvent.click(screen.getByRole('button', { name: 'Executions' }));
    await screen.findByText('running');
    fireEvent.click(getIconButtons()[0]); // e1, running

    const button = await screen.findByRole('button', { name: /download results/i });
    expect(button).toBeDisabled();
  });
});
