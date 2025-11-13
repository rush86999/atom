import React, { Component, ErrorInfo, ReactNode } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, RefreshCw, Home, Bug, Send } from 'lucide-react';
import { useAppStore } from '../store';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  enableReporting?: boolean;
  reportTo?: string; // URL for error reporting
  context?: Record<string, any>; // Additional context for error reporting
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
  errorId?: string;
  retryCount: number;
}

export class ErrorBoundary extends Component<Props, State> {
  private errorId: string;

  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, retryCount: 0 };
    this.errorId = `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, retryCount: 0 };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const errorId = `error-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    this.setState({ errorInfo, errorId });

    // Enhanced error logging with context
    const errorContext = {
      errorId,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      userId: 'anonymous', // Would be set from auth context
      componentStack: errorInfo.componentStack,
      context: this.props.context || {},
      retryCount: this.state.retryCount,
    };

    console.error('ErrorBoundary caught an error:', {
      error: error.toString(),
      stack: error.stack,
      ...errorContext
    });

    // Report error if enabled
    if (this.props.enableReporting) {
      this.reportError(error, errorInfo, errorContext);
    }

    // Call custom error handler if provided
    this.props.onError?.(error, errorInfo);
  }

  private async reportError(error: Error, errorInfo: ErrorInfo, context: any) {
    try {
      const reportData = {
        error: {
          message: error.message,
          stack: error.stack,
          name: error.name,
        },
        errorInfo: {
          componentStack: errorInfo.componentStack,
        },
        context,
        severity: this.determineSeverity(error),
      };

      if (this.props.reportTo) {
        await fetch(this.props.reportTo, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(reportData),
        });
      } else {
        // Fallback: store in localStorage for debugging
        const existingReports = JSON.parse(localStorage.getItem('errorReports') || '[]');
        existingReports.push(reportData);
        localStorage.setItem('errorReports', JSON.stringify(existingReports.slice(-10))); // Keep last 10
      }
    } catch (reportError) {
      console.error('Failed to report error:', reportError);
    }
  }

  private determineSeverity(error: Error): 'low' | 'medium' | 'high' | 'critical' {
    if (error.message.includes('Network') || error.message.includes('fetch')) {
      return 'medium';
    }
    if (error.name === 'TypeError' || error.name === 'ReferenceError') {
      return 'high';
    }
    if (error.message.includes('auth') || error.message.includes('security')) {
      return 'critical';
    }
    return 'medium';
  }

  handleRetry = () => {
    this.setState(prevState => ({
      hasError: false,
      error: undefined,
      errorInfo: undefined,
      retryCount: prevState.retryCount + 1
    }));
  };

  handleReportError = () => {
    if (this.state.error && this.state.errorInfo) {
      this.reportError(this.state.error, this.state.errorInfo, {
        errorId: this.state.errorId,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
        url: window.location.href,
        userId: 'anonymous',
        componentStack: this.state.errorInfo.componentStack,
        context: this.props.context || {},
        retryCount: this.state.retryCount,
        userReported: true,
      });
    }
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 px-4"
        >
          <div className="max-w-md w-full bg-white dark:bg-gray-800 rounded-lg shadow-lg p-8 text-center">
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.2, type: 'spring', stiffness: 200 }}
            >
              <AlertTriangle className="mx-auto h-16 w-16 text-red-500 mb-4" />
            </motion.div>

            <motion.h1
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3 }}
              className="text-2xl font-bold text-gray-900 dark:text-white mb-2"
            >
              Oops! Something went wrong
            </motion.h1>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.4 }}
              className="text-gray-600 dark:text-gray-400 mb-6"
            >
              We encountered an unexpected error. Please try refreshing the page or go back to the home page.
            </motion.p>

            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="flex flex-col sm:flex-row gap-3 justify-center"
            >
              <button
                onClick={this.handleRetry}
                className="flex items-center justify-center px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Try Again
              </button>

              {this.props.enableReporting && (
                <button
                  onClick={this.handleReportError}
                  className="flex items-center justify-center px-4 py-2 bg-orange-500 text-white rounded-md hover:bg-orange-600 transition-colors"
                >
                  <Send className="w-4 h-4 mr-2" />
                  Report Error
                </button>
              )}

              <button
                onClick={this.handleGoHome}
                className="flex items-center justify-center px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600 transition-colors"
              >
                <Home className="w-4 h-4 mr-2" />
                Go Home
              </button>
            </motion.div>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <motion.details
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
                className="mt-6 text-left"
              >
                <summary className="cursor-pointer text-sm text-gray-500 dark:text-gray-400 mb-2">
                  Error Details (Development Only)
                </summary>
                <pre className="text-xs bg-gray-100 dark:bg-gray-700 p-3 rounded overflow-auto max-h-40">
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </motion.details>
            )}
          </div>
        </motion.div>
      );
    }

    return this.props.children;
  }
}

// Hook for handling async errors in functional components
export const useErrorHandler = () => {
  return React.useCallback((error: Error, errorInfo?: { componentStack?: string }) => {
    console.error('Async error caught:', error, errorInfo);

    // In a real app, send to error reporting service
    // You could also trigger a global error state here
  }, []);
};

// Higher-order component for wrapping components with error boundary
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<Props, 'children'>
) {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`;

  return WrappedComponent;
}

// Specialized error boundaries for different contexts
export const ViewErrorBoundary: React.FC<{ children: ReactNode; viewName: string }> = ({
  children,
  viewName
}) => (
  <ErrorBoundary
    fallback={
      <div className="p-8 text-center">
        <AlertTriangle className="mx-auto h-12 w-12 text-yellow-500 mb-4" />
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
          {viewName} View Error
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          There was a problem loading the {viewName.toLowerCase()} view.
        </p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
        >
          Reload Page
        </button>
      </div>
    }
  >
    {children}
  </ErrorBoundary>
);

export const WidgetErrorBoundary: React.FC<{ children: ReactNode; widgetName: string }> = ({
  children,
  widgetName
}) => (
  <ErrorBoundary
    fallback={
      <div className="p-4 border border-red-200 dark:border-red-800 rounded-md bg-red-50 dark:bg-red-900/10">
        <div className="flex items-center space-x-2">
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <span className="text-sm text-red-700 dark:text-red-400">
            Error in {widgetName} widget
          </span>
        </div>
      </div>
    }
  >
    {children}
  </ErrorBoundary>
);
