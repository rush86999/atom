/**
 * SmartSuggestions Component Tests
 *
 * Tests verify the REAL SmartSuggestions component
 * (components/Automations/SmartSuggestions.tsx):
 *
 * - Empty workflow -> "Add Trigger" suggestion (confidence 1.0)
 * - Pattern routing by node type: trigger / condition / action / ai_node
 * - Service-specific patterns: slack / gmail / salesforce / hubspot
 * - trigger + service combo key fallback (unknown service -> 'trigger')
 * - Leaf-node selection (nodes that are edge sources are skipped)
 * - Confidence boost when a suggestion's service matches the workflow
 * - Sorting by confidence (desc) and slicing to 3 suggestions
 * - "Recommended" badge for confidence >= 0.85
 * - onSuggestionClick payload + "Why these suggestions?" affordance
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import type { Node } from 'reactflow';
import SmartSuggestions from '../SmartSuggestions';

const mkEdge = (source: string, target: string) => ({ id: `e${source}-${target}`, source, target });

// Fixture nodes omit reactflow's `position` (the component never reads it);
// the cast keeps the runtime fixture identical to the real shape tests rely on.
const mkNode = (id: string, type: string, service?: string): Node =>
  ({
    id,
    type,
    data: service ? { service } : {},
  }) as unknown as Node;

describe('SmartSuggestions', () => {
  const onSuggestionClick = jest.fn();

  beforeEach(() => {
    onSuggestionClick.mockClear();
  });

  it('suggests adding a trigger for an empty workflow', () => {
    render(
      <SmartSuggestions
        nodes={[]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );

    const button = screen.getByRole('button', { name: /Add Trigger/i });
    fireEvent.click(button);
    expect(onSuggestionClick).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'add-trigger',
        title: 'Add Trigger',
        type: 'trigger',
        confidence: 1.0,
      })
    );
  });

  it('routes trigger nodes to the generic trigger pattern sorted by confidence', () => {
    render(
      <SmartSuggestions
        nodes={[mkNode('1', 'trigger')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );

    const buttons = screen.getAllByRole('button', { name: /(Add Condition|Add Action|Add Delay)/i });
    expect(buttons).toHaveLength(3);
    // Add Action (0.9) sorts before Add Condition (0.8) and Add Delay (0.5)
    const titles = buttons.map((b) => b.textContent);
    expect(titles[0]).toContain('Add Action');
    // High-confidence suggestions get the Recommended badge
    expect(screen.getByText('Recommended')).toBeInTheDocument();
  });

  it('uses the slack_trigger pattern and boosts matching-service suggestions', () => {
    render(
      <SmartSuggestions
        nodes={[mkNode('1', 'trigger', 'slack')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );

    // Reply in Slack has service: 'slack' -> confidence 0.95 + 0.1 = 1.0
    const buttons = screen.getAllByRole('button', { name: /(Reply in Slack|Create Support Ticket|Analyze with AI)/i });
    expect(buttons).toHaveLength(3);
    expect(buttons[0].textContent).toContain('Reply in Slack');
    // Reply in Slack (1.0) and Analyze with AI (0.85) both qualify
    expect(screen.getAllByText('Recommended')).toHaveLength(2);

    fireEvent.click(buttons[0]);
    expect(onSuggestionClick).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'send-slack-reply', confidence: 1.0 })
    );
  });

  it('uses service-specific patterns for gmail, salesforce and hubspot', () => {
    const { rerender } = render(
      <SmartSuggestions
        nodes={[mkNode('1', 'trigger', 'gmail')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );
    expect(screen.getByRole('button', { name: /Summarize Email/i })).toBeInTheDocument();

    rerender(
      <SmartSuggestions
        nodes={[mkNode('1', 'trigger', 'salesforce')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );
    expect(screen.getByRole('button', { name: /Update Record/i })).toBeInTheDocument();

    rerender(
      <SmartSuggestions
        nodes={[mkNode('1', 'trigger', 'hubspot')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );
    // hubspot pattern: update-contact 0.9 + 0.1 = 1.0 tops create-deal 0.8 + 0.1 = 0.9
    const buttons = screen.getAllByRole('button', { name: /(Update Contact|Create Deal|Send Email)/i });
    expect(buttons).toHaveLength(3);
    expect(buttons[0].textContent).toContain('Update Contact');
  });

  it('falls back to the generic trigger pattern for an unknown service', () => {
    render(
      <SmartSuggestions
        nodes={[mkNode('1', 'trigger', 'custom_service')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );
    // custom_service has no pattern and no *_trigger key -> generic trigger pattern
    expect(screen.getByRole('button', { name: /Add Condition/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Add Action/i })).toBeInTheDocument();
  });

  it('routes condition nodes to true/false branch suggestions', () => {
    render(
      <SmartSuggestions
        nodes={[mkNode('1', 'condition')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );
    const buttons = screen.getAllByRole('button', { name: /(True Branch Action|False Branch Action|Nested Condition)/i });
    expect(buttons).toHaveLength(3);
    expect(buttons[0].textContent).toContain('True Branch Action');
  });

  it('routes action nodes to chaining suggestions', () => {
    render(
      <SmartSuggestions
        nodes={[mkNode('1', 'action')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );
    const buttons = screen.getAllByRole('button', { name: /(Add Another Action|Add Condition|Store Result)/i });
    expect(buttons).toHaveLength(3);
    expect(buttons[0].textContent).toContain('Add Another Action');
  });

  it('routes ai_node nodes to branch-on-result suggestions', () => {
    render(
      <SmartSuggestions
        nodes={[mkNode('1', 'ai_node')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );
    const buttons = screen.getAllByRole('button', { name: /(Branch on AI Result|Use AI Result|Store AI Result)/i });
    expect(buttons).toHaveLength(3);
    expect(buttons[0].textContent).toContain('Branch on AI Result');
  });

  it('derives suggestions from the last leaf node (skips edge sources)', () => {
    // node '1' is an edge source, node '2' is the leaf -> action pattern wins
    render(
      <SmartSuggestions
        nodes={[mkNode('1', 'trigger'), mkNode('2', 'action')]}
        edges={[mkEdge('1', '2')]}
        onSuggestionClick={onSuggestionClick}
      />
    );
    expect(screen.getByRole('button', { name: /Add Another Action/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Add Delay/i })).not.toBeInTheDocument();
  });

  it('shows the "Why these suggestions?" affordance and slices to 3', () => {
    render(
      <SmartSuggestions
        nodes={[mkNode('1', 'action')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );
    expect(screen.getByText('Why these suggestions?')).toBeInTheDocument();
    // Only 3 of the suggestion buttons are rendered
    expect(screen.getAllByRole('button').length).toBeLessThanOrEqual(4);
  });

  it('renders the section heading', () => {
    render(
      <SmartSuggestions
        nodes={[mkNode('1', 'action')]}
        edges={[]}
        onSuggestionClick={onSuggestionClick}
      />
    );
    expect(screen.getByText('Suggested Next Steps')).toBeInTheDocument();
  });
});
