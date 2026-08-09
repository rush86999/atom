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
    return (
      <div data-testid="workflow-builder">
        <div>Workflow Builder</div>
        <div data-testid="builder-initial-data">
          {JSON.stringify(props.initialData)}
        </div>
        <button onClick={() => props.onSave(sampleData)}>Save</button>
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
          description: 'Failed to execute workflow',
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

    fireEvent.click(getIconButtons()[0]); // ghost edit icon on the card
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
});
