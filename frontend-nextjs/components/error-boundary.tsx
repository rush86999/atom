'use client';

import React from 'react';

/**
 * Error Boundary Component
 *
 * Catches JavaScript errors anywhere in the child component tree,
 * logs those errors, and displays a fallback UI instead of crashing
 * the entire application.
 *
 * Usage:
 *   <ErrorBoundary>
 *     <YourComponent />
 *   </ErrorBoundary>
 *
 * Pattern from Phase 157-RESEARCH.md lines 686-753
 */
interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    // Log the error to console for debugging
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: undefined });
  };

  render(): React.ReactNode {
    if (this.state.hasError) {
      // Render custom fallback UI if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default fallback UI
      return (
        <div role="alert" style={styles.container}>
          <h2 style={styles.heading}>Something went wrong</h2>
          <p style={styles.message}>
            An unexpected error occurred. You can try again or refresh the page.
          </p>
          {this.state.error && (
            <details style={styles.details}>
              <summary style={styles.summary}>Error details</summary>
              <pre style={styles.errorText}>
                {this.state.error.toString()}
                {this.state.error.stack}
              </pre>
            </details>
          )}
          <button onClick={this.handleReset} style={styles.button}>
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

// Inline styles for the fallback UI
const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '2rem',
    margin: '1rem',
    border: '1px solid #f5c6c6',
    borderRadius: '0.5rem',
    backgroundColor: '#fff5f5',
    color: '#742a2a',
  },
  heading: {
    marginTop: 0,
    marginBottom: '1rem',
    fontSize: '1.5rem',
    fontWeight: 600,
  },
  message: {
    marginBottom: '1rem',
    lineHeight: 1.5,
  },
  details: {
    marginBottom: '1rem',
    padding: '0.75rem',
    backgroundColor: '#fff',
    border: '1px solid #e2e8f0',
    borderRadius: '0.25rem',
  },
  summary: {
    cursor: 'pointer',
    fontWeight: 500,
    marginBottom: '0.5rem',
  },
  errorText: {
    margin: 0,
    padding: '0.5rem',
    fontSize: '0.875rem',
    fontFamily: 'monospace',
    whiteSpace: 'pre-wrap' as const,
    wordBreak: 'break-word' as const,
  },
  button: {
    padding: '0.5rem 1rem',
    fontSize: '1rem',
    fontWeight: 500,
    color: '#fff',
    backgroundColor: '#3182ce',
    border: 'none',
    borderRadius: '0.25rem',
    cursor: 'pointer',
    transition: 'background-color 0.2s',
  },
};

export default ErrorBoundary;
