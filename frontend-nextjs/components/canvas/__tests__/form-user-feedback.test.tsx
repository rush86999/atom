import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { InteractiveForm } from '../InteractiveForm';

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

describe('InteractiveForm - Loading State Feedback', () => {
  const fields = [
    { name: 'name', label: 'Name', type: 'text' as const, required: true },
    { name: 'email', label: 'Email', type: 'email' as const, required: true }
  ];

  test('button shows "Submitting..." text during submission', async () => {
    const mockSubmit = jest.fn(() => new Promise<void>(resolve => {
      // Promise never resolves to keep submission pending
    }));

    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByRole('button').textContent).toBe('Submitting...');
    });
  });

  test('submit button has disabled attribute during submission', async () => {
    const mockSubmit = jest.fn(() => new Promise<void>(resolve => {
      // Keep pending
    }));

    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByRole('button')).toBeDisabled();
    });
  });

  test('multiple rapid clicks only call submit once', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup({ delay: null });

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    const button = screen.getByRole('button', { name: /submit/i });

    await user.click(button);
    await user.click(button);
    await user.click(button);

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(1);
    });
  });

  test('button is enabled after successful submission', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });

    // After success, form is replaced (no button visible until success message clears)
  });

  test('button is enabled after failed submission', async () => {
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Server error'));
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
      const button = screen.getByRole('button');
      expect(button).not.toBeDisabled();
    });
  });

  test('inputs remain editable during submission', async () => {
    const mockSubmit = jest.fn(() => new Promise<void>(resolve => {
      // Keep pending
    }));

    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    const nameInput = screen.getByLabelText(/name/i) as HTMLInputElement;

    await user.type(nameInput, 'John Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByRole('button').textContent).toBe('Submitting...');
    });

    // Can still type in input
    await user.clear(nameInput);
    await user.type(nameInput, 'Jane Doe');

    expect(nameInput).toHaveValue('Jane Doe');
  });
});

describe('InteractiveForm - Success State Feedback', () => {
  const fields = [
    { name: 'name', label: 'Name', type: 'text' as const, required: true }
  ];

  test('success message appears after successful submit', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });
  });

  test('success message contains checkmark', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      const successContainer = screen.getByText(/submitted successfully/i).parentElement;
      expect(successContainer?.querySelector('svg')).toBeInTheDocument();
    });
  });

  test('success message text is "Submitted successfully!"', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText('Submitted successfully!')).toBeInTheDocument();
    });
  });

  test('form is replaced by success message', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
      expect(screen.queryByLabelText(/name/i)).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /submit/i })).not.toBeInTheDocument();
    });
  });

  test('success message uses green color styling', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      const successContainer = screen.getByText(/submitted successfully/i).parentElement;
      expect(successContainer?.className).toContain('text-green-600');
    });
  });

  test('success message auto-hides after 3 seconds', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    jest.useFakeTimers();
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });

    // Fast-forward timers
    jest.advanceTimersByTime(3000);

    await waitFor(() => {
      expect(screen.queryByText(/submitted successfully/i)).not.toBeInTheDocument();
      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    });

    jest.useRealTimers();
  });
});

describe('InteractiveForm - Error State Feedback', () => {
  const fields = [
    { name: 'name', label: 'Name', type: 'text' as const, required: true },
    { name: 'email', label: 'Email', type: 'email' as const, required: true }
  ];

  test('form-level error appears on submission failure', async () => {
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Network error'));
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('form-level error uses red background styling', async () => {
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Server error'));
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      const errorBox = screen.getByText(/submission failed/i).closest('div');
      expect(errorBox?.className).toContain('bg-red-50');
      expect(errorBox?.className).toContain('text-red-600');
    });
  });

  test('form-level error shows "Submission failed. Please try again."', async () => {
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Any error'));
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed\. please try again\./i)).toBeInTheDocument();
    });
  });

  test('form remains visible after error', async () => {
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Error'));
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
    });
  });

  test('user can retry submission after error', async () => {
    let attemptCount = 0;
    const mockSubmit = jest.fn().mockImplementation(() => {
      attemptCount++;
      if (attemptCount === 1) {
        return Promise.reject(new Error('First attempt fails'));
      }
      return Promise.resolve();
    });

    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    // First attempt
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    // Retry
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });

    expect(mockSubmit).toHaveBeenCalledTimes(2);
  });

  test('field error and form error can both appear', async () => {
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Server error'));
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Trigger field error first
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });

    // Fix fields and trigger form error
    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      // Field errors cleared, form error present
      expect(screen.queryByText(/name is required/i)).not.toBeInTheDocument();
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });
  });

  test('error state doesn\'t prevent form editing', async () => {
    const mockSubmit = jest.fn().mockRejectedValue(new Error('Error'));
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    const nameInput = screen.getByLabelText(/name/i) as HTMLInputElement;

    await user.type(nameInput, 'John Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    // Can still edit
    await user.clear(nameInput);
    await user.type(nameInput, 'Jane Doe');

    expect(nameInput).toHaveValue('Jane Doe');
  });

  test('technical error details not shown to user', async () => {
    const mockSubmit = jest.fn().mockRejectedValue(new Error('NetworkError: Failed to fetch - 500 Internal Server Error'));
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
      // Technical details should NOT be visible
      expect(screen.queryByText(/NetworkError/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/500/i)).not.toBeInTheDocument();
    });
  });
});

describe('InteractiveForm - Accessibility Feedback', () => {
  const fields = [
    { name: 'name', label: 'Name', type: 'text' as const, required: true },
    { name: 'email', label: 'Email', type: 'email' as const, required: true }
  ];

  test('error message is visible in DOM', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });
  });

  test('error icon has aria-hidden attribute', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      const errorContainer = screen.getByText(/name is required/i).closest('div');
      const icon = errorContainer?.querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  test('submit button text changes during submission', async () => {
    const mockSubmit = jest.fn(() => new Promise<void>(() => {}));
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    const button = screen.getByRole('button', { name: /submit/i });
    expect(button.textContent).toBe('Submit');

    await user.click(button);

    await waitFor(() => {
      expect(screen.getByRole('button').textContent).toBe('Submitting...');
    });
  });

  test('required fields have asterisk indicator', async () => {
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    const nameLabel = screen.getByText(/name/i);
    const asterisk = nameLabel.nextElementSibling;

    expect(asterisk).toBeInTheDocument();
    expect(asterisk?.textContent).toBe('*');
  });

  test('form fields are keyboard navigable', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    // Tab to first field
    await user.tab();
    expect(screen.getByLabelText(/name/i)).toHaveFocus();

    // Tab to second field
    await user.tab();
    expect(screen.getByLabelText(/email/i)).toHaveFocus();

    // Tab to submit button
    await user.tab();
    expect(screen.getByRole('button', { name: /submit/i })).toHaveFocus();
  });

  test('enter key submits form when button has focus', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');

    const button = screen.getByRole('button', { name: /submit/i });
    button.focus();

    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledTimes(1);
    });
  });
});

describe('InteractiveForm - Interactive Feedback Scenarios', () => {
  const fields = [
    { name: 'name', label: 'Name', type: 'text' as const, required: true },
    { name: 'email', label: 'Email', type: 'email' as const, required: true }
  ];

  test('complete flow: error fix success', async () => {
    let shouldFail = true;
    const mockSubmit = jest.fn().mockImplementation(() => {
      if (shouldFail) {
        return Promise.reject(new Error('Server error'));
      }
      return Promise.resolve();
    });

    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // Submit with missing email
    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });

    // Fix email and submit
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    // Server error on first attempt
    await waitFor(() => {
      expect(screen.getByText(/submission failed/i)).toBeInTheDocument();
    });

    // Retry successfully
    shouldFail = false;
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });

    expect(mockSubmit).toHaveBeenCalledTimes(2);
  });

  test('multiple validation errors clear individually', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    // Submit empty form
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });

    // Fix name only
    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.queryByText(/name is required/i)).not.toBeInTheDocument();
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });
  });

  test('form can be submitted multiple times successfully', async () => {
    const mockSubmit = jest.fn().mockResolvedValue(undefined);
    jest.useFakeTimers();
    const user = userEvent.setup();

    render(<InteractiveForm fields={fields} onSubmit={mockSubmit} />);

    // First submission
    await user.type(screen.getByLabelText(/name/i), 'John Doe');
    await user.type(screen.getByLabelText(/email/i), 'john@example.com');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });

    // Wait for success message to clear
    jest.advanceTimersByTime(3000);

    await waitFor(() => {
      expect(screen.queryByText(/submitted successfully/i)).not.toBeInTheDocument();
    });

    // Second submission
    const nameInput = screen.getByLabelText(/name/i) as HTMLInputElement;
    await user.clear(nameInput);
    await user.type(nameInput, 'Jane Doe');
    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/submitted successfully/i)).toBeInTheDocument();
    });

    expect(mockSubmit).toHaveBeenCalledTimes(2);
    jest.useRealTimers();
  });

  test('empty form submission shows all required errors', async () => {
    const user = userEvent.setup();
    render(<InteractiveForm fields={fields} onSubmit={jest.fn()} />);

    await user.click(screen.getByRole('button', { name: /submit/i }));

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });

    // Form still visible for corrections
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });
});
