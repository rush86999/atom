import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useRouter } from 'next/router';
import ResetPassword from '@/pages/auth/reset-password';

// Mock next/router
jest.mock('next/router', () => ({
  useRouter: jest.fn(),
}));

// Mock global fetch
global.fetch = jest.fn() as jest.Mock;

describe('ResetPassword Component', () => {
  const mockPush = jest.fn();
  const mockToken = 'valid-reset-token-123';

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      query: { token: mockToken },
      pathname: '/auth/reset-password',
    });
    global.fetch = jest.fn().mockImplementation(async (url) => ({
      ok: true,
      json: async () => url === '/api/auth/verify-token'
        ? { valid: true }
        : { success: true, verification: { status: 'verified', effect: 'committed' } },
    })) as jest.Mock;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Component Import/Export', () => {
    it('should import and render ResetPassword component', () => {
      render(<ResetPassword />);
      expect(screen.getByText(/verifying reset link/i)).toBeInTheDocument();
    });

    it('should export ResetPassword as default', () => {
      expect(ResetPassword).toBeDefined();
    });
  });

  describe('Token Verification', () => {
    it('should show loading state while verifying token', () => {
      render(<ResetPassword />);
      expect(screen.getByText(/verifying reset link/i)).toBeInTheDocument();
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('should show reset form after successful token verification', async () => {
      render(<ResetPassword />);

      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });
    });

    it('should show invalid link message when token is invalid', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ valid: false }),
      });

      render(<ResetPassword />);

      await waitFor(() => {
        expect(screen.getByText(/invalid reset link/i)).toBeInTheDocument();
        expect(screen.getByText(/this password reset link is invalid or has expired/i)).toBeInTheDocument();
      });
    });

    it('should show invalid link message when verification fails', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

      render(<ResetPassword />);

      await waitFor(() => {
        expect(screen.getByText(/invalid reset link/i)).toBeInTheDocument();
      });
    });

    it('should call verify-token API on mount', async () => {
      render(<ResetPassword />);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/auth/verify-token', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ token: mockToken }),
        });
      });
    });
  });

  describe('Form Elements', () => {
    beforeEach(async () => {
      render(<ResetPassword />);
      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });
    });

    it('should render password input field', () => {
      const passwordInput = screen.getByPlaceholderText(/new password/i);
      expect(passwordInput).toBeInTheDocument();
      expect(passwordInput).toHaveAttribute('type', 'password');
      expect(passwordInput).toHaveAttribute('required');
    });

    it('should render confirm password input field', () => {
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      expect(confirmPasswordInput).toBeInTheDocument();
      expect(confirmPasswordInput).toHaveAttribute('type', 'password');
      expect(confirmPasswordInput).toHaveAttribute('required');
    });

    it('should render submit button', () => {
      const submitButton = screen.getByRole('button', { name: /reset password/i });
      expect(submitButton).toBeInTheDocument();
      expect(submitButton).toHaveAttribute('type', 'submit');
    });

    it('should render back to sign in link', () => {
      const signInLink = screen.getByRole('link', { name: /back to sign in/i });
      expect(signInLink).toBeInTheDocument();
      expect(signInLink).toHaveAttribute('href', '/auth/signin');
    });
  });

  describe('State Management', () => {
    beforeEach(async () => {
      render(<ResetPassword />);
      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });
    });

    it('should update password state on input change', async () => {
      const passwordInput = screen.getByPlaceholderText(/new password/i);
      await userEvent.type(passwordInput, 'newPassword123');
      expect(passwordInput).toHaveValue('newPassword123');
    });

    it('should update confirm password state on input change', async () => {
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      await userEvent.type(confirmPasswordInput, 'newPassword123');
      expect(confirmPasswordInput).toHaveValue('newPassword123');
    });

    it('should show loading state during submission', async () => {
      (global.fetch as jest.Mock).mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ ok: true, json: async () => ({ success: true }) }), 100)));
      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /reset password/i });

      await userEvent.type(passwordInput, 'newPassword123');
      await userEvent.type(confirmPasswordInput, 'newPassword123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(submitButton).toHaveTextContent(/resetting/i);
        expect(submitButton).toBeDisabled();
      });
    });
  });

  describe('Form Validation', () => {
    beforeEach(async () => {
      render(<ResetPassword />);
      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });
    });

    it('should show error when passwords do not match', async () => {
      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /reset password/i });

      await userEvent.type(passwordInput, 'newPassword123');
      await userEvent.type(confirmPasswordInput, 'differentPassword');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
      });
    });

    it('should show error when password is too short', async () => {
      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /reset password/i });

      await userEvent.type(passwordInput, 'short');
      await userEvent.type(confirmPasswordInput, 'short');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/password must be at least 8 characters/i)).toBeInTheDocument();
      });
    });
  });

  describe('Password Reset Flow', () => {
    beforeEach(async () => {
      render(<ResetPassword />);
      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });
    });

    it('should call reset-password API on successful submission', async () => {
      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /reset password/i });

      await userEvent.type(passwordInput, 'newPassword123');
      await userEvent.type(confirmPasswordInput, 'newPassword123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/auth/reset-password', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            token: mockToken,
            password: 'newPassword123',
          }),
        });
      });
    });

    it('should show success message on successful reset', async () => {
      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /reset password/i });

      await userEvent.type(passwordInput, 'newPassword123');
      await userEvent.type(confirmPasswordInput, 'newPassword123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/password reset successful/i)).toBeInTheDocument();
      });
    });

    it('should redirect to signin after successful reset', async () => {
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
      jest.useFakeTimers();
      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /reset password/i });

      await user.type(passwordInput, 'newPassword123');
      await user.type(confirmPasswordInput, 'newPassword123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/password reset successful/i)).toBeInTheDocument();
      });

      jest.advanceTimersByTime(2000);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/auth/signin');
      });
    });

    it('should show error message on failed reset', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ valid: true }),
      }).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Token expired' }),
      });

      render(<ResetPassword />);
      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });

      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /reset password/i });

      await userEvent.type(passwordInput, 'newPassword123');
      await userEvent.type(confirmPasswordInput, 'newPassword123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/token expired/i)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for form inputs', async () => {
      render(<ResetPassword />);
      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });

      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);

      expect(passwordInput).toHaveAttribute('id', 'password');
      expect(confirmPasswordInput).toHaveAttribute('id', 'confirmPassword');
    });

    it('should show error messages in accessible divs', async () => {
      render(<ResetPassword />);
      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });

      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /reset password/i });

      await userEvent.type(passwordInput, 'short');
      await userEvent.type(confirmPasswordInput, 'short');
      fireEvent.click(submitButton);

      await waitFor(() => {
        const errorDiv = screen.getByText(/password must be at least 8 characters/i).closest('div');
        expect(errorDiv).toHaveClass('bg-red-50');
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty form submission', async () => {
      render(<ResetPassword />);
      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /reset password/i });
      fireEvent.click(submitButton);

      // HTML5 validation should prevent submission
      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      expect(passwordInput).toBeInvalid();
      expect(confirmPasswordInput).toBeInvalid();
    });

    it('should handle network errors gracefully', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ valid: true }),
      }).mockRejectedValueOnce(new Error('Network error'));

      render(<ResetPassword />);
      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });

      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /reset password/i });

      await userEvent.type(passwordInput, 'newPassword123');
      await userEvent.type(confirmPasswordInput, 'newPassword123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/an error occurred/i)).toBeInTheDocument();
      });
    });

    it('should clear error state on new submission', async () => {
      render(<ResetPassword />);
      await waitFor(() => {
        expect(screen.getByText(/set new password/i)).toBeInTheDocument();
      });

      const passwordInput = screen.getByPlaceholderText(/new password/i);
      const confirmPasswordInput = screen.getByPlaceholderText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /reset password/i });

      // First attempt - mismatched passwords
      await userEvent.type(passwordInput, 'newPassword123');
      await userEvent.type(confirmPasswordInput, 'different');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
      });

      // Fix and resubmit
      await userEvent.clear(confirmPasswordInput);
      await userEvent.type(confirmPasswordInput, 'newPassword123');
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.queryByText(/passwords do not match/i)).not.toBeInTheDocument();
      });
    });
  });
  describe('Recovery receipt finality', () => {
    it('does not show success or redirect for an unverified committed response', async () => {
      (global.fetch as jest.Mock).mockImplementation(async (url) => ({
        ok: true,
        json: async () => url === '/api/auth/verify-token' ? { valid: true } : {
          success: true, status: 'committed_unverified',
          verification: { status: 'unavailable', effect: 'committed' },
        },
      }));
      render(<ResetPassword />);
      await screen.findByPlaceholderText(/new password/i);
      await userEvent.type(screen.getByPlaceholderText(/new password/i), 'CurrentPassword1!');
      await userEvent.type(screen.getByPlaceholderText(/confirm password/i), 'CurrentPassword1!');
      fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
      await screen.findByText(/password change could not be confirmed/i);
      expect(screen.queryByText(/password reset successful/i)).not.toBeInTheDocument();
      expect(mockPush).not.toHaveBeenCalled();
    });

    it('cancels the scheduled sign-in redirect when the user leaves the page', async () => {
      jest.useFakeTimers();
      try {
        const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
        const view = render(<ResetPassword />);
        await screen.findByPlaceholderText(/new password/i);
        await user.type(screen.getByPlaceholderText(/new password/i), 'CurrentPassword1!');
        await user.type(screen.getByPlaceholderText(/confirm password/i), 'CurrentPassword1!');
        fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
        await screen.findByText(/password reset successful/i);
        view.unmount();
        jest.advanceTimersByTime(3000);
        expect(mockPush).not.toHaveBeenCalled();
      } finally {
        jest.useRealTimers();
      }
    });
  });

  describe('Request ownership across navigation', () => {
    it('ignores an older verification after a new token is rejected', async () => {
      let resolveOld: (value: unknown) => void = () => {};
      (global.fetch as jest.Mock).mockImplementation((_url, options) => {
        const value = JSON.parse(options.body).token;
        return value === mockToken ? new Promise(resolve => { resolveOld = resolve; })
          : Promise.resolve({ ok: true, json: async () => ({ valid: false }) });
      });
      const view = render(<ResetPassword />);
      (useRouter as jest.Mock).mockReturnValue({ push: mockPush, query: { token: 'new-token' } });
      view.rerender(<ResetPassword />);
      await screen.findByText(/^Invalid Reset Link$/i);
      await act(async () => resolveOld({ ok: true, json: async () => ({ valid: true }) }));
      expect(screen.getByText(/^Invalid Reset Link$/i)).toBeInTheDocument();
      expect(screen.queryByPlaceholderText(/new password/i)).not.toBeInTheDocument();
    });

    it.each(['token change', 'unmount'])('does not redirect from a delayed reset after %s', async (navigation) => {
      jest.useFakeTimers();
      let resolveReset: (value: unknown) => void = () => {};
      (global.fetch as jest.Mock).mockImplementation((url) => url === '/api/auth/verify-token'
        ? Promise.resolve({ ok: true, json: async () => ({ valid: true }) })
        : new Promise(resolve => { resolveReset = resolve; }));
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
      const view = render(<ResetPassword />);
      await screen.findByPlaceholderText(/new password/i);
      await user.type(screen.getByPlaceholderText(/new password/i), 'CurrentPassword1!');
      await user.type(screen.getByPlaceholderText(/confirm password/i), 'CurrentPassword1!');
      fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
      if (navigation === 'unmount') view.unmount();
      else {
        (useRouter as jest.Mock).mockReturnValue({ push: mockPush, query: { token: 'new-token' } });
        view.rerender(<ResetPassword />);
      }
      await act(async () => resolveReset({ ok: true, json: async () => ({ success: true, verification: { status: 'verified' } }) }));
      await act(async () => { jest.advanceTimersByTime(3000); });
      expect(mockPush).not.toHaveBeenCalled();
      expect(screen.queryByText(/password reset successful/i)).not.toBeInTheDocument();
    });
  });

});
