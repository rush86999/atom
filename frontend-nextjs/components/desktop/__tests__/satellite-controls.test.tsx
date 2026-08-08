/**
 * SatelliteControls Component Tests
 *
 * Verifies the real SatelliteControls (components/desktop/satellite-controls.tsx):
 * - renders nothing outside the Tauri runtime
 * - renders the node card with STOPPED badge, script path input and connect button
 * - connecting without a backend token shows the error state
 * - connecting invokes start_satellite with the session API key + script path
 *   and flips to RUNNING with the connected message
 * - disconnecting invokes stop_satellite and flips back to STOPPED
 * - a stop failure surfaces the error message
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

let mockSessionData: any = { backendToken: 'tok-123' };

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: mockSessionData, status: 'authenticated' }),
}));

// imported after the next-auth mock so the factory never runs before mockSessionData exists
import { SatelliteControls } from '../satellite-controls';

const getTauri = () => (window as any).__TAURI__;

// The shadcn Label renders without htmlFor, so query the input element itself
const getPathInput = (container: HTMLElement): HTMLInputElement =>
  container.querySelector('input') as HTMLInputElement;

describe('SatelliteControls', () => {
  beforeEach(() => {
    mockSessionData = { backendToken: 'tok-123' };
    (window as any).__TAURI__ = {
      core: { invoke: jest.fn() },
    };
  });

  afterEach(() => {
    delete (window as any).__TAURI__;
  });

  it('renders nothing when not running inside Tauri', () => {
    delete (window as any).__TAURI__;
    const { container } = render(<SatelliteControls />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the node card with STOPPED status and connect button', async () => {
    const { container } = render(<SatelliteControls />);

    expect(await screen.findByText('Local Node (Satellite)')).toBeInTheDocument();
    expect(screen.getByText('STOPPED')).toBeInTheDocument();
    expect(screen.getByText('Allow Atom Cloud to control this machine.')).toBeInTheDocument();

    const input = getPathInput(container);
    expect(input.value).toBe('scripts/satellite/atom_satellite.py');
    expect(input).not.toBeDisabled();

    expect(screen.getByRole('button', { name: /Connect Satellite/ })).toBeInTheDocument();
  });

  it('starts the satellite with the session API key and script path', async () => {
    getTauri().core.invoke.mockResolvedValueOnce(undefined);

    const { container } = render(<SatelliteControls />);
    await screen.findByText('STOPPED');
    fireEvent.click(screen.getByRole('button', { name: /Connect Satellite/ }));

    expect(getTauri().core.invoke).toHaveBeenCalledWith('start_satellite', {
      apiKey: 'tok-123',
      scriptPath: 'scripts/satellite/atom_satellite.py',
    });

    expect(await screen.findByText('RUNNING')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Disconnect Satellite/ })).toBeInTheDocument();
    // success message is state-only; the running badge is the visible signal
    expect(screen.queryByText(/Satellite connected/)).not.toBeInTheDocument();
    expect(getPathInput(container)).toBeDisabled();
  });

  it('shows an error when no API key is present in the session', async () => {
    mockSessionData = {};
    render(<SatelliteControls />);
    await screen.findByText('STOPPED');

    fireEvent.click(screen.getByRole('button', { name: /Connect Satellite/ }));

    expect(
      await screen.findByText('Failed to start: Error: No API Key found. Please log in again.')
    ).toBeInTheDocument();
    expect(screen.getByText('ERROR')).toBeInTheDocument();
    expect(getTauri().core.invoke).not.toHaveBeenCalledWith('start_satellite', expect.anything());
  });

  it('disconnects the satellite and flips back to stopped', async () => {
    getTauri().core.invoke
      .mockResolvedValueOnce(undefined) // start
      .mockResolvedValueOnce(undefined); // stop

    render(<SatelliteControls />);
    await screen.findByText('STOPPED');
    fireEvent.click(screen.getByRole('button', { name: /Connect Satellite/ }));
    await screen.findByText('RUNNING');

    fireEvent.click(screen.getByRole('button', { name: /Disconnect Satellite/ }));

    await waitFor(() => expect(screen.getByText('STOPPED')).toBeInTheDocument());
    expect(getTauri().core.invoke).toHaveBeenCalledWith('stop_satellite');
    expect(screen.getByRole('button', { name: /Connect Satellite/ })).toBeInTheDocument();
  });

  it('shows the error message when stopping fails', async () => {
    getTauri().core.invoke
      .mockResolvedValueOnce(undefined) // start
      .mockRejectedValueOnce(new Error('daemon not running')); // stop

    render(<SatelliteControls />);
    await screen.findByText('STOPPED');
    fireEvent.click(screen.getByRole('button', { name: /Connect Satellite/ }));
    await screen.findByText('RUNNING');

    fireEvent.click(screen.getByRole('button', { name: /Disconnect Satellite/ }));

    // stop failure flips the status to error so the message is visible
    expect(await screen.findByText('Error stopping: Error: daemon not running')).toBeInTheDocument();
    expect(screen.getByText('ERROR')).toBeInTheDocument();
  });

  it('disables the script path input while the satellite is running', async () => {
    getTauri().core.invoke.mockResolvedValueOnce(undefined);

    const { container } = render(<SatelliteControls />);
    await screen.findByText('STOPPED');
    fireEvent.click(screen.getByRole('button', { name: /Connect Satellite/ }));
    await screen.findByText('RUNNING');

    expect(getPathInput(container)).toBeDisabled();
  });
});
