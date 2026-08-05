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
});
