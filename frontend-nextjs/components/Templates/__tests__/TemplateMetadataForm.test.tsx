/**
 * TemplateMetadataForm component tests.
 *
 * Pure form component driven by `metadata`/`onChange` props. Covers field
 * edits, tag add (button + Enter), tag remove, suggested tags, preview card
 * rendering, and read-only mode.
 */
import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { TemplateMetadataForm, TemplateMetadata } from '../TemplateMetadataForm';

const METADATA: TemplateMetadata = {
  name: 'Lead Processing',
  description: 'Process incoming leads automatically',
  category: 'automation',
  complexity: 'intermediate',
  tags: ['lead'],
};

describe('TemplateMetadataForm', () => {
  const mockOnChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders name, description, category and complexity with current values', () => {
    render(<TemplateMetadataForm metadata={METADATA} onChange={mockOnChange} />);

    expect(
      (screen.getByLabelText(/Template Name \*/i) as HTMLInputElement).value
    ).toBe('Lead Processing');
    expect(
      (screen.getByLabelText(/Description \*/i) as HTMLTextAreaElement).value
    ).toBe('Process incoming leads automatically');
    // Category + complexity selects both expose combobox role.
    expect(screen.getAllByRole('combobox')).toHaveLength(2);
    expect(screen.getAllByText('lead').length).toBeGreaterThanOrEqual(1);
  });

  it('propagates name changes to onChange', () => {
    render(<TemplateMetadataForm metadata={METADATA} onChange={mockOnChange} />);
    fireEvent.change(screen.getByLabelText(/Template Name \*/i), {
      target: { value: 'Renamed' },
    });
    expect(mockOnChange).toHaveBeenCalledWith({ ...METADATA, name: 'Renamed' });
  });

  it('propagates description changes to onChange', () => {
    render(<TemplateMetadataForm metadata={METADATA} onChange={mockOnChange} />);
    fireEvent.change(screen.getByLabelText(/Description \*/i), {
      target: { value: 'New description' },
    });
    expect(mockOnChange).toHaveBeenCalledWith({ ...METADATA, description: 'New description' });
  });

  it('adds a tag via the input + button and lowercases it', () => {
    const { container } = render(
      <TemplateMetadataForm metadata={METADATA} onChange={mockOnChange} />
    );
    fireEvent.change(screen.getByPlaceholderText('Add a tag...'), {
      target: { value: 'CRM' },
    });
    fireEvent.click(container.querySelector('svg.lucide-plus')!.closest('button')!);
    expect(mockOnChange).toHaveBeenCalledWith({
      ...METADATA,
      tags: ['lead', 'crm'],
    });
  });

  it('adds a tag on Enter', () => {
    render(<TemplateMetadataForm metadata={METADATA} onChange={mockOnChange} />);
    fireEvent.change(screen.getByPlaceholderText('Add a tag...'), {
      target: { value: 'sales' },
    });
    fireEvent.keyPress(screen.getByPlaceholderText('Add a tag...'), {
      key: 'Enter',
      code: 'Enter',
      charCode: 13,
    });
    expect(mockOnChange).toHaveBeenCalledWith({
      ...METADATA,
      tags: ['lead', 'sales'],
    });
  });

  it('does not add a duplicate tag', () => {
    render(<TemplateMetadataForm metadata={METADATA} onChange={mockOnChange} />);
    fireEvent.change(screen.getByPlaceholderText('Add a tag...'), {
      target: { value: 'lead' },
    });
    fireEvent.keyPress(screen.getByPlaceholderText('Add a tag...'), {
      key: 'Enter',
      code: 'Enter',
      charCode: 13,
    });
    expect(mockOnChange).not.toHaveBeenCalled();
  });

  it('removes a tag via its X button', () => {
    render(<TemplateMetadataForm metadata={METADATA} onChange={mockOnChange} />);
    const badge = screen.getAllByText('lead')[0].closest('div')!;
    fireEvent.click(within(badge).getByRole('button'));
    expect(mockOnChange).toHaveBeenCalledWith({ ...METADATA, tags: [] });
  });

  it('adds a suggested tag by clicking the suggestion', () => {
    render(<TemplateMetadataForm metadata={METADATA} onChange={mockOnChange} />);
    fireEvent.click(screen.getByRole('button', { name: '+ automation' }));
    expect(mockOnChange).toHaveBeenCalledWith({
      ...METADATA,
      tags: ['lead', 'automation'],
    });
  });

  it('renders the preview card with resolved labels and fallbacks', () => {
    const empty: TemplateMetadata = {
      name: '',
      description: '',
      category: 'unknown-cat',
      complexity: 'unknown-level',
      tags: [],
    };
    render(<TemplateMetadataForm metadata={empty} onChange={mockOnChange} />);

    expect(screen.getByText('Preview')).toBeInTheDocument();
    expect(screen.getByText('Untitled Template')).toBeInTheDocument();
    expect(screen.getByText('No description')).toBeInTheDocument();
    // Unknown values fall back to the raw value.
    expect(screen.getByText('unknown-cat')).toBeInTheDocument();
    expect(screen.getByText('unknown-level')).toBeInTheDocument();
  });

  it('renders the preview card with known labels', () => {
    render(<TemplateMetadataForm metadata={METADATA} onChange={mockOnChange} />);
    expect(screen.getByText('Lead Processing')).toBeInTheDocument();
    // "Automation"/"Intermediate" appear in the select triggers AND the preview
    // card badges — assert each renders at least twice (trigger + preview).
    expect(screen.getAllByText('Automation').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('Intermediate').length).toBeGreaterThanOrEqual(2);
    // Description renders in both the textarea and the preview card.
    expect(
      screen.getAllByText('Process incoming leads automatically').length
    ).toBeGreaterThanOrEqual(2);
  });

  it('disables all inputs and hides tag controls in read-only mode', () => {
    render(<TemplateMetadataForm metadata={METADATA} onChange={mockOnChange} readOnly />);

    expect(
      (screen.getByLabelText(/Template Name \*/i) as HTMLInputElement).disabled
    ).toBe(true);
    expect(
      (screen.getByLabelText(/Description \*/i) as HTMLTextAreaElement).disabled
    ).toBe(true);
    expect(screen.queryByPlaceholderText('Add a tag...')).not.toBeInTheDocument();
    expect(screen.queryByText(/Suggested tags:/i)).not.toBeInTheDocument();
    // Tags render without remove buttons — the only tag-remove icon button gone.
    expect(screen.getAllByText('lead').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByRole('button', { name: '+ automation' })).not.toBeInTheDocument();
  });
});
