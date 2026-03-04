/**
 * Component-Level Error Recovery Tests
 *
 * Tests error recovery flows at the component level for key components.
 * Validates that components handle loading → error → retry → success flows correctly.
 *
 * Test Groups:
 * 1. InteractiveForm Error Recovery (3 tests)
 *
 * Phase 133-04: Component-Level Error Recovery Tests
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { server, rest } from '@/tests/mocks/server';
import { InteractiveForm } from '@/components/canvas/InteractiveForm';

// ============================================================================
// Test Setup
// ============================================================================

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock window.atom.canvas API
const mockCanvasAPI = {
  getState: jest.fn(),
  getAllStates: jest.fn(),
  subscribe: jest.fn(),
  subscribeAll: jest.fn()
};

beforeEach(() => {
  (window as any).atom = { canvas: mockCanvasAPI };
  jest.clearAllMocks();
});

afterEach(() => {
  delete (window as any).atom;
});

// ============================================================================
// Test Group 1: InteractiveForm Error Recovery
// ============================================================================

describe('InteractiveForm - Error Recovery', () => {

  test('should handle form submission failure (503) with retry', async () => {
    const user = userEvent.setup();
    let attemptCount = 0;

    // Mock onSubmit that fails first time, succeeds second
    const mockSubmit = jest.fn().mockImplementation(async () => {
      attemptCount++;

      if (attemptCount === 1) {
        throw new Error('Service Unavailable (503)');
      }

      return { success: true };
    });

    const fields = [
      { name: 'name', label: 'Name', type: 'text' as const, required: true },
      { name: 'email', label: 'Email', type: 'email' as const, required: true },
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Fill form
    await user.type(screen.getByLabelText(/name/i), 'Test User');
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');

    // Submit form (first attempt fails)
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Should show error after first failure
    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    expect(attemptCount).toBe(1);

    // Click retry button
    const retryButton = screen.getByRole('button', { name: /submit/i });
    await user.click(retryButton);

    // Should succeed on second attempt
    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });

    expect(attemptCount).toBe(2);
  });

  test('should handle governance error (403) with helpful message', async () => {
    const user = userEvent.setup();

    // Mock onSubmit that fails with governance error
    const mockSubmit = jest.fn().mockRejectedValue({
      success: false,
      error: 'Forbidden',
      error_code: 'GOVERNANCE_BLOCKED',
      details: 'Agent maturity level insufficient for this action',
      status: 403,
    });

    const fields = [
      { name: 'action', label: 'Action', type: 'text' as const, required: true },
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Fill and submit form
    await user.type(screen.getByLabelText(/action/i), 'Delete all data');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Should show governance error message
    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    // Verify retry button is still available
    expect(screen.getByRole('button', { name: /submit/i })).toBeVisible();
  });

  test('should clear error state after successful retry', async () => {
    const user = userEvent.setup();
    let shouldFail = true;

    // Mock onSubmit that fails first time, succeeds second
    const mockSubmit = jest.fn().mockImplementation(async () => {
      if (shouldFail) {
        throw new Error('Network Error');
      }
      return { success: true };
    });

    const fields = [
      { name: 'data', label: 'Data', type: 'text' as const, required: true },
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Fill and submit form
    await user.type(screen.getByLabelText(/data/i), 'test data');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Should show error
    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    // Fix mock to succeed
    shouldFail = false;

    // Retry
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Should succeed and clear error
    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
      expect(screen.queryByText(/submission failed/i)).not.toBeInTheDocument();
    });
  });
});

// ============================================================================
// Test Group 2: Loading States During Error Recovery
// ============================================================================

describe('InteractiveForm - Loading States During Error Recovery', () => {

  test('should show loading state during form submission', async () => {
    const user = userEvent.setup();

    // Mock slow submission
    const mockSubmit = jest.fn().mockImplementation(async () => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      return { success: true };
    });

    const fields = [
      { name: 'field', label: 'Field', type: 'text' as const, required: true },
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Fill form
    await user.type(screen.getByLabelText(/field/i), 'test value');

    // Submit
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Button should be disabled during submission
    await waitFor(() => {
      const submitButton = screen.getByRole('button', { name: /submitting/i });
      expect(submitButton).toBeInTheDocument();
      expect(submitButton).toBeDisabled();
    });

    // Wait for completion
    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });
  });

  test('should maintain loading state during retry after error', async () => {
    const user = userEvent.setup();
    let attemptCount = 0;

    // Mock slow submission with initial failure
    const mockSubmit = jest.fn().mockImplementation(async () => {
      attemptCount++;

      // Simulate slow response
      await new Promise(resolve => setTimeout(resolve, 500));

      if (attemptCount === 1) {
        throw new Error('Service Unavailable');
      }

      return { success: true };
    });

    const fields = [
      { name: 'value', label: 'Value', type: 'text' as const, required: true },
    ];

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Fill and submit form
    await user.type(screen.getByLabelText(/value/i), 'test');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Should show loading, then error
    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    // Retry
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Should show loading state during retry
    const submitButton = screen.getByRole('button', { name: /submitting/i });
    expect(submitButton).toBeInTheDocument();

    // Should eventually succeed
    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });
  });
});
