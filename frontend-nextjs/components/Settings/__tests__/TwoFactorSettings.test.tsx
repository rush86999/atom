/**
 * Round 21 TDD bug hunt — BUG-092: backup recovery codes never display after
 * enabling 2FA.
 *
 * The backend `/api/auth/2fa/enable` endpoint returns the standard envelope:
 *   { success: true, data: { backup_codes: [...] }, message, timestamp }
 * (see `router.success_response` in core/base_routes.py). The component read
 * `data.backup_codes`, which is `undefined` in the envelope — so the user
 * enabled 2FA and never saw the recovery codes to save, risking lockout.
 *
 * TDD: the assertion below fails against the pre-fix component (no codes
 * render), then passes once `handleEnable` reads `data.data.backup_codes`.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import TwoFactorSettings from '../TwoFactorSettings';

// qrcode.react renders an <svg>; stub it to keep the DOM minimal in jsdom.
jest.mock('qrcode.react', () => ({
  QRCodeSVG: () => <svg data-testid="qr" />,
}));

// toast renders portal DOM; stub it so it doesn't interfere with queries.
jest.mock('react-hot-toast', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

const backupCodes = ['AAAA-BBBB-CCCC-DDDD', '1111-2222-3333-4444'];

// The REAL envelope shape returned by POST /api/auth/2fa/enable.
const enableEnvelope = {
  success: true,
  data: { backup_codes: backupCodes },
  message: '2FA enabled successfully',
  timestamp: '2026-08-06T00:00:00Z',
};

describe('TwoFactorSettings', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes('/2fa/status')) {
        return Promise.resolve({ ok: true, json: async () => ({ enabled: false }) });
      }
      if (u.includes('/2fa/setup')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ secret: 'SECRET123', otpauth_url: 'otpauth://totp/test?secret=SECRET123' }),
        });
      }
      if (u.includes('/2fa/enable')) {
        return Promise.resolve({ ok: true, json: async () => enableEnvelope });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
  });

  it('renders the 2FA status card', async () => {
    render(<TwoFactorSettings />);
    await waitFor(() => {
      expect(screen.getByText(/Two-Factor Authentication/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Add an extra layer of security/)).toBeInTheDocument();
  });

  it('starts setup and shows the verification form', async () => {
    render(<TwoFactorSettings />);
    const enableBtn = await screen.findByRole('button', { name: /Enable 2FA/ });
    fireEvent.click(enableBtn);

    await screen.findByText(/Setup Two-Factor Authentication/);
    expect(screen.getByTestId('qr')).toBeInTheDocument();
    expect(screen.getByLabelText(/Verification Code/)).toBeInTheDocument();
  });

  it('displays the backup recovery codes after enabling 2FA (BUG-092)', async () => {
    render(<TwoFactorSettings />);
    const enableBtn = await screen.findByRole('button', { name: /Enable 2FA/ });
    fireEvent.click(enableBtn);

    const codeInput = await screen.findByLabelText(/Verification Code/);
    fireEvent.change(codeInput, { target: { value: '123456' } });

    const submitBtn = screen.getByRole('button', { name: /^Enable 2FA/ });
    fireEvent.click(submitBtn);

    // The recovery codes from the /enable envelope MUST be shown so the user
    // can save them. Pre-fix this fails because data.backup_codes is undefined.
    await waitFor(() => {
      expect(screen.getByText('AAAA-BBBB-CCCC-DDDD')).toBeInTheDocument();
    });
    expect(screen.getByText('1111-2222-3333-4444')).toBeInTheDocument();
  });

  it('disables 2FA after confirming the code', async () => {
    render(<TwoFactorSettings />);
    // First, render the enabled state: status returns enabled=true.
    global.fetch = jest.fn().mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url);
      if (u.includes('/2fa/status')) {
        return Promise.resolve({ ok: true, json: async () => ({ enabled: true }) });
      }
      if (u.includes('/2fa/disable')) {
        return Promise.resolve({ ok: true, json: async () => ({ success: true }) });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    });
    const promptSpy = jest.spyOn(window, 'prompt').mockReturnValue('123456');

    render(<TwoFactorSettings />);
    const disableBtn = await screen.findByRole('button', { name: /Disable/ });
    fireEvent.click(disableBtn);

    await waitFor(() => {
      expect(screen.getByText(/Add an extra layer of security/)).toBeInTheDocument();
    });
    promptSpy.mockRestore();
  });
});
