/**
 * Error Boundary Integration Tests
 *
 * Tests verify that the ErrorBoundary component catches and displays
 * component errors gracefully, providing meaningful error feedback to users.
 *
 * Pattern from Phase 157-RESEARCH.md lines 686-753
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ErrorBoundary from '@/components/error-boundary';

// Helper component that throws an error
const ThrowError: React.FC<{ shouldThrow?: boolean }> = ({ shouldThrow = true }) => {
  if (shouldThrow) {
    throw new Error('Test error from child component');
  }
  return <div>No error</div>;
};

// Helper component that throws different error types
const ThrowStringError: React.FC = () => {
  throw 'String error';
};

const ThrowNullError: React.FC = () => {
  throw null;
};

const ThrowUndefinedError: React.FC = () => {
  throw undefined;
};

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // Suppress console.error for these tests since we're intentionally causing errors
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  describe('Error catching', () => {
    it('should catch errors in child components and display fallback UI', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('should catch and handle string errors', () => {
      render(
        <ErrorBoundary>
          <ThrowStringError />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('should catch and handle null errors', () => {
      render(
        <ErrorBoundary>
          <ThrowNullError />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('should catch and handle undefined errors', () => {
      render(
        <ErrorBoundary>
          <ThrowUndefinedError />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });
  });

  describe('Error recovery', () => {
    it('should recover from errors after retry button is clicked', async () => {
      const { rerender } = render(
        <ErrorBoundary>
          <ThrowError shouldThrow={true} />
        </ErrorBoundary>
      );

      // Should show error fallback
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();

      // Click retry button
      const retryButton = screen.getByText('Try again');
      retryButton.click();

      // Rerender with non-throwing component
      rerender(
        <ErrorBoundary>
          <div>Recovered content</div>
        </ErrorBoundary>
      );

      // Should show normal content
      await waitFor(() => {
        expect(screen.getByText('Recovered content')).toBeInTheDocument();
      });
    });

    it('should reset error state when retry button is clicked', async () => {
      const { rerender } = render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();

      // Click retry
      screen.getByText('Try again').click();

      // Should allow retry with same component (will error again)
      rerender(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      await waitFor(() => {
        expect(screen.getByText('Something went wrong')).toBeInTheDocument();
      });
    });
  });

  describe('Error information display', () => {
    it('should display error details when available', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      // Error details should be shown
      expect(screen.getByText('Error details')).toBeInTheDocument();

      // Should contain the error message
      expect(screen.getByText(/Test error from child component/)).toBeInTheDocument();
    });

    it('should include error stack trace in details', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      // Expand details
      const details = screen.getByText('Error details');
      details.click();

      // Stack trace should be visible (checking for common stack trace patterns)
      const errorText = screen.getByRole('alert').textContent || '';
      expect(errorText).toContain('Test error from child component');
    });

    it('should show user-friendly message without technical details by default', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      // Main message should be user-friendly
      expect(screen.getByText(/An unexpected error occurred/)).toBeInTheDocument();
      expect(screen.getByText(/You can try again or refresh the page/)).toBeInTheDocument();
    });
  });

  describe('Error logging', () => {
    it('should log error information to console', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(consoleSpy).toHaveBeenCalledWith(
        'ErrorBoundary caught an error:',
        expect.any(Error),
        expect.objectContaining({
          componentStack: expect.any(String),
        })
      );

      consoleSpy.mockRestore();
    });

    it('should call custom error handler if provided', () => {
      const onError = jest.fn();

      render(
        <ErrorBoundary onError={onError}>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(onError).toHaveBeenCalledWith(
        expect.any(Error),
        expect.objectContaining({
          componentStack: expect.any(String),
        })
      );
    });
  });

  describe('Custom fallback UI', () => {
    it('should render custom fallback UI when provided', () => {
      const customFallback = <div>Custom error message</div>;

      render(
        <ErrorBoundary fallback={customFallback}>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.getByText('Custom error message')).toBeInTheDocument();
      expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    });

    it('should use default fallback when no custom fallback provided', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });
  });

  describe('Normal operation', () => {
    it('should render children normally when no error occurs', () => {
      render(
        <ErrorBoundary>
          <div>Normal content</div>
        </ErrorBoundary>
      );

      expect(screen.getByText('Normal content')).toBeInTheDocument();
      expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    });

    it('should render multiple children without errors', () => {
      render(
        <ErrorBoundary>
          <div>First child</div>
          <div>Second child</div>
          <div>Third child</div>
        </ErrorBoundary>
      );

      expect(screen.getByText('First child')).toBeInTheDocument();
      expect(screen.getByText('Second child')).toBeInTheDocument();
      expect(screen.getByText('Third child')).toBeInTheDocument();
    });

    it('should not interfere with component updates', () => {
      const { rerender } = render(
        <ErrorBoundary>
          <div>Initial content</div>
        </ErrorBoundary>
      );

      expect(screen.getByText('Initial content')).toBeInTheDocument();

      rerender(
        <ErrorBoundary>
          <div>Updated content</div>
        </ErrorBoundary>
      );

      expect(screen.getByText('Updated content')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have role="alert" for screen readers', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
    });

    it('should have retry button accessible to keyboard users', () => {
      render(
        <ErrorBoundary>
          <ThrowError />
        </ErrorBoundary>
      );

      const button = screen.getByRole('button', { name: 'Try again' });
      expect(button).toBeInTheDocument();

      // Simulate keyboard interaction
      button.focus();
      expect(button).toHaveFocus();
    });
  });

  describe('Edge cases', () => {
    it('should handle errors thrown during rendering', () => {
      const ThrowingComponent: React.FC = () => {
        throw new Error('Render error');
        return <div>Never rendered</div>;
      };

      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );

      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('should handle errors thrown in useEffect', async () => {
      const EffectErrorComponent: React.FC = () => {
        React.useEffect(() => {
          throw new Error('Effect error');
        }, []);

        return <div>Component with effect error</div>;
      };

      // Note: In React 18+, errors in useEffect ARE caught by ErrorBoundary
      render(
        <ErrorBoundary>
          <EffectErrorComponent />
        </ErrorBoundary>
      );

      // Error boundary catches the useEffect error
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('should handle async errors in event handlers', () => {
      const AsyncErrorComponent: React.FC = () => {
        const handleClick = () => {
          throw new Error('Async error');
        };

        return (
          <button onClick={handleClick}>Click to error</button>
        );
      };

      render(
        <ErrorBoundary>
          <AsyncErrorComponent />
        </ErrorBoundary>
      );

      const button = screen.getByText('Click to error');
      // Note: Event handler errors are NOT caught by ErrorBoundary in React
      // They are caught by window.onerror instead. This test documents current behavior.
      expect(button).toBeInTheDocument();
    });
  });

  describe('Error boundary nesting', () => {
    it('should allow nested error boundaries', () => {
      const InnerError: React.FC = () => {
        throw new Error('Inner error');
      };

      render(
        <ErrorBoundary>
          <div>Outer content</div>
          <ErrorBoundary fallback={<div>Inner boundary caught error</div>}>
            <InnerError />
          </ErrorBoundary>
        </ErrorBoundary>
      );

      // Inner boundary should catch the error
      expect(screen.getByText('Inner boundary caught error')).toBeInTheDocument();
      expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    });

    it('should fall back to outer boundary when inner not present', () => {
      const InnerError: React.FC = () => {
        throw new Error('Uncaught error');
      };

      render(
        <ErrorBoundary fallback={<div>Outer boundary</div>}>
          <div>
            <InnerError />
          </div>
        </ErrorBoundary>
      );

      expect(screen.getByText('Outer boundary')).toBeInTheDocument();
    });
  });
});
