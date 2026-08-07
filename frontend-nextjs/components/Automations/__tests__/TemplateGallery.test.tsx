/**
 * TemplateGallery Component Tests
 *
 * Tests verify the real TemplateGallery component
 * (components/Automations/TemplateGallery.tsx, a DEFAULT export):
 * - Header + tagline rendering
 * - Featured Templates section (hidden when filtering)
 * - Category filter buttons narrow the grid
 * - Search by name, description and service
 * - Template card content (badges, services, stats, NEW badge)
 * - Empty search state
 * - "Use Template" button invokes onUseTemplate with the template
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import TemplateGallery, { WorkflowTemplate } from '../TemplateGallery';

describe('TemplateGallery', () => {
  const mockOnUseTemplate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the header and tagline', () => {
    render(<TemplateGallery />);

    expect(screen.getByRole('heading', { name: /workflow templates/i })).toBeInTheDocument();
    expect(
      screen.getByText(/Get started in minutes with pre-built automations/i)
    ).toBeInTheDocument();
  });

  it('shows the Featured Templates section with three featured cards', () => {
    render(<TemplateGallery />);

    expect(screen.getByRole('heading', { name: /featured templates/i })).toBeInTheDocument();
    // Featured cards render again in the All Templates grid below
    expect(screen.getAllByText('New Lead Notification').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('AI Lead Enrichment').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('Newsletter Subscriber Welcome').length).toBeGreaterThanOrEqual(2);
  });

  it('renders the full template count', () => {
    render(<TemplateGallery />);

    expect(screen.getByText('14 templates')).toBeInTheDocument();
  });

  it('renders template card metadata (services, time, steps, uses)', () => {
    render(<TemplateGallery />);

    // Services appear across multiple cards
    expect(screen.getAllByText('HubSpot').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('Slack').length).toBeGreaterThanOrEqual(4);
    // Times and step counts repeat across cards
    expect(screen.getAllByText('5 min').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('3 steps').length).toBeGreaterThanOrEqual(2);
    // Unique stats — featured card + grid card both render the uses count
    expect(screen.getAllByText('12,500')).toHaveLength(2);
    // New templates are flagged with a NEW badge
    expect(screen.getAllByText('NEW')).toHaveLength(3); // ticket-triage, meeting-notes, content-generator
    // Featured-but-not-top-3 template renders only in the All Templates grid
    expect(screen.getByText('AI Ticket Triage')).toBeInTheDocument();
  });

  it('filters templates by name when searching', async () => {
    const user = userEvent.setup();
    render(<TemplateGallery />);

    await user.type(screen.getByPlaceholderText('Search templates...'), 'AI Meeting Notes');

    expect(screen.getByText('AI Meeting Notes')).toBeInTheDocument();
    expect(screen.queryByText('New Lead Notification')).not.toBeInTheDocument();
    expect(screen.getByText('1 template')).toBeInTheDocument();
  });

  it('filters templates by service when searching', async () => {
    const user = userEvent.setup();
    render(<TemplateGallery />);

    await user.type(screen.getByPlaceholderText('Search templates...'), 'notion');

    expect(screen.getByText('Social Mentions to Notion')).toBeInTheDocument();
    expect(screen.getByText('AI Meeting Notes')).toBeInTheDocument();
    expect(screen.getByText('AI Content Generator')).toBeInTheDocument();
    expect(screen.getByText('3 templates')).toBeInTheDocument();
    expect(screen.queryByText('AI Lead Enrichment')).not.toBeInTheDocument();
  });

  it('filters templates by service count for "slack"', async () => {
    const user = userEvent.setup();
    render(<TemplateGallery />);

    await user.type(screen.getByPlaceholderText('Search templates...'), 'slack');

    expect(screen.getByText('8 templates')).toBeInTheDocument();
    expect(screen.queryByText('Social Mentions to Notion')).not.toBeInTheDocument();
  });

  it('filters templates by category', async () => {
    const user = userEvent.setup();
    render(<TemplateGallery />);

    await user.click(screen.getByRole('button', { name: /sales/i }));

    expect(screen.getByRole('heading', { name: /sales templates/i })).toBeInTheDocument();
    expect(screen.getByText('3 templates')).toBeInTheDocument();
    expect(screen.getByText('New Lead Notification')).toBeInTheDocument();
    expect(screen.getByText('AI Lead Enrichment')).toBeInTheDocument();
    expect(screen.getByText('Deal Stage Change Alerts')).toBeInTheDocument();
    expect(screen.queryByText('AI Ticket Triage')).not.toBeInTheDocument();
  });

  it('hides the featured section when a category is selected', async () => {
    const user = userEvent.setup();
    render(<TemplateGallery />);

    await user.click(screen.getByRole('button', { name: /support/i }));
    expect(screen.queryByRole('heading', { name: /featured templates/i })).not.toBeInTheDocument();
  });

  it('shows the empty state when no templates match the search', async () => {
    const user = userEvent.setup();
    render(<TemplateGallery />);

    await user.type(screen.getByPlaceholderText('Search templates...'), 'zzzz-nothing');

    expect(screen.getByText('No templates found')).toBeInTheDocument();
    expect(screen.getByText('Try a different search term or category')).toBeInTheDocument();
    expect(screen.getByText('0 templates')).toBeInTheDocument();
  });

  it('calls onUseTemplate with the template when Use Template is clicked', async () => {
    const user = userEvent.setup();
    render(<TemplateGallery onUseTemplate={mockOnUseTemplate} />);

    await user.click(screen.getAllByRole('button', { name: /use template/i })[0]);

    expect(mockOnUseTemplate).toHaveBeenCalledTimes(1);
    const template = mockOnUseTemplate.mock.calls[0][0] as WorkflowTemplate;
    expect(template.id).toBe('lead-to-slack');
    expect(template.name).toBe('New Lead Notification');
    expect(template.category).toBe('sales');
  });
});
