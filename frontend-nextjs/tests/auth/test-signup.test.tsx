import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRouter } from 'next/router';
import { signIn, getSession } from 'next-auth/react';
import SignUp from '@/pages/auth/signup';

// Mock next/router
jest.mock('next/router', () => ({
  useRouter: jest.fn(),
}));

// Mock next-auth/react
jest.mock('next-auth/react', () => ({
  signIn: jest.fn(),
  getSession: jest.fn(),
}));

// Mock useToast
jest.mock('@/components/ui/use-toast', () => ({
  useToast: jest.fn(() => ({
    toast: jest.fn(),
  })),
}));

describe('SignUp Component', () => {
  const mockPush = jest.fn();
  const mockToast = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      pathname: '/auth/signup',
    });
    (getSession as jest.Mock).mockResolvedValue(null);
    (signIn as jest.Mock).mockResolvedValue({ ok: true, error: null });
  });

  describe('Component Import/Export', () => {
    it('should import and render SignUp component', () => {
      render(<SignUp />);
      expect(screen.getByRole('heading', { name: /create account/i })).toBeInTheDocument();
    });

    it('should export SignUp as default', () => {
      expect(SignUp).toBeDefined();
    });
  });

  describe('Props Interface', () => {
    it('should render without props', () => {
      const { container } = render(<SignUp />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('should have proper form structure', () => {
      const { container } = render(<SignUp />);
      const form = container.querySelector('form');
      expect(form).toBeInTheDocument();
    });
  });

  describe('Form Elements', () => {
    beforeEach(() => {
      render(<SignUp />);
    });

    it('should render name input field', () => {
      const nameInput = screen.getByLabelText(/full name/i);
      expect(nameInput).toBeInTheDocument();
      expect(nameInput).toHaveAttribute('type', 'text');
      expect(nameInput).toHaveAttribute('required');
    });

    it('should render email input field', () => {
      const emailInput = screen.getByLabelText(/email/i);
      expect(emailInput).toBeInTheDocument();
      expect(emailInput).toHaveAttribute('type', 'email');
      expect(emailInput).toHaveAttribute('required');
    });

    it('should render password input field', () => {
      const passwordInput = screen.getByLabelText(/^password$/i);
      expect(passwordInput).toBeInTheDocument();
      expect(passwordInput).toHaveAttribute('type', 'password');
      expect(passwordInput).toHaveAttribute('required');
    });

    it('should render confirm password input field', () => {
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      expect(confirmPasswordInput).toBeInTheDocument();
      expect(confirmPasswordInput).toHaveAttribute('type', 'password');
      expect(confirmPasswordInput).toHaveAttribute('required');
    });

    it('should render submit button', () => {
      const submitButton = screen.getByRole('button', { name: /create account/i });
      expect(submitButton).toBeInTheDocument();
      expect(submitButton).toHaveAttribute('type', 'submit');
    });

    it('should render sign in link', () => {
      const signInLink = screen.getByRole('link', { name: /sign in/i });
      expect(signInLink).toBeInTheDocument();
      expect(signInLink).toHaveAttribute('href', '/auth/signin');
    });

    it('should show password requirement hint', () => {
      expect(screen.getByText(/must be at least 6 characters/i)).toBeInTheDocument();
    });
  });

  describe('State Management', () => {
    it('should update name state on input change', async () => {
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      await userEvent.type(nameInput, 'John Doe');
      expect(nameInput).toHaveValue('John Doe');
    });

    it('should update email state on input change', async () => {
      render(<SignUp />);
      const emailInput = screen.getByLabelText(/email/i);
      await userEvent.type(emailInput, 'test@example.com');
      expect(emailInput).toHaveValue('test@example.com');
    });

    it('should update password state on input change', async () => {
      render(<SignUp />);
      const passwordInput = screen.getByLabelText(/^password$/i);
      await userEvent.type(passwordInput, 'password123');
      expect(passwordInput).toHaveValue('password123');
    });

    it('should update confirm password state on input change', async () => {
      render(<SignUp />);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      await userEvent.type(confirmPasswordInput, 'password123');
      expect(confirmPasswordInput).toHaveValue('password123');
    });

    it('should show loading state during submission', async () => {
      (signIn as jest.Mock).mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ ok: true }), 100)));
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      await userEvent.type(confirmPasswordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(submitButton).toHaveTextContent(/creating account/i);
        expect(submitButton).toBeDisabled();
      });
    });
  });

  describe('Form Validation', () => {
    it('should show error when passwords do not match', async () => {
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      await userEvent.type(confirmPasswordInput, 'differentpassword');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
      });
    });

    it('should show error when password is too short', async () => {
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, '12345');
      await userEvent.type(confirmPasswordInput, '12345');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/password must be at least 6 characters/i)).toBeInTheDocument();
      });
    });

    it('should clear error state when user fixes validation', async () => {
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      // Submit with mismatched passwords
      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      await userEvent.type(confirmPasswordInput, 'different');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
      });

      // Fix the mismatch
      await userEvent.clear(confirmPasswordInput);
      await userEvent.type(confirmPasswordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText(/passwords do not match/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Navigation and Routing', () => {
    it('should redirect to home if session exists', async () => {
      (getSession as jest.Mock).mockResolvedValue({ user: { email: 'test@example.com' } });
      render(<SignUp />);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/');
      });
    });

    it('should redirect to home on successful registration', async () => {
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      await userEvent.type(confirmPasswordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/');
      });
    });

    it('should redirect to signin page if user already exists', async () => {
      (signIn as jest.Mock).mockResolvedValue({ error: 'User already exists', ok: false });
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'existing@example.com');
      await userEvent.type(passwordInput, 'password123');
      await userEvent.type(confirmPasswordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/auth/signin');
      });
    });

    it('should navigate to signin page when link clicked', () => {
      render(<SignUp />);
      const signInLink = screen.getByRole('link', { name: /sign in/i });
      expect(signInLink).toHaveAttribute('href', '/auth/signin');
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for form inputs', () => {
      render(<SignUp />);
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    });

    it('should have proper ARIA attributes', () => {
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);

      expect(nameInput).toHaveAttribute('id', 'name');
      expect(emailInput).toHaveAttribute('id', 'email');
      expect(passwordInput).toHaveAttribute('id', 'password');
      expect(confirmPasswordInput).toHaveAttribute('id', 'confirmPassword');
    });

    it('should show error with proper Alert component', async () => {
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      await userEvent.type(confirmPasswordInput, 'different');
      fireEvent.click(submitButton);

      await waitFor(() => {
        const alert = screen.getByRole('alert');
        expect(alert).toBeInTheDocument();
        expect(alert).toHaveTextContent(/passwords do not match/i);
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty form submission', async () => {
      render(<SignUp />);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      fireEvent.click(submitButton);

      // HTML5 validation should prevent submission
      expect(screen.getByLabelText(/full name/i)).toBeInvalid();
      expect(screen.getByLabelText(/email/i)).toBeInvalid();
      expect(screen.getByLabelText(/^password$/i)).toBeInvalid();
      expect(screen.getByLabelText(/confirm password/i)).toBeInvalid();
    });

    it('should handle network errors gracefully', async () => {
      (signIn as jest.Mock).mockRejectedValue(new Error('Network error'));
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      await userEvent.type(confirmPasswordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/an unexpected error occurred/i)).toBeInTheDocument();
      });
    });

    it('should handle special characters in name', async () => {
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);

      await userEvent.type(nameInput, "John O'Brien Jr.");
      expect(nameInput).toHaveValue("John O'Brien Jr.");
    });

    it('should handle long passwords', async () => {
      render(<SignUp />);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const longPassword = 'a'.repeat(100);

      await userEvent.type(passwordInput, longPassword);
      await userEvent.type(confirmPasswordInput, longPassword);

      expect(passwordInput).toHaveValue(longPassword);
      expect(confirmPasswordInput).toHaveValue(longPassword);
    });

    it('should clear error state on new submission', async () => {
      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      // First attempt - mismatched passwords
      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      await userEvent.type(confirmPasswordInput, 'different');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
      });

      // Fix and resubmit
      await userEvent.clear(confirmPasswordInput);
      await userEvent.type(confirmPasswordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText(/passwords do not match/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Toast Notifications', () => {
    it('should show success toast on account creation', async () => {
      const toastMock = jest.fn();
      (require('@/components/ui/use-toast').useToast as jest.Mock).mockReturnValue({
        toast: toastMock,
      });

      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      await userEvent.type(confirmPasswordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(toastMock).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'Welcome to ATOM!',
          })
        );
      });
    });

    it('should show toast when redirecting to signin', async () => {
      const toastMock = jest.fn();
      (require('@/components/ui/use-toast').useToast as jest.Mock).mockReturnValue({
        toast: toastMock,
      });
      (signIn as jest.Mock).mockResolvedValue({ error: 'User exists', ok: false });

      render(<SignUp />);
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password$/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /create account/i });

      await userEvent.type(nameInput, 'John Doe');
      await userEvent.type(emailInput, 'existing@example.com');
      await userEvent.type(passwordInput, 'password123');
      await userEvent.type(confirmPasswordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(toastMock).toHaveBeenCalledWith(
          expect.objectContaining({
            title: 'Account created successfully!',
          })
        );
      });
    });
  });
});
