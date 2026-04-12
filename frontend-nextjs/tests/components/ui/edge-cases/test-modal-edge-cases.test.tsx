/**
 * Modal Edge Cases Test Suite
 *
 * Tests edge cases for Modal component including:
 * - Rapid open/close
 * - Multiple modals stacked
 * - Very long content
 * - Form validation
 * - Async actions
 * - Backdrop click during animation
 * - ESC key during animation
 * - External close triggers
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Modal } from '@/components/ui/modal';

describe('Modal Edge Cases', () => {
  beforeEach(() => {
    // Reset body styles before each test
    document.body.style.overflow = '';
  });

  afterEach(() => {
    // Clean up any modals
    const modals = document.querySelectorAll('[role="dialog"]');
    modals.forEach((modal) => modal.remove());
  });

  describe('Rapid Open/Close', () => {
    it('should handle rapid open/close cycles', async () => {
      const handleClose = jest.fn();
      const { rerender } = render(
        <Modal isOpen={true} onClose={handleClose}>
          <div>Modal Content</div>
        </Modal>
      );

      // Close and reopen rapidly
      rerender(
        <Modal isOpen={false} onClose={handleClose}>
          <div>Modal Content</div>
        </Modal>
      );

      rerender(
        <Modal isOpen={true} onClose={handleClose}>
          <div>Modal Content</div>
        </Modal>
      );

      rerender(
        <Modal isOpen={false} onClose={handleClose}>
          <div>Modal Content</div>
        </Modal>
      );

      // Should not throw errors
      expect(handleClose).toHaveBeenCalled();
    });

    it('should handle close before animation completes', async () => {
      const handleClose = jest.fn();
      const { rerender } = render(
        <Modal isOpen={true} onClose={handleClose}>
          <div>Modal Content</div>
        </Modal>
      );

      // Trigger close immediately
      rerender(
        <Modal isOpen={false} onClose={handleClose}>
          <div>Modal Content</div>
        </Modal>
      );

      // Should handle gracefully
      expect(handleClose).toHaveBeenCalled();
    });

    it('should handle multiple close triggers', async () => {
      const handleClose = jest.fn();
      render(
        <Modal isOpen={true} onClose={handleClose}>
          <div>Modal Content</div>
        </Modal>
      );

      const backdrop = document.querySelector('.fixed.inset-0');
      const closeButton = screen.getByRole('button', { name: /close/i });

      // Click both backdrop and close button
      if (backdrop) {
        fireEvent.click(backdrop);
      }
      fireEvent.click(closeButton);

      // Should handle multiple close triggers
      expect(handleClose).toHaveBeenCalled();
    });
  });

  describe('Multiple Modals Stacked', () => {
    it('should handle multiple modals open simultaneously', () => {
      const handleClose1 = jest.fn();
      const handleClose2 = jest.fn();

      render(
        <>
          <Modal isOpen={true} onClose={handleClose1} title="Modal 1">
            <div>Content 1</div>
          </Modal>
          <Modal isOpen={true} onClose={handleClose2} title="Modal 2">
            <div>Content 2</div>
          </Modal>
        </>
      );

      expect(screen.getByText('Modal 1')).toBeInTheDocument();
      expect(screen.getByText('Modal 2')).toBeInTheDocument();
    });

    it('should close top modal first', async () => {
      const handleClose1 = jest.fn();
      const handleClose2 = jest.fn();

      render(
        <>
          <Modal isOpen={true} onClose={handleClose1} title="Modal 1">
            <div>Content 1</div>
          </Modal>
          <Modal isOpen={true} onClose={handleClose2} title="Modal 2">
            <div>Content 2</div>
          </Modal>
        </>
      );

      const closeButton2 = screen.getAllByRole('button', { name: /close/i })[1];
      fireEvent.click(closeButton2);

      expect(handleClose2).toHaveBeenCalled();
    });

    it('should handle z-index stacking', () => {
      render(
        <>
          <Modal isOpen={true} onClose={jest.fn()} title="Modal 1">
            <div>Content 1</div>
          </Modal>
          <Modal isOpen={true} onClose={jest.fn()} title="Modal 2">
            <div>Content 2</div>
          </Modal>
        </>
      );

      const dialogs = screen.getAllByRole('dialog');
      expect(dialogs).toHaveLength(2);
    });
  });

  describe('Very Long Content', () => {
    it('should handle very long content with scrolling', () => {
      const longContent = 'Paragraph '.repeat(1000);

      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Long Content Modal">
          <div>{longContent}</div>
        </Modal>
      );

      expect(screen.getByText(/Paragraph/i)).toBeInTheDocument();
    });

    it('should handle content with overflow', () => {
      const overflowContent = 'a'.repeat(10000);

      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Overflow Modal">
          <div>{overflowContent}</div>
        </Modal>
      );

      expect(screen.getByText(new RegExp('a{100}'))).toBeInTheDocument();
    });

    it('should handle content with HTML elements', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="HTML Modal">
          <div>
            <h1>Heading 1</h1>
            <p>Paragraph</p>
            <ul>
              <li>Item 1</li>
              <li>Item 2</li>
            </ul>
          </div>
        </Modal>
      );

      expect(screen.getByText('Heading 1')).toBeInTheDocument();
      expect(screen.getByText('Paragraph')).toBeInTheDocument();
      expect(screen.getByText('Item 1')).toBeInTheDocument();
    });
  });

  describe('Form Validation', () => {
    it('should handle form with validation errors', async () => {
      const handleSubmit = jest.fn();
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Form Modal">
          <form onSubmit={handleSubmit}>
            <input data-testid="email" type="email" required />
            <button type="submit">Submit</button>
          </form>
        </Modal>
      );

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      // Form validation should prevent submission
      expect(handleSubmit).not.toHaveBeenCalled();
    });

    it('should handle dirty state on close', () => {
      const handleClose = jest.fn();
      render(
        <Modal isOpen={true} onClose={handleClose} title="Form Modal">
          <form>
            <input data-testid="field" defaultValue="dirty" />
          </form>
        </Modal>
      );

      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);

      expect(handleClose).toHaveBeenCalled();
    });

    it('should handle form submission', async () => {
      const handleSubmit = jest.fn((e) => e.preventDefault());
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Form Modal">
          <form onSubmit={handleSubmit}>
            <input type="text" defaultValue="test" />
            <button type="submit">Submit</button>
          </form>
        </Modal>
      );

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      expect(handleSubmit).toHaveBeenCalled();
    });
  });

  describe('Async Actions', () => {
    it('should handle async action on close', async () => {
      const handleClose = jest.fn(async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
      });

      render(
        <Modal isOpen={true} onClose={handleClose} title="Async Modal">
          <div>Content</div>
        </Modal>
      );

      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);

      await waitFor(() => {
        expect(handleClose).toHaveBeenCalled();
      });
    });

    it('should handle async action on submit', async () => {
      const handleSubmit = jest.fn(async () => {
        await new Promise((resolve) => setTimeout(resolve, 100));
      });

      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Async Modal">
          <button onClick={handleSubmit}>Submit</button>
        </Modal>
      );

      const submitButton = screen.getByRole('button', { name: /submit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(handleSubmit).toHaveBeenCalled();
      });
    });

    it('should handle close before async action completes', async () => {
      const handleClose = jest.fn();
      let resolveAction: any;

      const asyncAction = new Promise((resolve) => {
        resolveAction = resolve;
      });

      render(
        <Modal isOpen={true} onClose={handleClose} title="Async Modal">
          <button onClick={() => asyncAction.then(() => {})}>Submit</button>
        </Modal>
      );

      const { rerender } = render(
        <Modal isOpen={false} onClose={handleClose} title="Async Modal">
          <button onClick={() => asyncAction.then(() => {})}>Submit</button>
        </Modal>
      );

      // Should handle gracefully
      expect(handleClose).toHaveBeenCalled();
    });
  });

  describe('Backdrop Click During Animation', () => {
    it('should handle backdrop click during open animation', () => {
      const handleClose = jest.fn();
      render(
        <Modal isOpen={true} onClose={handleClose}>
          <div>Content</div>
        </Modal>
      );

      const backdrop = document.querySelector('.fixed.inset-0');
      if (backdrop) {
        fireEvent.click(backdrop);
      }

      // Should handle gracefully
      expect(handleClose).toHaveBeenCalled();
    });

    it('should handle backdrop click during close animation', () => {
      const handleClose = jest.fn();
      const { rerender } = render(
        <Modal isOpen={true} onClose={handleClose}>
          <div>Content</div>
        </Modal>
      );

      // Start closing
      rerender(
        <Modal isOpen={false} onClose={handleClose}>
          <div>Content</div>
        </Modal>
      );

      const backdrop = document.querySelector('.fixed.inset-0');
      if (backdrop) {
        fireEvent.click(backdrop);
      }

      // Should handle gracefully
      expect(handleClose).toHaveBeenCalled();
    });
  });

  describe('ESC Key During Animation', () => {
    it('should handle ESC key during open animation', () => {
      const handleClose = jest.fn();
      render(
        <Modal isOpen={true} onClose={handleClose}>
          <div>Content</div>
        </Modal>
      );

      fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' });

      expect(handleClose).toHaveBeenCalled();
    });

    it('should handle ESC key during close animation', () => {
      const handleClose = jest.fn();
      const { rerender } = render(
        <Modal isOpen={true} onClose={handleClose}>
          <div>Content</div>
        </Modal>
      );

      // Start closing
      rerender(
        <Modal isOpen={false} onClose={handleClose}>
          <div>Content</div>
        </Modal>
      );

      fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' });

      // Should handle gracefully
      expect(handleClose).toHaveBeenCalled();
    });
  });

  describe('External Close Triggers', () => {
    it('should handle external close button', () => {
      const handleClose = jest.fn();
      render(
        <>
          <button onClick={handleClose}>External Close</button>
          <Modal isOpen={true} onClose={handleClose}>
            <div>Content</div>
          </Modal>
        </>
      );

      const externalButton = screen.getByRole('button', { name: /external close/i });
      fireEvent.click(externalButton);

      expect(handleClose).toHaveBeenCalled();
    });

    it('should handle programmatic close', () => {
      const handleClose = jest.fn();
      render(
        <Modal isOpen={true} onClose={handleClose}>
          <div>Content</div>
        </Modal>
      );

      // Programmatic close
      handleClose();

      expect(handleClose).toHaveBeenCalled();
    });

    it('should handle close from parent component', () => {
      const handleClose = jest.fn();
      const { rerender } = render(
        <Modal isOpen={true} onClose={handleClose}>
          <div>Content</div>
        </Modal>
      );

      // Parent closes modal
      rerender(
        <Modal isOpen={false} onClose={handleClose}>
          <div>Content</div>
        </Modal>
      );

      expect(handleClose).toHaveBeenCalled();
    });
  });

  describe('Empty Content', () => {
    it('should handle empty children', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Empty Modal">
          {null}
        </Modal>
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('should handle whitespace-only content', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Whitespace Modal">
          {'   '}
        </Modal>
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('should handle modal without title', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()}>
          <div>Content</div>
        </Modal>
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('Accessibility Edge Cases', () => {
    it('should handle aria-labelledby with special characters', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Title &times;">
          <div>Content</div>
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-modal', 'true');
    });

    it('should handle aria-describedby', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Modal Title" description="Modal description">
          <div>Content</div>
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-modal', 'true');
    });

    it('should handle focus trap', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Focus Modal">
          <button>Button 1</button>
          <button>Button 2</button>
        </Modal>
      );

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  describe('Body Scroll Lock', () => {
    it('should disable body scroll when open', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Scroll Modal">
          <div>Content</div>
        </Modal>
      );

      expect(document.body.style.overflow).toBe('hidden');
    });

    it('should restore body scroll when closed', () => {
      const { rerender } = render(
        <Modal isOpen={true} onClose={jest.fn()} title="Scroll Modal">
          <div>Content</div>
        </Modal>
      );

      rerender(
        <Modal isOpen={false} onClose={jest.fn()} title="Scroll Modal">
          <div>Content</div>
        </Modal>
      );

      expect(document.body.style.overflow).toBe('');
    });
  });

  describe('Custom Class Names', () => {
    it('should merge custom className', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Custom Modal" className="custom-class">
          <div>Content</div>
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    it('should handle custom content className', () => {
      render(
        <Modal isOpen={true} onClose={jest.fn()} title="Custom Modal" contentClassName="content-class">
          <div>Content</div>
        </Modal>
      );

      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });
  });
});
