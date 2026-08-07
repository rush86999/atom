/**
 * TeamManagementModal component tests.
 *
 * fetch is mocked per test. Covers open/closed rendering, form validation
 * gating, create success (POST payload + callbacks), create failure, and the
 * not-authenticated guard.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import TeamManagementModal from '../TeamManagementModal';

describe('TeamManagementModal', () => {
  const mockOnClose = jest.fn();
  const mockOnTeamCreated = jest.fn();

  const mockFetch = (res: { ok: boolean; status?: number; json?: any }) => {
    (global.fetch as jest.Mock) = jest.fn(() =>
      Promise.resolve({
        ok: res.ok,
        status: res.status ?? 200,
        json: async () => res.json ?? {},
      })
    );
  };

  const renderModal = () =>
    render(
      <TeamManagementModal
        isOpen
        onClose={mockOnClose}
        workspaceId="ws-1"
        onTeamCreated={mockOnTeamCreated}
      />
    );

  beforeEach(() => {
    jest.clearAllMocks();
    // localStorage is a real jsdom Storage instance (setup.ts's mock assignment
    // does not survive the getter-only global) → spy on Storage.prototype.
    jest.spyOn(Storage.prototype, 'getItem').mockReturnValue('token123');
    mockFetch({ ok: true, json: { id: 'team-9', name: 'Engineering' } });
  });

  it('renders nothing when closed', () => {
    const { container } = render(
      <TeamManagementModal isOpen={false} onClose={mockOnClose} workspaceId="ws-1" />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the form when open', () => {
    renderModal();
    expect(screen.getByRole('heading', { name: /Create Team/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Engineering Team')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Team description...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Create Team/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
  });

  it('keeps the submit button disabled until a name is provided', () => {
    renderModal();
    const submit = screen.getByRole('button', { name: /Create Team/i });
    expect(submit).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText('Engineering Team'), {
      target: { value: 'Platform' },
    });
    expect(screen.getByRole('button', { name: /Create Team/i })).toBeEnabled();
  });

  it('creates a team, calls onTeamCreated and closes', async () => {
    renderModal();
    fireEvent.change(screen.getByPlaceholderText('Engineering Team'), {
      target: { value: 'Platform' },
    });
    fireEvent.change(screen.getByPlaceholderText('Team description...'), {
      target: { value: 'Builds the platform' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Create Team/i }));

    await waitFor(() => {
      expect(mockOnTeamCreated).toHaveBeenCalledWith({ id: 'team-9', name: 'Engineering' });
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/enterprise/teams',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer token123',
        },
      })
    );
    const [, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({
      name: 'Platform',
      description: 'Builds the platform',
      workspace_id: 'ws-1',
    });
  });

  it('shows an error message when the create request fails', async () => {
    mockFetch({ ok: false, status: 500, json: {} });
    renderModal();
    fireEvent.change(screen.getByPlaceholderText('Engineering Team'), {
      target: { value: 'Platform' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Create Team/i }));

    expect(await screen.findByText('Failed to create team')).toBeInTheDocument();
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it('shows the not-authenticated error when no token exists', async () => {
    jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    renderModal();
    fireEvent.change(screen.getByPlaceholderText('Engineering Team'), {
      target: { value: 'Platform' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Create Team/i }));

    expect(await screen.findByText('Not authenticated')).toBeInTheDocument();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('closes via the Cancel button', () => {
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('closes via the X button', () => {
    const { container } = renderModal();
    fireEvent.click(container.querySelector('svg.lucide-x')!.closest('button')!);
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });
});
