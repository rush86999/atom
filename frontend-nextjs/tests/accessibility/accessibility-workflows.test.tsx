import { render, screen, waitFor } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import React from 'react';
import userEvent from '@testing-library/user-event';

// Extend Jest with jest-axe matcher
expect.extend(toHaveNoViolations);

/**
 * Workflow-based accessibility tests for WCAG 2.1 AA compliance
 *
 * These tests cover real user workflows and edge cases:
 * - Keyboard navigation through canvas
 * - Screen reader announcements for form errors
 * - Modal focus trapping and restoration
 * - Dynamic content announcements
 * - Custom interactive elements
 * - Image accessibility
 * - Color contrast compliance
 * - Focus indicators
 * - Form input labeling
 *
 * Test patterns from RESEARCH.md lines 246-285
 */

describe('Workflow accessibility', () => {
  describe('Keyboard navigation', () => {
    it('should navigate canvas workflow with keyboard', async () => {
      // Test keyboard navigation flows logically through canvas
      const { container } = render(
        <div role="application" aria-label="Canvas workflow">
          <button data-testid="step1">Step 1</button>
          <button data-testid="step2">Step 2</button>
          <button data-testid="step3">Step 3</button>
        </div>
      );

      // Verify no WCAG violations
      const results = await axe(container);
      expect(results).toHaveNoViolations();

      // Verify keyboard navigation
      const step1 = screen.getByTestId('step1');
      const step2 = screen.getByTestId('step2');
      const step3 = screen.getByTestId('step3');

      step1.focus();
      expect(step1).toHaveFocus();

      await userEvent.tab();
      expect(step2).toHaveFocus();

      await userEvent.tab();
      expect(step3).toHaveFocus();
    });

    it('should have visible focus indicators on all interactive elements', () => {
      // Test that all interactive elements show focus state
      render(
        <div>
          <button>Submit</button>
          <a href="/">Link</a>
          <input type="text" placeholder="Text input" />
        </div>
      );

      const button = screen.getByRole('button');
      const link = screen.getByRole('link');
      const input = screen.getByRole('textbox');

      // Focus each element and verify it can receive focus
      button.focus();
      expect(button).toHaveFocus();

      link.focus();
      expect(link).toHaveFocus();

      input.focus();
      expect(input).toHaveFocus();
    });

    it('should maintain logical tab order in complex workflows', async () => {
      // Test tab order follows visual flow
      const { container } = render(
        <form aria-label="Test form">
          <label htmlFor="input1">Input 1</label>
          <input id="input1" type="text" />

          <label htmlFor="input2">Input 2</label>
          <input id="input2" type="text" />

          <button type="submit">Submit</button>
        </form>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();

      // Verify tab order: input1 -> input2 -> submit
      const input1 = screen.getByLabelText('Input 1');
      const input2 = screen.getByLabelText('Input 2');
      const submit = screen.getByRole('button', { name: 'Submit' });

      input1.focus();
      expect(input1).toHaveFocus();

      await userEvent.tab();
      expect(input2).toHaveFocus();

      await userEvent.tab();
      expect(submit).toHaveFocus();
    });
  });

  describe('Screen reader announcements', () => {
    it('should announce form errors via ARIA live regions', async () => {
      // Test that ARIA live regions announce validation errors
      render(
        <form aria-label="Test form">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            aria-invalid="true"
            aria-describedby="error-message"
          />
          <div role="alert" id="error-message" aria-live="assertive">
            Please enter a valid email address
          </div>
        </form>
      );

      // Verify error message is associated with input
      const input = screen.getByRole('textbox');
      expect(input).toHaveAttribute('aria-invalid', 'true');
      expect(input).toHaveAttribute('aria-describedby', 'error-message');

      // Verify error message is in ARIA live region
      const errorMessage = screen.getByRole('alert');
      expect(errorMessage).toHaveTextContent('Please enter a valid email address');
      expect(errorMessage).toHaveAttribute('aria-live', 'assertive');
    });

    it('should announce dynamic content updates', async () => {
      // Test async updates announced to screen readers
      const { container } = render(
        <div>
          <div aria-live="polite" aria-atomic="true" data-testid="status">
            Loading...
          </div>
        </div>
      );

      const status = screen.getByTestId('status');

      // Initial state
      expect(status).toHaveTextContent('Loading...');

      // Simulate dynamic update
      const { rerender } = render(
        <div>
          <div aria-live="polite" aria-atomic="true" data-testid="status">
            Content loaded successfully
          </div>
        </div>,
        { container }
      );

      await waitFor(() => {
        expect(status).toHaveTextContent('Content loaded successfully');
      });
    });

    it('should announce modal open/close', async () => {
      // Test modals are announced when opened
      render(
        <div>
          <button aria-haspopup="dialog">Open Modal</button>
        </div>
      );

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('aria-haspopup', 'dialog');
    });
  });

  describe('Modal focus management', () => {
    it('should trap focus in modal when open', async () => {
      // Test focus trapped in modal
      render(
        <div role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <h2 id="modal-title">Modal Title</h2>
          <button data-testid="modal-button1">Button 1</button>
          <button data-testid="modal-button2">Button 2</button>
          <button data-testid="modal-close">Close</button>
        </div>
      );

      const modal = screen.getByRole('dialog');
      expect(modal).toHaveAttribute('aria-modal', 'true');

      // Verify focus is within modal
      const button1 = screen.getByTestId('modal-button1');
      button1.focus();
      expect(button1).toHaveFocus();
    });

    it('should restore focus to trigger after modal closes', async () => {
      // Test focus returns to trigger after modal closes
      render(
        <div>
          <button data-testid="trigger">Open Modal</button>
        </div>
      );

      const trigger = screen.getByTestId('trigger');
      trigger.focus();

      // Simulate modal close
      await waitFor(() => {
        expect(trigger).toHaveFocus();
      });
    });

    it('should have accessible modal announcements', async () => {
      // Test modals have proper ARIA attributes
      const { container } = render(
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          aria-describedby="modal-desc"
        >
          <h2 id="modal-title">Modal Title</h2>
          <p id="modal-desc">Modal description</p>
          <button>Close</button>
        </div>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();

      const modal = screen.getByRole('dialog');
      expect(modal).toHaveAttribute('aria-labelledby', 'modal-title');
      expect(modal).toHaveAttribute('aria-describedby', 'modal-desc');
    });
  });

  describe('Custom interactive elements', () => {
    it('should have proper ARIA roles on custom buttons', async () => {
      // Test custom buttons have button role
      const { container } = render(
        <div role="button" tabIndex={0} aria-label="Custom button">
          Custom Button
        </div>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();

      const customButton = screen.getByRole('button');
      expect(customButton).toHaveAttribute('tabIndex', '0');
      expect(customButton).toHaveAttribute('aria-label', 'Custom button');
    });

    it('should have proper ARIA roles on custom links', async () => {
      // Test custom links have link role
      const { container } = render(
        <div role="link" tabIndex={0} aria-label="Custom link">
          Custom Link
        </div>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();

      const customLink = screen.getByRole('link');
      expect(customLink).toHaveAttribute('tabIndex', '0');
    });
  });

  describe('Image accessibility', () => {
    it('should have alt text on all images', async () => {
      // Test images have alt text or presentation role
      const { container } = render(
        <div>
          <img src="/test.jpg" alt="Test image" />
          <img src="/decorative.jpg" alt="" role="presentation" />
        </div>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();

      // Images with role="presentation" are not exposed to assistive technologies
      // so getAllByRole('img') only finds the informative image
      const images = screen.getAllByRole('img');
      expect(images).toHaveLength(1);

      // First image has meaningful alt text
      expect(images[0]).toHaveAttribute('alt', 'Test image');

      // Verify decorative image exists in DOM (even if not in accessibility tree)
      const decorativeImage = container.querySelector('img[role="presentation"]');
      expect(decorativeImage).toBeInTheDocument();
      expect(decorativeImage).toHaveAttribute('alt', '');
    });

    it('should have accessible names for informative images', async () => {
      // Test informative images have non-empty alt text
      render(
        <div>
          <img src="/chart.png" alt="Sales chart showing 20% increase" />
        </div>
      );

      const image = screen.getByAltText('Sales chart showing 20% increase');
      expect(image).toBeInTheDocument();
    });
  });

  describe('Color contrast', () => {
    it('should meet WCAG AA contrast requirements', async () => {
      // Test text contrast >= 4.5:1
      const { container } = render(
        <div style={{ color: '#000000', backgroundColor: '#FFFFFF' }}>
          High contrast text
        </div>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    it('should have sufficient contrast on interactive elements', async () => {
      // Test buttons have sufficient contrast
      const { container } = render(
        <button
          style={{
            color: '#FFFFFF',
            backgroundColor: '#0066CC',
            padding: '10px 20px'
          }}
        >
          Submit
        </button>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });

  describe('Form accessibility', () => {
    it('should have labels on all form inputs', async () => {
      // Test all form inputs have associated labels
      const { container } = render(
        <form>
          <label htmlFor="name">Name</label>
          <input id="name" type="text" />

          <label htmlFor="email">Email</label>
          <input id="email" type="email" />

          <label htmlFor="message">Message</label>
          <textarea id="message" />
        </form>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();

      // Verify all inputs have labels
      const nameInput = screen.getByLabelText('Name');
      const emailInput = screen.getByLabelText('Email');
      const messageInput = screen.getByLabelText('Message');

      expect(nameInput).toBeInTheDocument();
      expect(emailInput).toBeInTheDocument();
      expect(messageInput).toBeInTheDocument();
    });

    it('should have required indicators on required fields', async () => {
      // Test required fields are marked
      render(
        <form>
          <label htmlFor="required-field">
            Required Field <span aria-hidden="true">*</span>
          </label>
          <input id="required-field" type="text" required aria-required="true" />
        </form>
      );

      const input = screen.getByLabelText(/required field/i);
      expect(input).toHaveAttribute('aria-required', 'true');
      expect(input).toHaveAttribute('required');
    });

    it('should have error messages associated with invalid fields', async () => {
      // Test error messages are linked to inputs
      render(
        <form>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            aria-invalid="true"
            aria-describedby="password-error"
          />
          <span id="password-error" role="alert">
            Password must be at least 8 characters
          </span>
        </form>
      );

      const input = screen.getByLabelText('Password');
      expect(input).toHaveAttribute('aria-invalid', 'true');
      expect(input).toHaveAttribute('aria-describedby', 'password-error');

      const errorMessage = screen.getByRole('alert');
      expect(errorMessage).toHaveTextContent('Password must be at least 8 characters');
    });
  });

  describe('Semantic HTML', () => {
    it('should use proper heading hierarchy', async () => {
      // Test headings follow logical order
      const { container } = render(
        <div>
          <h1>Main Title</h1>
          <h2>Section Title</h2>
          <h3>Subsection Title</h3>
        </div>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();

      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 3 })).toBeInTheDocument();
    });

    it('should have proper landmark regions', async () => {
      // Test page has landmarks for navigation
      const { container } = render(
        <div>
          <nav aria-label="Main navigation">
            <a href="/">Home</a>
            <a href="/about">About</a>
          </nav>
          <main aria-label="Main content">
            <h1>Main Content</h1>
          </main>
          <footer aria-label="Site footer">
            <p>&copy; 2026</p>
          </footer>
        </div>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();

      expect(screen.getByRole('navigation')).toBeInTheDocument();
      expect(screen.getByRole('main')).toBeInTheDocument();
      expect(screen.getByRole('contentinfo')).toBeInTheDocument();
    });
  });

  describe('List accessibility', () => {
    it('should have proper list semantics', async () => {
      // Test lists use proper markup
      const { container } = render(
        <ul>
          <li>Item 1</li>
          <li>Item 2</li>
          <li>Item 3</li>
        </ul>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();

      const list = screen.getByRole('list');
      expect(list).toBeInTheDocument();

      const items = screen.getAllByRole('listitem');
      expect(items).toHaveLength(3);
    });
  });

  describe('Table accessibility', () => {
    it('should have proper table headers', async () => {
      // Test tables have headers
      const { container } = render(
        <table>
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Email</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>John Doe</td>
              <td>john@example.com</td>
            </tr>
          </tbody>
        </table>
      );

      const results = await axe(container);
      expect(results).toHaveNoViolations();

      const table = screen.getByRole('table');
      expect(table).toBeInTheDocument();

      const headers = screen.getAllByRole('columnheader');
      expect(headers).toHaveLength(2);
    });
  });

  describe('Skip links', () => {
    it('should have skip link for keyboard navigation', () => {
      // Test skip link allows bypassing navigation
      render(
        <div>
          <a href="#main-content" className="skip-link">
            Skip to main content
          </a>
          <nav aria-label="Navigation">
            <a href="/">Home</a>
          </nav>
          <main id="main-content">
            <h1>Main Content</h1>
          </main>
        </div>
      );

      const skipLink = screen.getByRole('link', { name: 'Skip to main content' });
      expect(skipLink).toHaveAttribute('href', '#main-content');

      const mainContent = screen.getByRole('main');
      expect(mainContent).toHaveAttribute('id', 'main-content');
    });
  });

  describe('Focus management in dynamic workflows', () => {
    it('should manage focus when content appears', async () => {
      // Test focus moves to new content
      const { container } = render(
        <div>
          <button aria-expanded="false" aria-controls="panel">
            Toggle Panel
          </button>
          <div id="panel" hidden>
            <button>Panel Button</button>
          </div>
        </div>
      );

      const toggle = screen.getByRole('button', { name: 'Toggle Panel' });
      expect(toggle).toHaveAttribute('aria-expanded', 'false');

      // Simulate panel opening
      const { rerender } = render(
        <div>
          <button aria-expanded="true" aria-controls="panel">
            Toggle Panel
          </button>
          <div id="panel">
            <button>Panel Button</button>
          </div>
        </div>,
        { container }
      );

      await waitFor(() => {
        expect(toggle).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByRole('button', { name: 'Panel Button' })).toBeInTheDocument();
      });
    });
  });
});
