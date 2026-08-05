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
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import WorkflowAutomation from '@/components/WorkflowAutomation';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

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
      edges: [],
    };
    return (
      <div data-testid="workflow-builder">
        <div>Workflow Builder</div>
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
});
