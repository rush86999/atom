/**
 * DesktopSecurityAudit Component Tests
 *
 * Verifies the real DesktopSecurityAudit (components/desktop/DesktopSecurityAudit.tsx):
 * - renders nothing outside the Tauri runtime
 * - Browse invokes open_folder_dialog and shows the selected path
 * - the scan button stays disabled until a folder is selected
 * - a clean scan renders ALL CLEAR and toasts success
 * - findings render "N RISKS DETECTED" with category/severity/description rows
 * - a failed execute_command with parseable stdout still renders risks
 * - invoke rejection toasts the scan error
 * - a non-array findings payload (object-shaped stdout) must not crash
 *   the findings render (real-bug guard)
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockToast = { success: jest.fn(), error: jest.fn(), info: jest.fn() };

jest.mock('sonner', () => ({
  toast: mockToast,
}));

// imported after the sonner mock so the factory never runs before mockToast exists
import { DesktopSecurityAudit } from '../DesktopSecurityAudit';

const getTauri = () => (window as any).__TAURI__;

describe('DesktopSecurityAudit', () => {
  beforeEach(() => {
    mockToast.success.mockClear();
    mockToast.error.mockClear();
    (window as any).__TAURI__ = {
      core: { invoke: jest.fn() },
      invoke: jest.fn(),
    };
  });

  afterEach(() => {
    delete (window as any).__TAURI__;
  });

  it('renders nothing when not running inside Tauri', () => {
    delete (window as any).__TAURI__;
    const { container } = render(<DesktopSecurityAudit />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the audit card with no folder selected and a disabled scan button', () => {
    render(<DesktopSecurityAudit />);

    expect(screen.getByText('Local Security Audit')).toBeInTheDocument();
    expect(screen.getByText('No folder selected')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /RUN SECURITY SCAN/ })).toBeDisabled();
  });

  it('selects a folder via the Tauri dialog and enables the scan', async () => {
    getTauri().core.invoke.mockResolvedValueOnce({ success: true, path: '/Users/me/code' });

    render(<DesktopSecurityAudit />);
    fireEvent.click(screen.getByRole('button', { name: /Browse/i }));

    expect(getTauri().core.invoke).toHaveBeenCalledWith('open_folder_dialog');
    expect(await screen.findByText('/Users/me/code')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /RUN SECURITY SCAN/ })).not.toBeDisabled();
  });

  it('toasts when the folder dialog fails', async () => {
    getTauri().core.invoke.mockRejectedValueOnce(new Error('dialog closed'));

    render(<DesktopSecurityAudit />);
    fireEvent.click(screen.getByRole('button', { name: /Browse/i }));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Failed to open folder dialog');
    });
    expect(screen.getByText('No folder selected')).toBeInTheDocument();
  });

  it('runs the CLI scanner and renders ALL CLEAR for an empty findings list', async () => {
    getTauri().core.invoke
      .mockResolvedValueOnce({ success: true, path: '/Users/me/code' })
      .mockResolvedValueOnce({ success: true, stdout: '[]' });

    render(<DesktopSecurityAudit />);
    fireEvent.click(screen.getByRole('button', { name: /Browse/i }));
    await screen.findByText('/Users/me/code');

    fireEvent.click(screen.getByRole('button', { name: /RUN SECURITY SCAN/ }));

    expect(await screen.findByText('ALL CLEAR')).toBeInTheDocument();
    expect(mockToast.success).toHaveBeenCalledWith('Local security audit complete.');
    expect(getTauri().core.invoke).toHaveBeenCalledWith('execute_command', {
      command: 'python3',
      args: ['-m', 'atom_security', '/Users/me/code', '--format', 'json'],
    });
  });

  it('shows the loading state on the scan button while auditing', async () => {
    getTauri().core.invoke
      .mockResolvedValueOnce({ success: true, path: '/Users/me/code' })
      .mockImplementationOnce(
        () => new Promise((resolve) => setTimeout(() => resolve({ success: true, stdout: '[]' }), 150))
      );

    render(<DesktopSecurityAudit />);
    fireEvent.click(screen.getByRole('button', { name: /Browse/i }));
    await screen.findByText('/Users/me/code');

    fireEvent.click(screen.getByRole('button', { name: /RUN SECURITY SCAN/ }));

    expect(await screen.findByText('AUDITING...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /AUDITING/ })).toBeDisabled();

    expect(await screen.findByText('ALL CLEAR')).toBeInTheDocument();
  });

  it('renders risk findings with category, severity and description', async () => {
    getTauri().core.invoke
      .mockResolvedValueOnce({ success: true, path: '/Users/me/code' })
      .mockResolvedValueOnce({
        success: true,
        stdout: JSON.stringify([
          { category: 'Hardcoded Secret', severity: 'high', description: 'API key in repo' },
          { category: 'Dependency', severity: 'medium', description: 'Outdated package' },
        ]),
      });

    render(<DesktopSecurityAudit />);
    fireEvent.click(screen.getByRole('button', { name: /Browse/i }));
    await screen.findByText('/Users/me/code');

    fireEvent.click(screen.getByRole('button', { name: /RUN SECURITY SCAN/ }));

    expect(await screen.findByText('2 RISKS DETECTED')).toBeInTheDocument();
    expect(screen.getByText('Hardcoded Secret')).toBeInTheDocument();
    expect(screen.getByText('high')).toBeInTheDocument();
    expect(screen.getByText('API key in repo')).toBeInTheDocument();
    expect(screen.getByText('Dependency')).toBeInTheDocument();
    expect(screen.getByText('Outdated package')).toBeInTheDocument();
  });

  it('parses risks from a failed execute_command when stdout is valid JSON', async () => {
    getTauri().core.invoke
      .mockResolvedValueOnce({ success: true, path: '/Users/me/code' })
      .mockResolvedValueOnce({
        success: false,
        stdout: JSON.stringify([{ category: 'Secrets', severity: 'critical', description: 'Found key' }]),
      });

    render(<DesktopSecurityAudit />);
    fireEvent.click(screen.getByRole('button', { name: /Browse/i }));
    await screen.findByText('/Users/me/code');

    fireEvent.click(screen.getByRole('button', { name: /RUN SECURITY SCAN/ }));

    expect(await screen.findByText('1 RISKS DETECTED')).toBeInTheDocument();
    expect(screen.getByText('Found key')).toBeInTheDocument();
  });

  it('toasts the scan execution error when invoke rejects', async () => {
    getTauri().core.invoke
      .mockResolvedValueOnce({ success: true, path: '/Users/me/code' })
      .mockRejectedValueOnce(new Error('python3 not found'));

    render(<DesktopSecurityAudit />);
    fireEvent.click(screen.getByRole('button', { name: /Browse/i }));
    await screen.findByText('/Users/me/code');

    fireEvent.click(screen.getByRole('button', { name: /RUN SECURITY SCAN/ }));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Scan execution error: python3 not found');
    });
    expect(screen.queryByText('ALL CLEAR')).not.toBeInTheDocument();
  });

  it('does not crash when the scanner returns an object-shaped findings payload', async () => {
    getTauri().core.invoke
      .mockResolvedValueOnce({ success: true, path: '/Users/me/code' })
      .mockResolvedValueOnce({
        success: true,
        stdout: JSON.stringify({ findings: [{ category: 'Secrets', severity: 'high', description: 'x' }] }),
      });

    render(<DesktopSecurityAudit />);
    fireEvent.click(screen.getByRole('button', { name: /Browse/i }));
    await screen.findByText('/Users/me/code');

    fireEvent.click(screen.getByRole('button', { name: /RUN SECURITY SCAN/ }));

    // must not throw; unknown shape is treated as an empty, safe scan
    expect(await screen.findByText('ALL CLEAR')).toBeInTheDocument();
  });
});
