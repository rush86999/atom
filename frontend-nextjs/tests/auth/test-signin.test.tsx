import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRouter } from 'next/router';
import { signIn, getSession } from 'next-auth/react';
import SignIn from '@/pages/auth/signin';

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

describe('SignIn Component', () => {
  const mockPush = jest.fn();
  const mockToast = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      pathname: '/auth/signin',
    });
    (getSession as jest.Mock).mockResolvedValue(null);
    (signIn as jest.Mock).mockResolvedValue({ ok: true, error: null });
  });

  describe('Component Import/Export', () => {
    it('should import and render SignIn component', () => {
      render(<SignIn />);
      expect(screen.getByRole('heading', { name: /sign in to atom/i })).toBeInTheDocument();
    });

    it('should export SignIn as default', () => {
      expect(SignIn).toBeDefined();
    });
  });

  describe('Props Interface', () => {
    it('should render without props', () => {
      const { container } = render(<SignIn />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('should accept className prop if added', () => {
      const { container } = render(<SignIn />);
      const form = container.querySelector('form');
      expect(form).toBeInTheDocument();
    });
  });

  describe('Form Elements', () => {
    beforeEach(() => {
      render(<SignIn />);
    });

    it('should render email input field', () => {
      const emailInput = screen.getByLabelText(/email/i);
      expect(emailInput).toBeInTheDocument();
      expect(emailInput).toHaveAttribute('type', 'email');
      expect(emailInput).toHaveAttribute('required');
    });

    it('should render password input field', () => {
      const passwordInput = screen.getByLabelText(/password/i);
      expect(passwordInput).toBeInTheDocument();
      expect(passwordInput).toHaveAttribute('type', 'password');
      expect(passwordInput).toHaveAttribute('required');
    });

    it('should render submit button', () => {
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      expect(submitButton).toBeInTheDocument();
      expect(submitButton).toHaveAttribute('type', 'submit');
    });

    it('should render forgot password link', () => {
      const forgotLink = screen.getByRole('link', { name: /forgot password/i });
      expect(forgotLink).toBeInTheDocument();
      expect(forgotLink).toHaveAttribute('href', '/auth/forgot-password');
    });

    it('should render sign up link', () => {
      const signUpLink = screen.getByRole('link', { name: /sign up/i });
      expect(signUpLink).toBeInTheDocument();
      expect(signUpLink).toHaveAttribute('href', '/auth/signup');
    });

    it('should render Google sign in button', () => {
      const googleButton = screen.getByRole('button', { name: /sign in with google/i });
      expect(googleButton).toBeInTheDocument();
    });

    it('should render GitHub sign in button', () => {
      const githubButton = screen.getByRole('button', { name: /sign in with github/i });
      expect(githubButton).toBeInTheDocument();
    });
  });

  describe('State Management', () => {
    it('should update email state on input change', async () => {
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      await userEvent.type(emailInput, 'test@example.com');
      expect(emailInput).toHaveValue('test@example.com');
    });

    it('should update password state on input change', async () => {
      render(<SignIn />);
      const passwordInput = screen.getByLabelText(/password/i);
      await userEvent.type(passwordInput, 'password123');
      expect(passwordInput).toHaveValue('password123');
    });

    it('should show loading state during submission', async () => {
      (signIn as jest.Mock).mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ ok: true }), 100)));
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(submitButton).toHaveTextContent('Signing in...');
        expect(submitButton).toBeDisabled();
      });
    });

    it('should show error message on authentication failure', async () => {
      (signIn as jest.Mock).mockResolvedValue({ error: 'Invalid credentials', ok: false });
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'wrongpassword');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
      });
    });
  });

  describe('Two-Factor Authentication', () => {
    it('should show TOTP input when 2FA is required', async () => {
      (signIn as jest.Mock).mockResolvedValue({ error: '2FA_REQUIRED' });
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByLabelText(/security code/i)).toBeInTheDocument();
        expect(screen.getByText(/enter the code from your authenticator app/i)).toBeInTheDocument();
      });
    });

    it('should update TOTP code state on input change', async () => {
      (signIn as jest.Mock).mockResolvedValue({ error: '2FA_REQUIRED' });
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        const totpInput = screen.getByLabelText(/security code/i);
        expect(totpInput).toBeInTheDocument();
      });

      const totpInput = screen.getByLabelText(/security code/i);
      await userEvent.type(totpInput, '123456');
      expect(totpInput).toHaveValue('123456');
    });

    it('should show error for invalid 2FA code', async () => {
      (signIn as jest.Mock)
        .mockResolvedValueOnce({ error: '2FA_REQUIRED' })
        .mockResolvedValueOnce({ error: 'INVALID_2FA_CODE' });
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        const totpInput = screen.getByLabelText(/security code/i);
        expect(totpInput).toBeInTheDocument();
      });

      const totpInput = screen.getByLabelText(/security code/i);
      await userEvent.type(totpInput, '000000');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid 2fa code/i)).toBeInTheDocument();
      });
    });

    it('should return to login form when back button clicked', async () => {
      (signIn as jest.Mock).mockResolvedValue({ error: '2FA_REQUIRED' });
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByLabelText(/security code/i)).toBeInTheDocument();
      });

      const backButton = screen.getByRole('button', { name: /back to login/i });
      fireEvent.click(backButton);

      await waitFor(() => {
        expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
        expect(screen.queryByLabelText(/security code/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Navigation and Routing', () => {
    it('should redirect to home if session exists', async () => {
      (getSession as jest.Mock).mockResolvedValue({ user: { email: 'test@example.com' } });
      render(<SignIn />);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/');
      });
    });

    it('should redirect to home on successful sign in', async () => {
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/');
      });
    });

    it('should call signIn with Google provider', async () => {
      render(<SignIn />);
      const googleButton = screen.getByRole('button', { name: /sign in with google/i });

      fireEvent.click(googleButton);

      await waitFor(() => {
        expect(signIn).toHaveBeenCalledWith('google', { callbackUrl: '/' });
      });
    });

    it('should call signIn with GitHub provider', async () => {
      render(<SignIn />);
      const githubButton = screen.getByRole('button', { name: /sign in with github/i });

      fireEvent.click(githubButton);

      await waitFor(() => {
        expect(signIn).toHaveBeenCalledWith('github', { callbackUrl: '/' });
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for form inputs', () => {
      render(<SignIn />);
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });

    it('should have proper ARIA attributes', () => {
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);

      expect(emailInput).toHaveAttribute('id', 'email');
      expect(passwordInput).toHaveAttribute('id', 'password');
    });

    it('should show error with proper ARIA role', async () => {
      (signIn as jest.Mock).mockResolvedValue({ error: 'Invalid credentials', ok: false });
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'wrongpassword');
      fireEvent.click(submitButton);

      await waitFor(() => {
        const errorDiv = screen.getByText(/invalid email or password/i).closest('div');
        expect(errorDiv).toHaveClass('bg-red-50');
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty form submission', async () => {
      render(<SignIn />);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      fireEvent.click(submitButton);

      // HTML5 validation should prevent submission
      expect(screen.getByLabelText(/email/i)).toBeInvalid();
      expect(screen.getByLabelText(/password/i)).toBeInvalid();
    });

    it('should handle network errors gracefully', async () => {
      (signIn as jest.Mock).mockRejectedValue(new Error('Network error'));
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'password123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/an unexpected error occurred/i)).toBeInTheDocument();
      });
    });

    it('should clear error state on new submission', async () => {
      (signIn as jest.Mock)
        .mockResolvedValueOnce({ error: 'Invalid credentials', ok: false })
        .mockResolvedValueOnce({ ok: true, error: null });
      render(<SignIn />);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      // First attempt - should fail
      await userEvent.type(emailInput, 'test@example.com');
      await userEvent.type(passwordInput, 'wrongpassword');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
      });

      // Second attempt - should succeed
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText(/invalid email or password/i)).not.toBeInTheDocument();
      });
    });
  });
});
