/**
 * HubSpotWorkflowAutomation Component Tests
 *
 * Tests verify the real HubSpotWorkflowAutomation component
 * (components/integrations/hubspot/HubSpotWorkflowAutomation.tsx) — a pure
 * props-driven workflow management UI. It makes no network calls (no MSW
 * handlers needed); workflows and the onWorkflow* callbacks are props.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import HubSpotWorkflowAutomation from '@/components/integrations/hubspot/HubSpotWorkflowAutomation';

const mockWorkflows = [
  {
    id: 'w1',
    name: 'Lead Nurturing',
    description: 'Nurture new leads with follow-up emails',
    triggers: [
      {
        id: 't1',
        name: 'Lead Score Trigger',
        type: 'lead_score' as const,
        condition: 'greater_than',
        value: 50,
        enabled: true,
      },
    ],
    actions: [{ id: 'a1', type: 'email' as const, config: {} }],
    enabled: true,
    runs: 12,
    successRate: 92,
  },
];

describe('HubSpotWorkflowAutomation', () => {
  // Test 1: renders component
  test('renders component', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    expect(
      screen.getByRole('heading', { name: /workflow automation/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /create workflow/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows empty state when no workflows exist
  test('shows empty state when no workflows', () => {
    render(<HubSpotWorkflowAutomation workflows={[]} />);

    expect(
      screen.getByText(/no workflows created yet/i)
    ).toBeInTheDocument();
  });

  // Test 3: displays workflows with status badge and description
  test('displays workflows with status and description', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    expect(screen.getByText('Lead Nurturing')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(
      screen.getByText('Nurture new leads with follow-up emails')
    ).toBeInTheDocument();
  });

  // Test 4: displays workflow stats
  test('displays workflow stats', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    expect(screen.getByText('Triggers')).toBeInTheDocument();
    expect(screen.getByText('Runs')).toBeInTheDocument();
    expect(screen.getByText('Success Rate')).toBeInTheDocument();
    expect(screen.getByText('92%')).toBeInTheDocument();
  });

  // Test 5: create workflow button opens the creation form
  test('create workflow button opens the creation form', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[0]);

    expect(screen.getByText('Create New Workflow')).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/hot lead follow-up/i)
    ).toBeInTheDocument();
    expect(screen.getByText('Actions')).toBeInTheDocument();
  });

  // Test 6: creating a workflow calls onWorkflowCreate
  test('creating a workflow calls onWorkflowCreate', () => {
    const onWorkflowCreate = jest.fn();
    render(
      <HubSpotWorkflowAutomation workflows={mockWorkflows} onWorkflowCreate={onWorkflowCreate} />
    );

    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[0]);

    const nameInput = screen.getByPlaceholderText(/hot lead follow-up/i);
    fireEvent.change(nameInput, { target: { value: 'Hot Lead Follow-up' } });

    // Form submit button is the second "Create Workflow" button (header first)
    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[1]);

    expect(onWorkflowCreate).toHaveBeenCalledTimes(1);
    expect(onWorkflowCreate).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Hot Lead Follow-up' })
    );
  });

  // Test 7: displays workflow analytics tab
  test('displays workflow analytics tab', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    fireEvent.click(screen.getByRole('button', { name: 'Workflow Analytics' }));

    expect(screen.getByText('Total Workflows')).toBeInTheDocument();
    expect(screen.getByText('Total Executions')).toBeInTheDocument();
  });

  // Test 8: displays templates tab
  test('displays templates tab', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    fireEvent.click(screen.getByRole('button', { name: 'Templates' }));

    expect(screen.getByText('Workflow Templates')).toBeInTheDocument();
    expect(screen.getByText('Welcome Sequence')).toBeInTheDocument();
    expect(screen.getByText('Re-engagement')).toBeInTheDocument();
  });

  // Test 9: pause button calls onWorkflowToggle
  test('pause button calls onWorkflowToggle', () => {
    const onWorkflowToggle = jest.fn();
    render(
      <HubSpotWorkflowAutomation workflows={mockWorkflows} onWorkflowToggle={onWorkflowToggle} />
    );

    fireEvent.click(screen.getByRole('button', { name: /pause/i }));

    expect(onWorkflowToggle).toHaveBeenCalledWith('w1', false);
  });

  // Test 10: delete button calls onWorkflowDelete
  test('delete button calls onWorkflowDelete', () => {
    const onWorkflowDelete = jest.fn();
    render(
      <HubSpotWorkflowAutomation workflows={mockWorkflows} onWorkflowDelete={onWorkflowDelete} />
    );

    fireEvent.click(screen.getByRole('button', { name: /delete/i }));

    expect(onWorkflowDelete).toHaveBeenCalledWith('w1');
  });

  // Test 11: create button stays disabled until a name is entered
  test('create button stays disabled until a name is entered', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[0]);

    const submitButton = screen.getAllByRole('button', { name: /create workflow/i })[1];
    expect(submitButton).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText(/hot lead follow-up/i), {
      target: { value: 'Hot Lead Follow-up' },
    });

    expect(submitButton).toBeEnabled();
  });

  // Test 12: name and description inputs feed onWorkflowCreate payload
  test('name and description inputs feed the created workflow payload', () => {
    const onWorkflowCreate = jest.fn();
    render(
      <HubSpotWorkflowAutomation workflows={mockWorkflows} onWorkflowCreate={onWorkflowCreate} />
    );

    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[0]);

    fireEvent.change(screen.getByPlaceholderText(/hot lead follow-up/i), {
      target: { value: 'Hot Lead Follow-up' },
    });
    fireEvent.change(screen.getByPlaceholderText(/describe what this workflow does/i), {
      target: { value: 'Follow up on hot leads' },
    });
    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[1]);

    expect(onWorkflowCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Hot Lead Follow-up',
        description: 'Follow up on hot leads',
      })
    );
  });

  // Test 13: adding a trigger renders a trigger card
  test('adding a trigger renders a trigger card', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[0]);

    const triggerSelect = screen.getAllByRole('combobox')[0];
    fireEvent.change(triggerSelect, { target: { value: 'lead_score' } });

    expect(screen.getByText('Lead Score Trigger')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Value')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Equals')).toBeInTheDocument();
    expect(screen.getByRole('checkbox')).toBeChecked();
  });

  // Test 14: adding an action renders an action card
  test('adding an action renders an action card', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[0]);

    const actionSelect = screen.getAllByRole('combobox')[1];
    fireEvent.change(actionSelect, { target: { value: 'email' } });

    expect(screen.getAllByText('Send Email')).toHaveLength(2);
    expect(screen.getByPlaceholderText('Delay (min)')).toBeInTheDocument();
  });

  // Test 15: created workflow includes added triggers and actions
  test('created workflow includes added triggers and actions', () => {
    const onWorkflowCreate = jest.fn();
    render(
      <HubSpotWorkflowAutomation workflows={mockWorkflows} onWorkflowCreate={onWorkflowCreate} />
    );

    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[0]);

    const [triggerSelect, actionSelect] = screen.getAllByRole('combobox');
    fireEvent.change(triggerSelect, { target: { value: 'behavior' } });
    fireEvent.change(actionSelect, { target: { value: 'task' } });

    fireEvent.change(screen.getByPlaceholderText(/hot lead follow-up/i), {
      target: { value: 'Lead Nurturing v2' },
    });
    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[1]);

    expect(onWorkflowCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Lead Nurturing v2',
        triggers: [expect.objectContaining({ type: 'behavior', name: 'Behavior Trigger' })],
        actions: [expect.objectContaining({ type: 'task' })],
      })
    );
  });

  // Test 16: cancel closes the creation form
  test('cancel closes the creation form', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[0]);
    expect(screen.getByText('Create New Workflow')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^cancel$/i }));

    expect(screen.queryByText('Create New Workflow')).not.toBeInTheDocument();
  });

  // Test 17: empty state Create Workflow button opens the form
  test('empty state create button opens the form', () => {
    render(<HubSpotWorkflowAutomation workflows={[]} />);

    fireEvent.click(screen.getAllByRole('button', { name: /create workflow/i })[1]);

    expect(screen.getByText('Create New Workflow')).toBeInTheDocument();
  });

  // Test 18: paused workflow shows Paused badge and Resume action
  test('paused workflow shows Paused badge and resumes via onWorkflowToggle', () => {
    const onWorkflowToggle = jest.fn();
    const pausedWorkflows = [
      { ...mockWorkflows[0], id: 'w2', enabled: false },
    ];
    render(
      <HubSpotWorkflowAutomation workflows={pausedWorkflows} onWorkflowToggle={onWorkflowToggle} />
    );

    expect(screen.getByText('Paused')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /resume/i }));

    expect(onWorkflowToggle).toHaveBeenCalledWith('w2', true);
  });

  // Test 19: success rate renders across color-scheme thresholds
  test('success rate renders for all color-scheme thresholds', () => {
    const variedWorkflows = [
      { ...mockWorkflows[0], id: 'w1', successRate: 92 },
      { ...mockWorkflows[0], id: 'w2', successRate: 80 },
      { ...mockWorkflows[0], id: 'w3', successRate: 60 },
      { ...mockWorkflows[0], id: 'w4', successRate: 30 },
    ];
    render(<HubSpotWorkflowAutomation workflows={variedWorkflows} />);

    expect(screen.getByText('92%')).toBeInTheDocument();
    expect(screen.getByText('80%')).toBeInTheDocument();
    expect(screen.getByText('60%')).toBeInTheDocument();
    expect(screen.getByText('30%')).toBeInTheDocument();
  });

  // Test 20: analytics tab shows aggregate workflow counts
  test('analytics tab shows aggregate counts', () => {
    const analyticWorkflows = [
      { ...mockWorkflows[0], id: 'w1', runs: 12, enabled: true },
      { ...mockWorkflows[0], id: 'w2', runs: 5, enabled: false },
    ];
    render(<HubSpotWorkflowAutomation workflows={analyticWorkflows} />);

    fireEvent.click(screen.getByRole('button', { name: 'Workflow Analytics' }));

    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('17')).toBeInTheDocument();
  });

  // Test 21: templates tab lists the four pre-built templates
  test('templates tab lists four use-template actions', () => {
    render(<HubSpotWorkflowAutomation workflows={mockWorkflows} />);

    fireEvent.click(screen.getByRole('button', { name: 'Templates' }));

    expect(screen.getByText('Welcome Sequence')).toBeInTheDocument();
    expect(screen.getByText('Lead Nurturing')).toBeInTheDocument();
    expect(screen.getByText('Re-engagement')).toBeInTheDocument();
    expect(screen.getByText('Task Automation')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /use template/i })).toHaveLength(4);
  });

  // Test 22: last run timestamp renders when present
  test('last run timestamp renders when present', () => {
    const withLastRun = [
      { ...mockWorkflows[0], lastRun: '2024-05-01T12:00:00Z' },
    ];
    render(<HubSpotWorkflowAutomation workflows={withLastRun} />);

    const lastRun = screen.getByText(/last run:/i);
    expect(lastRun.textContent).toMatch(/2024/);
  });
});
