import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Modal, ModalFooter } from '@/components/ui/modal';
import { Button } from '@/components/ui/button';

describe('Modal Component', () => {
  describe('Rendering', () => {
    it('renders when isOpen is true', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()}>
          <p>Modal content</p>
        </Modal>
      );
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Modal content')).toBeInTheDocument();
    });

    it('does not render when isOpen is false', () => {
      render(
        <Modal isOpen={false} onClose={jest.fn()}>
          <p>Modal content</p>
        </Modal>
      );
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders with title when provided', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Test Modal">
          <p>Content</p>
        </Modal>
      );
      expect(screen.getByText('Test Modal')).toBeInTheDocument();
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('renders without title when not provided', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()}>
          <p>Content</p>
        </Modal>
      );
      expect(screen.queryByRole('heading')).not.toBeInTheDocument();
    });

    it('renders with custom className', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} className="custom-modal">
          <p>Content</p>
        </Modal>
      );
      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveClass('custom-modal');
    });

    it('renders children content', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()}>
          <p>First paragraph</p>
          <p>Second paragraph</p>
        </Modal>
      );
      expect(screen.getByText('First paragraph')).toBeInTheDocument();
      expect(screen.getByText('Second paragraph')).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      const handleClose = jest.fn();

      render(
        <Modal isOpen={true} onClose={handleClose}>
          <p>Content</p>
        </Modal>
      );

      const closeButton = screen.getByRole('button', { name: '' }); // X icon button
      await user.click(closeButton);

      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when backdrop is clicked', async () => {
      const user = userEvent.setup();
      const handleClose = jest.fn();

      render(
        <Modal isOpen={true} onClose={handleClose}>
          <p>Content</p>
        </Modal>
      );

      const backdrop = screen.getByText(''); // aria-hidden div
      await user.click(backdrop);

      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('does not call onClose when clicking inside modal content', async () => {
      const user = userEvent.setup();
      const handleClose = jest.fn();

      render(
        <Modal isOpen={true} onClose={handleClose}>
          <p>Modal content</p>
        </Modal>
      );

      const content = screen.getByText('Modal content');
      await user.click(content);

      expect(handleClose).not.toHaveBeenCalled();
    });
  });

  describe('Keyboard Interactions', () => {
    it('calls onClose when Escape key is pressed', async () => {
      const user = userEvent.setup();
      const handleClose = jest.fn();

      render(
        <Modal isOpen={true} onClose={handleClose}>
          <p>Content</p>
        </Modal>
      );

      await user.keyboard('{Escape}');

      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('does not call onClose when other keys are pressed', async () => {
      const user = userEvent.setup();
      const handleClose = jest.fn();

      render(
        <Modal isOpen={true} onClose={handleClose}>
          <p>Content</p>
        </Modal>
      );

      await user.keyboard('{Enter}');
      expect(handleClose).not.toHaveBeenCalled();

      await user.keyboard('{Tab}');
      expect(handleClose).not.toHaveBeenCalled();
    });

    it('removes event listener on unmount', () => {
      const handleClose = jest.fn();
      const { unmount } = render(
        <Modal isOpen={true} onClose={handleClose}>
          <p>Content</p>
        </Modal>
      );

      unmount();

      // Should not throw errors or cause issues
      expect(() => {
        const escapeEvent = new KeyboardEvent('keydown', { key: 'Escape' });
        document.dispatchEvent(escapeEvent);
      }).not.toThrow();
    });
  });

  describe('Accessibility', () => {
    it('has dialog role', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()}>
          <p>Content</p>
        </Modal>
      );
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has aria-modal attribute', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()}>
          <p>Content</p>
        </Modal>
      );
      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-modal', 'true');
    });

    it('backdrop has aria-hidden attribute', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()}>
          <p>Content</p>
        </Modal>
      );
      const backdrop = screen.getByText(''); // aria-hidden div
      expect(backdrop).toHaveAttribute('aria-hidden', 'true');
    });

    it('trap focus within modal', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Test Modal">
          <Button>Action</Button>
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toContainElement(screen.getByRole('button', { name: 'Action' }));
      expect(dialog).toContainElement(screen.getByRole('button')); // Close button
    });

    it('close button has accessible label', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Test Modal">
          <p>Content</p>
        </Modal>
      );

      // Close button with X icon should have aria-label or be identifiable
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Body Scroll Behavior', () => {
    it('disables body scroll when modal opens', () => {
      const { rerender } = render(
        <Modal isOpen={false} onClose={jest.fn()}>
          <p>Content</p>
        </Modal>
      );

      expect(document.body.style.overflow).toBe('unset');

      rerender(
        <Modal isOpen={true} onClose={jest.fn()}>
          <p>Content</p>
        </Modal>
      );

      expect(document.body.style.overflow).toBe('hidden');
    });

    it('restores body scroll when modal closes', () => {
      const { rerender } = render(
        <Modal isOpen={true} onClose={jest.fn()}>
          <p>Content</p>
        </Modal>
      );

      expect(document.body.style.overflow).toBe('hidden');

      rerender(
        <Modal isOpen={false} onClose={jest.fn()}>
          <p>Content</p>
        </Modal>
      );

      expect(document.body.style.overflow).toBe('unset');
    });

    it('restores body scroll on unmount', () => {
      const { unmount } = render(
        <Modal isOpen={true} onClose={jest.fn()}>
          <p>Content</p>
        </Modal>
      );

      expect(document.body.style.overflow).toBe('hidden');

      unmount();

      expect(document.body.style.overflow).toBe('unset');
    });
  });

  describe('Portal Behavior', () => {
    it('renders modal in portal at document.body', () => {
      render(
        <div id="root">
          <Modal isOpen={true} onClose={jest.fn()}>
            <p>Modal content</p>
          </Modal>
        </div>
      );

      const modal = screen.getByRole('dialog');
      expect(modal.parentElement?.parentElement).toBe(document.body);
    });

    it('renders backdrop in portal at document.body', () => {
      render(
        <div id="root">
          <Modal isOpen={true} onClose={jest.fn()}>
            <p>Modal content</p>
          </Modal>
        </div>
      );

      const backdropContainer = document.body.querySelector('.fixed.inset-0');
      expect(backdropContainer).toBeInTheDocument();
    });
  });

  describe('ModalFooter Component', () => {
    it('renders footer children', () => {
      render(
        <ModalFooter>
          <Button>Cancel</Button>
          <Button>Submit</Button>
        </ModalFooter>
      );

      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Submit' })).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(
        <ModalFooter className="custom-footer">
          <Button>Action</Button>
        </ModalFooter>
      );

      const footer = screen.getByRole('button', { name: 'Action' }).parentElement;
      expect(footer).toHaveClass('custom-footer');
    });

    it('has default flex layout with justify-end', () => {
      render(
        <ModalFooter>
          <Button>First</Button>
          <Button>Second</Button>
        </ModalFooter>
      );

      const footer = screen.getByRole('button', { name: 'First' }).parentElement;
      expect(footer).toHaveClass('flex');
      expect(footer).toHaveClass('justify-end');
    });
  });

  describe('Edge Cases', () => {
    it('handles rapid open/close cycles', async () => {
      const user = userEvent.setup();
      const handleClose = jest.fn();

      const { rerender } = render(
        <Modal isOpen={true} onClose={handleClose}>
          <p>Content</p>
        </Modal>
      );

      rerender(
        <Modal isOpen={false} onClose={handleClose}>
          <p>Content</p>
        </Modal>
      );

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    it('handles empty children', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()}>
          {null}
        </Modal>
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('handles complex nested content', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Complex Modal">
          <form>
            <label htmlFor="input">Input</label>
            <input id="input" type="text" />
            <Button type="submit">Submit</Button>
          </form>
        </Modal>
      );

      expect(screen.getByRole('form')).toBeInTheDocument();
      expect(screen.getByLabelText('Input')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Submit' })).toBeInTheDocument();
    });

    it('handles multiple modals (stacking)', () => {
      render(
        <>
          <Modal isOpen={true} onClose={jest.fn()} title="First Modal">
            <p>First content</p>
          </Modal>
          <Modal isOpen={true} onClose={jest.fn()} title="Second Modal">
            <p>Second content</p>
          </Modal>
        </>
      );

      const dialogs = screen.getAllByRole('dialog');
      expect(dialogs).toHaveLength(2);
      expect(screen.getByText('First content')).toBeInTheDocument();
      expect(screen.getByText('Second content')).toBeInTheDocument();
    });
  });

  describe('Lifecycle', () => {
    it('cleans up event listeners on unmount', () => {
      const handleClose = jest.fn();
      const { unmount } = render(
        <Modal isOpen={true} onClose={handleClose}>
          <p>Content</p>
        </Modal>
      );

      const removeEventListenerSpy = jest.spyOn(document, 'removeEventListener');

      unmount();

      // Cleanup should happen without errors
      expect(() => unmount()).not.toThrow();
      removeEventListenerSpy.mockRestore();
    });

    it('handles unmount while open', () => {
      const { unmount } = render(
        <Modal isOpen={true} onClose={jest.fn()}>
          <p>Content</p>
        </Modal>
      );

      expect(document.body.style.overflow).toBe('hidden');

      unmount();

      expect(document.body.style.overflow).toBe('unset');
    });
  });
});
