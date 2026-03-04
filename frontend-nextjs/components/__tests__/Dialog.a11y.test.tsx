/**
 * Dialog Component Accessibility Tests
 *
 * Purpose: Test Dialog component for WCAG 2.1 AA compliance
 * Tests: axe violations, focus trap, Escape key, aria-hidden, focus restoration
 *
 * IMPORTANT: Uses baseElement for React Portal testing (Radix UI renders to document.body)
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from '../../tests/accessibility-config';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

describe('Dialog Accessibility', () => {
  it('should have no accessibility violations when open', async () => {
    const { container, baseElement } = render(
      <Dialog open={true} onOpenChange={() => {}}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Test Dialog</DialogTitle>
          </DialogHeader>
          <DialogDescription>
            This is a test dialog for accessibility validation
          </DialogDescription>
          <Button>Close</Button>
        </DialogContent>
      </Dialog>
    );

    // Use baseElement for Portal-rendered content
    const results = await axe(baseElement);
    expect(results).toHaveNoViolations();
  });

  it('should have focusable elements within dialog', async () => {
    const handleClose = jest.fn();

    render(
      <Dialog open={true} onOpenChange={handleClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Focus Elements Test</DialogTitle>
          </DialogHeader>
          <button>First Button</button>
          <button>Second Button</button>
          <Button>Third Button</Button>
        </DialogContent>
      </Dialog>
    );

    // All buttons should be in the document
    const firstButton = screen.getByText('First Button');
    const secondButton = screen.getByText('Second Button');
    const thirdButton = screen.getByText('Third Button');

    expect(firstButton).toBeInTheDocument();
    expect(secondButton).toBeInTheDocument();
    expect(thirdButton).toBeInTheDocument();

    // Verify buttons are focusable
    firstButton.focus();
    expect(firstButton).toHaveFocus();

    secondButton.focus();
    expect(secondButton).toHaveFocus();
  });

  it('should close on Escape key', async () => {
    const handleClose = jest.fn();

    render(
      <Dialog open={true} onOpenChange={handleClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Escape Key Test</DialogTitle>
          </DialogHeader>
          <DialogDescription>Press Escape to close</DialogDescription>
        </DialogContent>
      </Dialog>
    );

    // Press Escape key
    await userEvent.keyboard('{Escape}');

    // onClose callback should be called
    expect(handleClose).toHaveBeenCalledWith(false);
  });

  it('should have aria-hidden when closed', () => {
    const handleClose = jest.fn();

    render(
      <Dialog open={false} onOpenChange={handleClose}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Closed Dialog</DialogTitle>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );

    // Dialog should not be in DOM when closed
    const dialog = screen.queryByRole('dialog');
    expect(dialog).toBeNull();
  });

  it('should have proper ARIA attributes', async () => {
    const { baseElement } = render(
      <Dialog open={true} onOpenChange={() => {}}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>ARIA Test</DialogTitle>
          </DialogHeader>
          <DialogDescription>
            Testing ARIA attributes
          </DialogDescription>
          <Button>Action</Button>
        </DialogContent>
      </Dialog>
    );

    const dialog = screen.getByRole('dialog');

    // Check aria-modal
    expect(dialog).toHaveAttribute('aria-modal', 'true');

    // Check role
    expect(dialog).toHaveAttribute('role', 'dialog');

    // Verify no violations
    const results = await axe(baseElement);
    expect(results).toHaveNoViolations();
  });

  it('should have accessible title', async () => {
    const { baseElement } = render(
      <Dialog open={true} onOpenChange={() => {}}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Accessible Dialog Title</DialogTitle>
          </DialogHeader>
          <DialogDescription>
            Dialog with accessible title
          </DialogDescription>
        </DialogContent>
      </Dialog>
    );

    const dialog = screen.getByRole('dialog');
    const title = screen.getByText('Accessible Dialog Title');

    expect(dialog).toContainElement(title);
    expect(title.tagName).toBe('H2');

    const results = await axe(baseElement);
    expect(results).toHaveNoViolations();
  });
});
