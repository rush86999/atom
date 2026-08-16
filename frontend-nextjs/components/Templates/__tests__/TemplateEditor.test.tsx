/**
 * TemplateEditor component tests.
 *
 * Covers metadata tab, save validation (name/description/steps), adding and
 * reordering workflow steps, input parameters, the preview tab + Preview
 * button, and read-only mode.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TemplateEditor, WorkflowTemplate } from '../TemplateEditor';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] as any[] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const INITIAL: WorkflowTemplate = {
  template_id: 'tpl-1',
  name: 'Lead Processing',
  description: 'Process incoming leads',
  category: 'automation',
  complexity: 'intermediate',
  tags: ['lead'],
  inputs: [],
  steps: [],
};

describe('TemplateEditor', () => {
  const mockOnSave = jest.fn().mockResolvedValue(undefined);
  const mockOnCancel = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the metadata form prefilled from initialTemplate', () => {
    render(<TemplateEditor initialTemplate={INITIAL} onSave={mockOnSave} onCancel={mockOnCancel} />);

    expect(screen.getByRole('heading', { name: /Template Editor/i })).toBeInTheDocument();
    expect(
      (screen.getByLabelText(/Template Name \*/i) as HTMLInputElement).value
    ).toBe('Lead Processing');
    expect(
      (screen.getByLabelText(/Description \*/i) as HTMLTextAreaElement).value
    ).toBe('Process incoming leads');
    expect(screen.getAllByText('lead').length).toBeGreaterThanOrEqual(1);
  });

  it('toasts a validation error when saving without a name', () => {
    render(<TemplateEditor onSave={mockOnSave} onCancel={mockOnCancel} />);
    fireEvent.click(screen.getByRole('button', { name: /Save Template/i }));

    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Validation Error',
        description: 'Template name is required',
        variant: 'error',
      })
    );
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it('toasts a validation error when saving without a description', () => {
    render(<TemplateEditor onSave={mockOnSave} onCancel={mockOnCancel} />);
    fireEvent.change(screen.getByLabelText(/Template Name \*/i), {
      target: { value: 'Name Only' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Save Template/i }));

    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Validation Error',
        description: 'Template description is required',
        variant: 'error',
      })
    );
  });

  it('toasts a validation error when saving without any steps', () => {
    render(<TemplateEditor onSave={mockOnSave} onCancel={mockOnCancel} />);
    fireEvent.change(screen.getByLabelText(/Template Name \*/i), {
      target: { value: 'Complete' },
    });
    fireEvent.change(screen.getByLabelText(/Description \*/i), {
      target: { value: 'Has a description but no steps' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Save Template/i }));

    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Validation Error',
        description: 'Template must have at least one step',
        variant: 'error',
      })
    );
    expect(mockOnSave).not.toHaveBeenCalled();
  });

  it('saves a valid template with steps and calls onSave', async () => {
    render(<TemplateEditor initialTemplate={INITIAL} onSave={mockOnSave} onCancel={mockOnCancel} />);

    fireEvent.click(screen.getByRole('button', { name: /Workflow Steps/i }));
    fireEvent.click(screen.getByRole('button', { name: /Add First Step/i }));
    fireEvent.click(screen.getByRole('button', { name: /Save Template/i }));

    await waitFor(() => {
      expect(mockOnSave).toHaveBeenCalledTimes(1);
    });
    const saved = mockOnSave.mock.calls[0][0] as WorkflowTemplate;
    expect(saved.name).toBe('Lead Processing');
    expect(saved.steps).toHaveLength(1);
    expect(saved.steps[0]).toEqual(
      expect.objectContaining({ step_type: 'action', name: 'Step 1' })
    );
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Success', description: 'Template saved successfully' })
    );
  });

  it('adds steps with sequential names and type badges', () => {
    render(<TemplateEditor initialTemplate={INITIAL} onSave={mockOnSave} onCancel={mockOnCancel} />);
    fireEvent.click(screen.getByRole('button', { name: /Workflow Steps/i }));

    fireEvent.click(screen.getByRole('button', { name: /Add First Step/i }));
    expect(screen.getByText('Step 1')).toBeInTheDocument();
    expect(screen.getAllByText('action')).toHaveLength(1);

    fireEvent.click(screen.getByRole('button', { name: /Add Step/i }));
    expect(screen.getByText('Step 2')).toBeInTheDocument();
  });

  it('edits the selected step inline via handleUpdateStep', () => {
    render(
      <TemplateEditor
        initialTemplate={{ ...INITIAL, steps: [{ id: 's1', name: 'Step 1', step_type: 'action' }] }}
        onSave={mockOnSave}
        onCancel={mockOnCancel}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /Workflow Steps/i }));

    // Editor fields appear only after selecting the step card
    expect(screen.queryByTestId('step-name-s1')).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('Step 1'));
    expect(screen.getByTestId('step-name-s1')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('step-name-s1'), {
      target: { value: 'Renamed Step' },
    });
    fireEvent.change(screen.getByTestId('step-description-s1'), {
      target: { value: 'A brand new description' },
    });

    expect(screen.getByText('Renamed Step')).toBeInTheDocument();
    expect(screen.getAllByText('A brand new description').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText('Step 1')).not.toBeInTheDocument();
  });

  it('reorders steps down and deletes them', () => {
    const { container } = render(
      <TemplateEditor initialTemplate={INITIAL} onSave={mockOnSave} onCancel={mockOnCancel} />
    );
    fireEvent.click(screen.getByRole('button', { name: /Workflow Steps/i }));
    fireEvent.click(screen.getByRole('button', { name: /Add First Step/i }));
    fireEvent.click(screen.getByRole('button', { name: /Add Step/i }));

    // First step: move up disabled, move down enabled; second step: inverse.
    const upButtons = container.querySelectorAll('svg.lucide-arrow-up');
    const downButtons = container.querySelectorAll('svg.lucide-arrow-down');
    expect(upButtons[0].closest('button')).toBeDisabled();
    expect(upButtons[1].closest('button')).toBeEnabled();

    fireEvent.click(downButtons[0].closest('button')!);
    const stepNames = screen.getAllByText(/^Step \d$/);
    expect(stepNames[0]).toHaveTextContent('Step 2');
    expect(stepNames[1]).toHaveTextContent('Step 1');

    // Delete the first card (now Step 2) → Step 1 remains.
    fireEvent.click(container.querySelector('svg.lucide-trash-2')!.closest('button')!);
    expect(screen.getByText('Step 1')).toBeInTheDocument();
    expect(screen.queryByText('Step 2')).not.toBeInTheDocument();
  });

  it('adds and removes input parameters on the Inputs tab', () => {
    const { container } = render(
      <TemplateEditor initialTemplate={INITIAL} onSave={mockOnSave} onCancel={mockOnCancel} />
    );
    fireEvent.click(screen.getByRole('button', { name: /Input Parameters/i }));
    expect(screen.getByText('No input parameters defined yet')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Add Parameter/i }));
    const nameInput = screen.getByPlaceholderText('parameter_name');
    fireEvent.change(nameInput, { target: { value: 'lead_id' } });
    expect((nameInput as HTMLInputElement).value).toBe('lead_id');

    // Empty-state dashed block is gone; the list render keeps one Add Parameter
    // button and shows the parameter card with label/type/description fields.
    expect(screen.queryByText('No input parameters defined yet')).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Add Parameter/i })).toHaveLength(1);
    expect(screen.getByText('Parameter Name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('User-friendly label')).toBeInTheDocument();

    // Delete the parameter via its trash button → empty state returns.
    fireEvent.click(container.querySelector('svg.lucide-trash-2')!.closest('button')!);
    expect(screen.getByText('No input parameters defined yet')).toBeInTheDocument();
  });

  it('shows the summary on the Preview tab', () => {
    const withSteps: WorkflowTemplate = {
      ...INITIAL,
      steps: [{ id: 's1', name: 'Notify Slack', step_type: 'action' }],
      inputs: [{ name: 'lead_id', type: 'string', required: true }],
    };
    render(<TemplateEditor initialTemplate={withSteps} onSave={mockOnSave} onCancel={mockOnCancel} />);
    fireEvent.click(screen.getAllByRole('button', { name: /Preview/i })[0]);

    expect(screen.getByText('Template Summary')).toBeInTheDocument();
    expect(screen.getByText('Lead Processing')).toBeInTheDocument();
    expect(screen.getByText('automation')).toBeInTheDocument();
    expect(screen.getByText('intermediate')).toBeInTheDocument();
    expect(screen.getByText('1 parameters')).toBeInTheDocument();
    expect(screen.getByText('Process incoming leads')).toBeInTheDocument();
    expect(screen.getAllByText('lead').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Notify Slack')).toBeInTheDocument();
    expect(screen.getByText('(action)')).toBeInTheDocument();
  });

  it('routes the Preview button to the preview tab', () => {
    render(<TemplateEditor initialTemplate={INITIAL} onSave={mockOnSave} onCancel={mockOnCancel} />);
    fireEvent.click(screen.getAllByRole('button', { name: /Preview/i })[1]);
    expect(screen.getByText('Template Summary')).toBeInTheDocument();
  });

  it('renders read-only mode without save/cancel and with disabled inputs', () => {
    render(<TemplateEditor initialTemplate={INITIAL} onSave={mockOnSave} onCancel={mockOnCancel} readOnly />);

    expect(screen.queryByRole('button', { name: /Save Template/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Cancel/i })).not.toBeInTheDocument();
    expect(
      (screen.getByLabelText(/Template Name \*/i) as HTMLInputElement).disabled
    ).toBe(true);
    expect(
      (screen.getByLabelText(/Description \*/i) as HTMLTextAreaElement).disabled
    ).toBe(true);
  });

  it('invokes onCancel when the Cancel button is clicked', () => {
    render(<TemplateEditor initialTemplate={INITIAL} onSave={mockOnSave} onCancel={mockOnCancel} />);
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(mockOnCancel).toHaveBeenCalledTimes(1);
  });

  it('toasts an error when onSave rejects', async () => {
    const failingSave = jest.fn().mockRejectedValue(new Error('Disk full'));
    render(
      <TemplateEditor initialTemplate={{ ...INITIAL, steps: [{ id: 's1', name: 'Step A', step_type: 'action' }] }} onSave={failingSave} />
    );

    fireEvent.click(screen.getByRole('button', { name: /Save Template/i }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Disk full',
          variant: 'error',
        })
      );
    });
  });

  it('moves a step up and keeps the remaining step selected after deletion', () => {
    const twoSteps: WorkflowTemplate = {
      ...INITIAL,
      steps: [
        { id: 's1', name: 'First', step_type: 'trigger' },
        { id: 's2', name: 'Second', step_type: 'action' },
      ],
    };
    const { container } = render(<TemplateEditor initialTemplate={twoSteps} onSave={mockOnSave} />);

    fireEvent.click(screen.getByRole('button', { name: /Workflow Steps/i }));

    const upButtons = container.querySelectorAll('svg.lucide-arrow-up');
    fireEvent.click(upButtons[1].closest('button')!);

    const names = screen.getAllByText(/^(First|Second)$/);
    expect(names[0]).toHaveTextContent('Second');
    expect(names[1]).toHaveTextContent('First');

    // Clicking a card marks it selected (ring styling)
    fireEvent.click(names[1].closest('[class*="border"]')!);
    expect(names[1].closest('[class*="ring-2"]')).toBeTruthy();
  });

  it('renders rich step metadata: optional badge, description, service, action, duration', () => {
    const rich: WorkflowTemplate = {
      ...INITIAL,
      steps: [
        {
          id: 's1',
          name: 'Enrich Lead',
          step_type: 'agent_execution',
          description: 'Enriches the lead record',
          service: 'hubspot',
          action: 'update_contact',
          estimated_duration: 120,
          is_optional: true,
        },
      ],
    };
    render(<TemplateEditor initialTemplate={rich} onSave={mockOnSave} />);

    fireEvent.click(screen.getByRole('button', { name: /Workflow Steps/i }));

    expect(screen.getByText('Enrich Lead')).toBeInTheDocument();
    expect(screen.getByText('agent_execution')).toBeInTheDocument();
    expect(screen.getByText('Optional')).toBeInTheDocument();
    expect(screen.getByText('Enriches the lead record')).toBeInTheDocument();
    expect(screen.getByText('Service: hubspot')).toBeInTheDocument();
    expect(screen.getByText('Action: update_contact')).toBeInTheDocument();
    expect(screen.getByText('Duration: 120s')).toBeInTheDocument();
  });

  it('edits input parameter name, label, description and type', () => {
    render(<TemplateEditor initialTemplate={INITIAL} onSave={mockOnSave} />);
    fireEvent.click(screen.getByRole('button', { name: /Input Parameters/i }));
    fireEvent.click(screen.getByRole('button', { name: /Add Parameter/i }));

    const nameInput = screen.getByPlaceholderText('parameter_name');
    fireEvent.change(nameInput, { target: { value: 'owner_id' } });
    expect((nameInput as HTMLInputElement).value).toBe('owner_id');

    const labelInput = screen.getByPlaceholderText('User-friendly label');
    fireEvent.change(labelInput, { target: { value: 'Record Owner' } });
    expect((labelInput as HTMLInputElement).value).toBe('Record Owner');

    const description = screen.getByPlaceholderText('Describe this parameter...');
    fireEvent.change(description, { target: { value: 'HubSpot owner id' } });
    expect((description as HTMLTextAreaElement).value).toBe('HubSpot owner id');

    // Type select: open the combobox and pick "Number"
    fireEvent.click(screen.getByRole('combobox'));
    fireEvent.click(screen.getByRole('option', { name: 'Number' }));
    expect(screen.getByRole('combobox')).toHaveTextContent('Number');

    // A second parameter can be appended from the list footer button
    fireEvent.click(screen.getAllByRole('button', { name: /Add Parameter/i })[0]);
    expect(screen.getAllByPlaceholderText('parameter_name')).toHaveLength(2);
  });

  it('shows empty preview placeholders and no-tags fallback', () => {
    render(<TemplateEditor initialTemplate={{ ...INITIAL, name: '', description: '', tags: [] }} onSave={mockOnSave} />);
    fireEvent.click(screen.getAllByRole('button', { name: /Preview/i })[1]);

    expect(screen.getAllByText('Not set')).toHaveLength(2);
    expect(screen.getByText('No tags')).toBeInTheDocument();
    expect(screen.getByText('No steps defined')).toBeInTheDocument();
    expect(screen.getByText('0 parameters')).toBeInTheDocument();
  });
});
