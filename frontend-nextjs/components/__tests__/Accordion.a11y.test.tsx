import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'jest-axe';
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent
} from '@/components/ui/accordion';

/**
 * Accordion Accessibility Test Suite
 *
 * Tests WCAG 2.1 AA compliance for Accordion compound component:
 * - ARIA attributes: aria-expanded, aria-controls
 * - Keyboard navigation: Enter, Space keys
 * - Radix UI handles ARIA automatically
 *
 * Reference: WAI-ARIA Authoring Practices 1.2 - Accordion Pattern (Disclosures)
 * https://www.w3.org/WAI/ARIA/apg/patterns/accordion/
 */

describe('Accordion Accessibility', () => {
  const renderAccordion = () => {
    return render(
      <Accordion type="single" collapsible>
        <AccordionItem value="item-1">
          <AccordionTrigger>Section 1</AccordionTrigger>
          <AccordionContent>
            <p>Content 1</p>
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="item-2">
          <AccordionTrigger>Section 2</AccordionTrigger>
          <AccordionContent>
            <p>Content 2</p>
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="item-3">
          <AccordionTrigger>Section 3</AccordionTrigger>
          <AccordionContent>
            <p>Content 3</p>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    );
  };

  it('should have no accessibility violations', async () => {
    const { container } = renderAccordion();
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  it('should have aria-expanded on trigger', () => {
    renderAccordion();

    const trigger1 = screen.getByRole('button', { name: 'Section 1' });

    // Radix UI Accordion handles aria-expanded automatically
    expect(trigger1).toHaveAttribute('aria-expanded');
  });

  it('should toggle aria-expanded on click', async () => {
    const user = userEvent.setup();
    renderAccordion();

    const trigger1 = screen.getByRole('button', { name: 'Section 1' });

    // Initially collapsed
    expect(trigger1).toHaveAttribute('aria-expanded', 'false');

    // Click to expand
    await user.click(trigger1);

    // Should be expanded
    expect(trigger1).toHaveAttribute('aria-expanded', 'true');

    // Click to collapse
    await user.click(trigger1);

    // Should be collapsed again
    expect(trigger1).toHaveAttribute('aria-expanded', 'false');
  });

  it('should toggle with Enter key', async () => {
    const user = userEvent.setup();
    renderAccordion();

    const trigger1 = screen.getByRole('button', { name: 'Section 1' });

    // Focus trigger
    trigger1.focus();
    expect(trigger1).toHaveFocus();

    // Initially collapsed
    expect(trigger1).toHaveAttribute('aria-expanded', 'false');

    // Press Enter to expand
    await user.keyboard('{Enter}');

    // Should be expanded
    expect(trigger1).toHaveAttribute('aria-expanded', 'true');
  });

  it('should toggle with Space key', async () => {
    const user = userEvent.setup();
    renderAccordion();

    const trigger2 = screen.getByRole('button', { name: 'Section 2' });

    // Focus trigger
    trigger2.focus();
    expect(trigger2).toHaveFocus();

    // Initially collapsed
    expect(trigger2).toHaveAttribute('aria-expanded', 'false');

    // Press Space to expand
    await user.keyboard(' ');

    // Should be expanded
    expect(trigger2).toHaveAttribute('aria-expanded', 'true');
  });

  it('should have aria-controls linking to content', () => {
    renderAccordion();

    const trigger1 = screen.getByRole('button', { name: 'Section 1' });

    // Radix UI Accordion handles aria-controls automatically
    // Trigger should have aria-controls pointing to content
    expect(trigger1).toHaveAttribute('aria-controls');
  });

  it('should display content when expanded', async () => {
    const user = userEvent.setup();
    renderAccordion();

    const trigger1 = screen.getByRole('button', { name: 'Section 1' });

    // Content may not be in DOM initially (Radix UI pattern)
    // Click to expand
    await user.click(trigger1);

    // Content should now be in DOM and visible
    const content1 = screen.getByText('Content 1');
    expect(content1).toBeVisible();
  });

  it('should hide content when collapsed', async () => {
    const user = userEvent.setup();
    renderAccordion();

    const trigger1 = screen.getByRole('button', { name: 'Section 1' });

    // Expand first
    await user.click(trigger1);
    const content1 = screen.getByText('Content 1');
    expect(content1).toBeVisible();

    // Collapse
    await user.click(trigger1);

    // Content should be hidden (may still be in DOM but not visible)
    if (screen.queryByText('Content 1')) {
      expect(screen.queryByText('Content 1')).not.toBeVisible();
    }
  });
});
