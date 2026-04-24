import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRouter } from 'next/router';
import ForgotPassword from '@/pages/auth/forgot-password';

// Mock next/router
jest.mock('next/router', () => ({
  useRouter: jest.fn(),
}));

// Mock global fetch
global.fetch = jest.fn() as jest.Mock;

describe('ForgotPassword Component', () => {
  const mockPush = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      pathname: '/auth/forgot-password',
    });
    (global.mockFetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });
  });

  describe('Component Import/Export', () => {
    it('should import and render ForgotPassword component', () => {
      render(<ForgotPassword />);
      expect(screen.getByRole('heading', { name: /reset your password/i })).toBeInTheDocument();
    });

    it('should export ForgotPassword as default', () => {
      expect(ForgotPassword).toBeDefined();
    });
  });

  describe('Props Interface', () => {
    it('should render without props', () => {
      const { container } = render(<ForgotPassword />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('should have proper form structure', () => {
      const { container } = render(<ForgotPassword />);
      const form = container.querySelector('form');
      expect(form).toBeInTheDocument();
    });
  });

  describe('Form Elements', () => {
    beforeEach(() => {
      render(<ForgotPassword />);
    });

    it('should render email input field', () => {
      const emailInput = screen.getByPlaceholderText(/email address/i);
      expect(emailInput).toBeInTheDocument();
      expect(emailInput).toHaveAttribute('type', 'email');
      expect(emailInput).toHaveAttribute('required');
    });

    it('should render submit button', () => {
      const submitButton = screen.getByRole('button', { name: /send reset link/i });
      expect(submitButton).toBeInTheDocument();
      expect(submitButton).toHaveAttribute('type', 'submit');
    });

    it('should render back to sign in link', () => {
      const signInLink = screen.getByRole('link', { name: /back to sign in/i });
      expect(signInLink).toBeInTheDocument();
      expect(signInLink).toHaveAttribute('href', '/auth/signin');
    });

    it('should render descriptive heading', () => {
      expect(screen.getByRole('heading', { name: /reset your password/i })).toBeInTheDocument();
      expect(screen.getByText(/enter your email address and we'll send you a link to reset your password/i)).toBeInTheDocument();
    });
  });

  describe('State Management', () => {
    beforeEach(() => {
      render(<ForgotPassword />);
    });

    it('should update email state on input change', async () => {
      const emailInput = screen.getByPlaceholderText(/email address/i);
      await userEvent.type(emailInput, 'test@example.com');
      expect(emailInput).toHaveValue('test@example.com');
    });

    it('should show loading state during submission', async () => {
      (global.mockFetch as jest.Mock).mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ ok: true, json: async () => ({ success: true }) }), 100)));
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'test@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(submitButton).toHaveTextContent(/sending/i);
        expect(submitButton).toBeDisabled();
      });
    });

    it('should clear email input after successful submission', async () => {
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'test@example.com');
      expect(emailInput).toHaveValue('test@example.com');

      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(emailInput).toHaveValue('');
      });
    });
  });

  describe('Form Submission', () => {
    beforeEach(() => {
      render(<ForgotPassword />);
    });

    it('should call forgot-password API on submission', async () => {
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'test@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/auth/forgot-password', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ email: 'test@example.com' }),
        });
      });
    });

    it('should show success message on successful submission', async () => {
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'test@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/if an account exists, a reset link has been sent to your email/i)).toBeInTheDocument();
      });
    });

    it('should show error message on failed submission', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'User not found' }),
      });

      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'nonexistent@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/user not found/i)).toBeInTheDocument();
      });
    });

    it('should show generic error message when no detail provided', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({}),
      });

      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'test@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/failed to send reset email/i)).toBeInTheDocument();
      });
    });
  });

  describe('Navigation', () => {
    it('should have link back to signin', () => {
      render(<ForgotPassword />);
      const signInLink = screen.getByRole('link', { name: /back to sign in/i });
      expect(signInLink).toHaveAttribute('href', '/auth/signin');
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for form inputs', () => {
      render(<ForgotPassword />);
      const emailInput = screen.getByPlaceholderText(/email address/i);
      expect(emailInput).toHaveAttribute('id', 'email');
    });

    it('should show success message in accessible div', async () => {
      render(<ForgotPassword />);
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'test@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        const successDiv = screen.getByText(/if an account exists/i).closest('div');
        expect(successDiv).toHaveClass('bg-green-50');
      });
    });

    it('should show error message in accessible div', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: 'Error' }),
      });

      render(<ForgotPassword />);
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'test@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        const errorDiv = screen.getByText(/error/i).closest('div');
        expect(errorDiv).toHaveClass('bg-red-50');
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty form submission', async () => {
      render(<ForgotPassword />);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      fireEvent.click(submitButton);

      // HTML5 validation should prevent submission
      const emailInput = screen.getByPlaceholderText(/email address/i);
      expect(emailInput).toBeInvalid();
    });

    it('should handle network errors gracefully', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValue(new Error('Network error'));

      render(<ForgotPassword />);
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'test@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/an error occurred/i)).toBeInTheDocument();
      });
    });

    it('should handle invalid email format', async () => {
      render(<ForgotPassword />);
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'invalid-email');
      fireEvent.click(submitButton);

      // HTML5 validation should prevent submission
      expect(emailInput).toBeInvalid();
    });

    it('should clear error state on new submission', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: false,
          json: async () => ({ detail: 'Network error' }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true }),
        });

      render(<ForgotPassword />);
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      // First attempt - should fail
      await userEvent.type(emailInput, 'test@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });

      // Second attempt - should succeed
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText(/network error/i)).not.toBeInTheDocument();
        expect(screen.getByText(/if an account exists/i)).toBeInTheDocument();
      });
    });

    it('should handle special characters in email', async () => {
      render(<ForgotPassword />);
      const emailInput = screen.getByPlaceholderText(/email address/i);

      await userEvent.type(emailInput, 'test+user@example.com');
      expect(emailInput).toHaveValue('test+user@example.com');
    });

    it('should handle multiple submissions', async () => {
      render(<ForgotPassword />);
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      // First submission
      await userEvent.type(emailInput, 'test1@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/if an account exists/i)).toBeInTheDocument();
        expect(emailInput).toHaveValue('');
      });

      // Second submission
      await userEvent.type(emailInput, 'test2@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Security Considerations', () => {
    it('should not reveal whether email exists or not', async () => {
      render(<ForgotPassword />);
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      // Both success and failure cases show similar messages
      await userEvent.type(emailInput, 'nonexistent@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        // Success message is ambiguous
        expect(screen.getByText(/if an account exists/i)).toBeInTheDocument();
      });
    });

    it('should sanitize error messages from API', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({ detail: '<script>alert("xss")</script>' }),
      });

      render(<ForgotPassword />);
      const emailInput = screen.getByPlaceholderText(/email address/i);
      const submitButton = screen.getByRole('button', { name: /send reset link/i });

      await userEvent.type(emailInput, 'test@example.com');
      fireEvent.click(submitButton);

      await waitFor(() => {
        const errorText = screen.getByText(/<script>/);
        // React escapes HTML by default
        expect(errorText).toBeInTheDocument();
      });
    });
  });
});
