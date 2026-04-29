import React from 'react';
import { renderWithProviders, screen } from '../../../tests/test-utils';
import { Badge } from '@/components/ui/badge';

describe('Badge Component', () => {
  describe('Rendering', () => {
    it('renders default badge', () => {
      renderWithProviders(<Badge>New</Badge>);
      const badge = screen.getByText('New');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveClass('bg-primary');
    });

    it('renders secondary variant', () => {
      renderWithProviders(<Badge variant="secondary">Draft</Badge>);
      const badge = screen.getByText('Draft');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveClass('bg-secondary');
    });

    it('renders destructive variant', () => {
      renderWithProviders(<Badge variant="destructive">Error</Badge>);
      const badge = screen.getByText('Error');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveClass('bg-destructive');
    });

    it('renders outline variant', () => {
      renderWithProviders(<Badge variant="outline">Border</Badge>);
      const badge = screen.getByText('Border');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveClass('border');
    });

    it('renders success variant', () => {
      renderWithProviders(<Badge variant="success">Complete</Badge>);
      const badge = screen.getByText('Complete');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveClass('bg-green-500');
    });

    it('renders warning variant', () => {
      renderWithProviders(<Badge variant="warning">Pending</Badge>);
      const badge = screen.getByText('Pending');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveClass('bg-yellow-500');
    });

    it('renders with default classes', () => {
      renderWithProviders(<Badge>Default</Badge>);
      const badge = screen.getByText('Default');
      expect(badge).toHaveClass('inline-flex');
      expect(badge).toHaveClass('items-center');
      expect(badge).toHaveClass('rounded-full');
      expect(badge).toHaveClass('px-2.5');
      expect(badge).toHaveClass('py-0.5');
      expect(badge).toHaveClass('text-xs');
      expect(badge).toHaveClass('font-semibold');
    });
  });

  describe('Content', () => {
    it('renders text content', () => {
      renderWithProviders(<Badge>Featured</Badge>);
      const badge = screen.getByText('Featured');
      expect(badge).toHaveTextContent('Featured');
    });

    it('renders with icon children', () => {
      renderWithProviders(
        <Badge>
          <span data-testid="icon">★</span>
          Starred
        </Badge>
      );
      const badge = screen.getByText('Starred');
      const icon = screen.getByTestId('icon');
      expect(badge).toContainElement(icon);
      expect(badge).toHaveTextContent('Starred');
    });

    it('renders with numeric values', () => {
      renderWithProviders(<Badge>99+</Badge>);
      const badge = screen.getByText('99+');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent('99+');
    });

    it('renders with single digit', () => {
      renderWithProviders(<Badge>3</Badge>);
      const badge = screen.getByText('3');
      expect(badge).toBeInTheDocument();
    });

    it('renders with large notification count', () => {
      renderWithProviders(<Badge>999</Badge>);
      const badge = screen.getByText('999');
      expect(badge).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies correct variant colors', () => {
      const { rerender } = renderWithProviders(<Badge variant="default">Default</Badge>);
      expect(screen.getByText('Default')).toHaveClass('bg-primary');

      rerender(<Badge variant="secondary">Secondary</Badge>);
      expect(screen.getByText('Secondary')).toHaveClass('bg-secondary');

      rerender(<Badge variant="destructive">Destructive</Badge>);
      expect(screen.getByText('Destructive')).toHaveClass('bg-destructive');

      rerender(<Badge variant="success">Success</Badge>);
      expect(screen.getByText('Success')).toHaveClass('bg-green-500');

      rerender(<Badge variant="warning">Warning</Badge>);
      expect(screen.getByText('Warning')).toHaveClass('bg-yellow-500');
    });

    it('handles custom className', () => {
      renderWithProviders(<Badge className="custom-class">Custom</Badge>);
      const badge = screen.getByText('Custom');
      expect(badge).toHaveClass('custom-class');
    });

    it('merges custom className with default classes', () => {
      renderWithProviders(<Badge className="custom-class">Test</Badge>);
      const badge = screen.getByText('Test');
      expect(badge).toHaveClass('custom-class');
      expect(badge).toHaveClass('rounded-full');
    });

    it('applies hover styles via variant', () => {
      renderWithProviders(<Badge variant="default">Hover me</Badge>);
      const badge = screen.getByText('Hover me');
      expect(badge).toHaveClass('hover:bg-primary/80');
    });
  });

  describe('Accessibility', () => {
    it('has accessible text content', () => {
      renderWithProviders(<Badge>Live</Badge>);
      const badge = screen.getByText('Live');
      expect(badge).toBeInTheDocument();
    });

    it('forwards aria-hidden attribute', () => {
      renderWithProviders(<Badge aria-hidden="true">3</Badge>);
      const badge = screen.getByText('3');
      expect(badge).toHaveAttribute('aria-hidden', 'true');
    });

    it('forwards role attribute', () => {
      renderWithProviders(<Badge role="status">Live</Badge>);
      const badge = screen.getByText('Live');
      expect(badge).toHaveAttribute('role', 'status');
    });

    it('forwards aria-label attribute', () => {
      renderWithProviders(<Badge aria-label="3 notifications">3</Badge>);
      const badge = screen.getByText('3');
      expect(badge).toHaveAttribute('aria-label', '3 notifications');
    });

    it('forwards aria-live attribute', () => {
      renderWithProviders(<Badge aria-live="polite">Updating</Badge>);
      const badge = screen.getByText('Updating');
      expect(badge).toHaveAttribute('aria-live', 'polite');
    });

    it('communicates decorative status with aria-hidden', () => {
      renderWithProviders(<Badge aria-hidden="true">Decoration</Badge>);
      const badge = screen.getByText('Decoration');
      expect(badge).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('Edge Cases', () => {
    it('renders with long text', () => {
      const longText = 'This is a very long badge text that might wrap';
      renderWithProviders(<Badge>{longText}</Badge>);
      const badge = screen.getByText(longText);
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent(longText);
    });

    it('renders with special characters', () => {
      renderWithProviders(<Badge>Café & Restaurant</Badge>);
      const badge = screen.getByText('Café & Restaurant');
      expect(badge).toBeInTheDocument();
    });

    it('renders with emojis', () => {
      renderWithProviders(<Badge>🎉 Success</Badge>);
      const badge = screen.getByText('🎉 Success');
      expect(badge).toBeInTheDocument();
    });

    it('renders with Unicode characters', () => {
      renderWithProviders(<Badge>中文 Badge</Badge>);
      const badge = screen.getByText('中文 Badge');
      expect(badge).toBeInTheDocument();
    });

    it('renders with HTML entities', () => {
      renderWithProviders(<Badge>Badge &amp; More</Badge>);
      const badge = screen.getByText('Badge & More');
      expect(badge).toBeInTheDocument();
    });

    it('handles numeric status codes', () => {
      renderWithProviders(<Badge>200</Badge>);
      const badge = screen.getByText('200');
      expect(badge).toBeInTheDocument();
    });

    it('renders with zero value', () => {
      renderWithProviders(<Badge>0</Badge>);
      const badge = screen.getByText('0');
      expect(badge).toBeInTheDocument();
    });

    it('renders with mixed content (text + number)', () => {
      renderWithProviders(<Badge>5 unread</Badge>);
      const badge = screen.getByText('5 unread');
      expect(badge).toBeInTheDocument();
    });

    it('forwards data-* attributes', () => {
      renderWithProviders(<Badge data-testid="test-badge">Test</Badge>);
      const badge = screen.getByTestId('test-badge');
      expect(badge).toBeInTheDocument();
    });

    it('forwards id attribute', () => {
      renderWithProviders(<Badge id="badge-1">Badge</Badge>);
      const badge = screen.getByText('Badge');
      expect(badge).toHaveAttribute('id', 'badge-1');
    });
  });

  describe('Combined Props', () => {
    it('renders with variant and custom className', () => {
      renderWithProviders(<Badge variant="destructive" className="custom">Alert</Badge>);
      const badge = screen.getByText('Alert');
      expect(badge).toHaveClass('bg-destructive');
      expect(badge).toHaveClass('custom');
    });

    it('renders with all accessibility props', () => {
      renderWithProviders(
        <Badge
          role="status"
          aria-live="polite"
          aria-label="Status update"
        >
          Updated
        </Badge>
      );
      const badge = screen.getByText('Updated');
      expect(badge).toHaveAttribute('role', 'status');
      expect(badge).toHaveAttribute('aria-live', 'polite');
      expect(badge).toHaveAttribute('aria-label', 'Status update');
    });

    it('renders decorative badge with all attributes', () => {
      renderWithProviders(
        <Badge
          variant="secondary"
          aria-hidden="true"
          className="decoration"
        >
          Decor
        </Badge>
      );
      const badge = screen.getByText('Decor');
      expect(badge).toHaveClass('bg-secondary');
      expect(badge).toHaveClass('decoration');
      expect(badge).toHaveAttribute('aria-hidden', 'true');
    });

    it('renders notification badge with role and aria-label', () => {
      renderWithProviders(
        <Badge
          variant="destructive"
          role="status"
          aria-label="3 new messages"
        >
          3
        </Badge>
      );
      const badge = screen.getByText('3');
      expect(badge).toHaveClass('bg-destructive');
      expect(badge).toHaveAttribute('role', 'status');
      expect(badge).toHaveAttribute('aria-label', '3 new messages');
    });
  });

  describe('Real-world Use Cases', () => {
    it('renders status badge (active/inactive)', () => {
      const { rerender } = renderWithProviders(<Badge variant="success">Active</Badge>);
      expect(screen.getByText('Active')).toHaveClass('bg-green-500');

      rerender(<Badge variant="secondary">Inactive</Badge>);
      expect(screen.getByText('Inactive')).toHaveClass('bg-secondary');
    });

    it('renders notification count badge', () => {
      renderWithProviders(
        <Badge variant="destructive" aria-label="5 notifications">
          5
        </Badge>
      );
      const badge = screen.getByText('5');
      expect(badge).toHaveClass('bg-destructive');
    });

    it('renders version badge', () => {
      renderWithProviders(<Badge variant="outline">v2.0</Badge>);
      const badge = screen.getByText('v2.0');
      expect(badge).toHaveClass('border');
    });

    it('renders category badge', () => {
      renderWithProviders(<Badge variant="secondary">Feature</Badge>);
      const badge = screen.getByText('Feature');
      expect(badge).toHaveClass('bg-secondary');
    });

    it('renders priority badge', () => {
      const { rerender } = renderWithProviders(<Badge variant="destructive">High</Badge>);
      expect(screen.getByText('High')).toHaveClass('bg-destructive');

      rerender(<Badge variant="warning">Medium</Badge>);
      expect(screen.getByText('Medium')).toHaveClass('bg-yellow-500');

      rerender(<Badge variant="secondary">Low</Badge>);
      expect(screen.getByText('Low')).toHaveClass('bg-secondary');
    });
  });

  describe('Visual Focus', () => {
    it('has focus styles', () => {
      renderWithProviders(<Badge>Focusable</Badge>);
      const badge = screen.getByText('Focusable');
      expect(badge).toHaveClass('focus:outline-none');
      expect(badge).toHaveClass('focus:ring-2');
    });

    it('has focus offset', () => {
      renderWithProviders(<Badge>Badge</Badge>);
      const badge = screen.getByText('Badge');
      expect(badge).toHaveClass('focus:ring-offset-2');
    });
  });
});
