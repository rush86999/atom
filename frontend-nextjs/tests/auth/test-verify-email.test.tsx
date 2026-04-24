import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRouter } from 'next/router';
import VerifyEmailPage from '@/pages/auth/verify-email';

// Mock next/router
jest.mock('next/router', () => ({
  useRouter: jest.fn(),
}));

// Mock global fetch
global.fetch = jest.fn() as jest.Mock;

// Mock window.alert
global.alert = jest.fn() as jest.Mock;

describe('VerifyEmailPage Component', () => {
  const mockPush = jest.fn();
  const testEmail = 'test@example.com';

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      query: { email: testEmail },
      pathname: '/auth/verify-email',
    });
    (global.mockFetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });
  });

  describe('Component Import/Export', () => {
    it('should import and render VerifyEmailPage component', () => {
      render(<VerifyEmailPage />);
      expect(screen.getByRole('heading', { name: /verify your email/i })).toBeInTheDocument();
    });

    it('should export VerifyEmailPage as default', () => {
      expect(VerifyEmailPage).toBeDefined();
    });
  });

  describe('Props Interface', () => {
    it('should render without props', () => {
      const { container } = render(<VerifyEmailPage />);
      expect(container.firstChild).toBeInTheDocument();
    });

    it('should accept email from router query', () => {
      render(<VerifyEmailPage />);
      expect(screen.getByText(testEmail)).toBeInTheDocument();
    });
  });

  describe('Form Elements', () => {
    beforeEach(() => {
      render(<VerifyEmailPage />);
    });

    it('should render verification code input field', () => {
      const codeInput = screen.getByLabelText(/verification code/i);
      expect(codeInput).toBeInTheDocument();
      expect(codeInput).toHaveAttribute('type', 'text');
      expect(codeInput).toHaveAttribute('required');
      expect(codeInput).toHaveAttribute('maxlength', '6');
    });

    it('should render verify button', () => {
      const verifyButton = screen.getByRole('button', { name: /verify email/i });
      expect(verifyButton).toBeInTheDocument();
      expect(verifyButton).toHaveAttribute('type', 'submit');
    });

    it('should render resend button', () => {
      const resendButton = screen.getByRole('button', { name: /resend verification email/i });
      expect(resendButton).toBeInTheDocument();
    });

    it('should render back to sign in link', () => {
      const signInLink = screen.getByRole('link', { name: /back to sign in/i });
      expect(signInLink).toBeInTheDocument();
      expect(signInLink).toHaveAttribute('href', '/auth/signin');
    });

    it('should display email in description', () => {
      expect(screen.getByText(testEmail)).toBeInTheDocument();
    });
  });

  describe('State Management', () => {
    beforeEach(() => {
      render(<VerifyEmailPage />);
    });

    it('should update verification code state on input change', async () => {
      const codeInput = screen.getByLabelText(/verification code/i);
      await userEvent.type(codeInput, '123456');
      expect(codeInput).toHaveValue('123456');
    });

    it('should only accept digits in verification code', async () => {
      const codeInput = screen.getByLabelText(/verification code/i);
      await userEvent.type(codeInput, 'abc123def456');
      // Should only keep digits and limit to 6 characters
      expect(codeInput).toHaveValue('123456');
    });

    it('should limit verification code to 6 characters', async () => {
      const codeInput = screen.getByLabelText(/verification code/i);
      await userEvent.type(codeInput, '123456789');
      expect(codeInput).toHaveValue('123456');
    });

    it('should show loading state during verification', async () => {
      (global.mockFetch as jest.Mock).mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ ok: true, json: async () => ({ success: true }) }), 100)));
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '123456');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        expect(verifyButton).toHaveTextContent(/verifying/i);
        expect(verifyButton).toBeDisabled();
      });
    });

    it('should show loading state during resend', async () => {
      (global.mockFetch as jest.Mock).mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ ok: true, json: async () => ({ success: true }) }), 100)));
      const resendButton = screen.getByRole('button', { name: /resend verification email/i });

      fireEvent.click(resendButton);

      await waitFor(() => {
        expect(resendButton).toHaveTextContent(/sending/i);
        expect(resendButton).toBeDisabled();
      });
    });

    it('should disable verify button when code is not 6 digits', () => {
      render(<VerifyEmailPage />);
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      expect(verifyButton).toBeDisabled();

      fireEvent.change(codeInput, { target: { value: '123' } });
      expect(verifyButton).toBeDisabled();
    });

    it('should enable verify button when code is 6 digits', async () => {
      render(<VerifyEmailPage />);
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '123456');
      expect(verifyButton).not.toBeDisabled();
    });
  });

  describe('Email Verification Flow', () => {
    beforeEach(() => {
      render(<VerifyEmailPage />);
    });

    it('should call verify-email API on submission', async () => {
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '123456');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/auth/verify-email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: testEmail,
            code: '123456',
          }),
        });
      });
    });

    it('should show success screen on successful verification', async () => {
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '123456');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        expect(screen.getByText(/email verified/i)).toBeInTheDocument();
        expect(screen.getByText(/redirecting to sign in/i)).toBeInTheDocument();
      });
    });

    it('should redirect to signin after successful verification', async () => {
      jest.useFakeTimers();
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '123456');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        expect(screen.getByText(/email verified/i)).toBeInTheDocument();
      });

      jest.advanceTimersByTime(2000);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/auth/signin?verified=true');
      });

      jest.useRealTimers();
    });

    it('should show error message on failed verification', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({ error: 'Invalid code' }),
      });

      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '000000');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid code/i)).toBeInTheDocument();
      });
    });

    it('should show generic error when no error message provided', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({}),
      });

      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '000000');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        expect(screen.getByText(/verification failed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Resend Email Flow', () => {
    beforeEach(() => {
      render(<VerifyEmailPage />);
    });

    it('should call send-verification-email API on resend', async () => {
      const resendButton = screen.getByRole('button', { name: /resend verification email/i });

      fireEvent.click(resendButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/auth/send-verification-email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: testEmail }),
        });
      });
    });

    it('should show alert on successful resend', async () => {
      const resendButton = screen.getByRole('button', { name: /resend verification email/i });

      fireEvent.click(resendButton);

      await waitFor(() => {
        expect(global.alert).toHaveBeenCalledWith('Verification email sent! Please check your inbox.');
      });
    });

    it('should show error on failed resend', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({ error: 'Rate limit exceeded' }),
      });

      const resendButton = screen.getByRole('button', { name: /resend verification email/i });

      fireEvent.click(resendButton);

      await waitFor(() => {
        expect(screen.getByText(/rate limit exceeded/i)).toBeInTheDocument();
      });
    });

    it('should show error when email is missing', () => {
      (useRouter as jest.Mock).mockReturnValue({
        push: mockPush,
        query: {},
        pathname: '/auth/verify-email',
      });

      render(<VerifyEmailPage />);
      const resendButton = screen.getByRole('button', { name: /resend verification email/i });

      fireEvent.click(resendButton);

      expect(screen.getByText(/email address is required/i)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for form inputs', () => {
      render(<VerifyEmailPage />);
      expect(screen.getByLabelText(/verification code/i)).toBeInTheDocument();
    });

    it('should have proper ARIA attributes', () => {
      render(<VerifyEmailPage />);
      const codeInput = screen.getByLabelText(/verification code/i);
      expect(codeInput).toHaveAttribute('id', 'code');
    });

    it('should show error in Alert component', async () => {
      (global.mockFetch as jest.Mock).mockResolvedValue({
        ok: false,
        json: async () => ({ error: 'Invalid code' }),
      });

      render(<VerifyEmailPage />);
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '000000');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        const alert = screen.getByRole('alert');
        expect(alert).toBeInTheDocument();
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty verification code submission', async () => {
      render(<VerifyEmailPage />);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      expect(verifyButton).toBeDisabled();
    });

    it('should handle network errors gracefully', async () => {
      (global.mockFetch as jest.Mock).mockRejectedValue(new Error('Network error'));

      render(<VerifyEmailPage />);
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '123456');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        expect(screen.getByText(/verification failed/i)).toBeInTheDocument();
      });
    });

    it('should clear error state on new submission', async () => {
      (global.mockFetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: false,
          json: async () => ({ error: 'Invalid code' }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ success: true }),
        });

      render(<VerifyEmailPage />);
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      // First attempt - should fail
      await userEvent.type(codeInput, '000000');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid code/i)).toBeInTheDocument();
      });

      // Second attempt - should succeed
      await userEvent.clear(codeInput);
      await userEvent.type(codeInput, '123456');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        expect(screen.queryByText(/invalid code/i)).not.toBeInTheDocument();
        expect(screen.getByText(/email verified/i)).toBeInTheDocument();
      });
    });

    it('should handle missing email gracefully', () => {
      (useRouter as jest.Mock).mockReturnValue({
        push: mockPush,
        query: {},
        pathname: '/auth/verify-email',
      });

      render(<VerifyEmailPage />);
      expect(screen.getByText(/your email/i)).toBeInTheDocument();
    });

    it('should handle special characters in email', () => {
      (useRouter as jest.Mock).mockReturnValue({
        push: mockPush,
        query: { email: 'test+user@example.com' },
        pathname: '/auth/verify-email',
      });

      render(<VerifyEmailPage />);
      expect(screen.getByText('test+user@example.com')).toBeInTheDocument();
    });
  });

  describe('Success Screen', () => {
    it('should show success icon', async () => {
      render(<VerifyEmailPage />);
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '123456');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        expect(screen.getByText(/email verified/i)).toBeInTheDocument();
        // Check for CheckCircle2 icon presence
        const successIcon = document.querySelector('svg[class*="text-green-500"]');
        expect(successIcon).toBeInTheDocument();
      });
    });

    it('should show loading spinner on success screen', async () => {
      render(<VerifyEmailPage />);
      const codeInput = screen.getByLabelText(/verification code/i);
      const verifyButton = screen.getByRole('button', { name: /verify email/i });

      await userEvent.type(codeInput, '123456');
      fireEvent.click(verifyButton);

      await waitFor(() => {
        // Check for Loader2 icon presence
        const spinner = document.querySelector('svg[class*="animate-spin"]');
        expect(spinner).toBeInTheDocument();
      });
    });
  });
});
