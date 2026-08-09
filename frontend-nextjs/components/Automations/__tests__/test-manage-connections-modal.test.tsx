/**
 * ManageConnectionsModal Component Tests
 *
 * Tests verify the REAL ManageConnectionsModal component
 * (components/Automations/ManageConnectionsModal.tsx):
 *
 * - Dialog open/close gating (no fetch when closed)
 * - Loading + empty states
 * - Connection list rendering (status badges, created/active dates)
 * - Rename flow (PATCH success/failure, empty-name guard, cancel edit)
 * - Delete flow (confirm accept/decline, success/failure)
 * - onConnectionsUpdated callback contract
 *
 * The custom shadcn Dialog (createPortal) renders children unconditionally
 * when open; the portal target is jsdom's body so queries work as usual.
 * framer-motion renders fine in jsdom (inline styles only).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import ManageConnectionsModal from '../ManageConnectionsModal';

// Each connection row is a motion.div with class "group"; scope queries to a
// specific row so multiple identical icon buttons don't collide.
const rowOf = (name: string) =>
  screen.getByText(name).closest('.group') as HTMLElement;
const rowButton = (name: string, title: string) =>
  within(rowOf(name)).getByTitle(title);

jest.mock('@/components/ui/use-toast', () => {
  const mockToast = jest.fn();
  return {
    useToast: () => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
    ToastProvider: ({ children }: any) => children,
    __mockToast: mockToast,
  };
});

const toastMock = () =>
  (jest.requireMock('@/components/ui/use-toast') as any).__mockToast as jest.Mock;

const jsonResponse = (body: any, ok = true) => ({
  ok,
  status: ok ? 200 : 500,
  json: async () => body,
});

const connections = [
  {
    id: 'conn-1',
    name: 'Work Gmail',
    status: 'active',
    created_at: '2026-01-10T10:00:00Z',
    last_used: '2026-08-01T10:00:00Z',
  },
  {
    id: 'conn-2',
    name: 'Personal Gmail',
    status: 'expired',
    created_at: '2026-02-20T10:00:00Z',
    last_used: null,
  },
];

const defaultProps = {
  isOpen: true,
  onClose: jest.fn(),
  integrationId: 'gmail',
  integrationName: 'Gmail',
  onConnectionsUpdated: jest.fn(),
};

describe('ManageConnectionsModal', () => {
  let fetchSpy: jest.SpyInstance;

  beforeEach(() => {
    fetchSpy = jest
      .spyOn(global as any, 'fetch')
      .mockResolvedValue(jsonResponse(connections));
    jest.spyOn(window, 'confirm').mockReturnValue(true);
    toastMock().mockClear();
  });

  it('does not fetch or render content while closed', () => {
    render(<ManageConnectionsModal {...defaultProps} isOpen={false} />);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(screen.queryByText(/Manage Gmail Connections/)).not.toBeInTheDocument();
  });

  it('shows a loading state on first open', () => {
    render(<ManageConnectionsModal {...defaultProps} />);
    expect(screen.getByText('Loading connections...')).toBeInTheDocument();
  });

  it('shows the empty state when no connections exist', async () => {
    fetchSpy.mockResolvedValue(jsonResponse([]));
    render(<ManageConnectionsModal {...defaultProps} />);
    await waitFor(() => {
      expect(
        screen.getByText('No connections found for this integration.')
      ).toBeInTheDocument();
    });
  });

  it('renders connection rows with status badges and dates', async () => {
    render(<ManageConnectionsModal {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Work Gmail')).toBeInTheDocument();
    });
    expect(screen.getByText('Personal Gmail')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
    expect(screen.getByText('expired')).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledWith('/api/v1/connections?integration_id=gmail');
    expect(screen.getByText('Credentials are encrypted at rest')).toBeInTheDocument();
    expect(screen.getByText('Manage Gmail Connections')).toBeInTheDocument();
  });

  it('survives a failed connections fetch', async () => {
    fetchSpy.mockRejectedValue(new Error('boom'));
    render(<ManageConnectionsModal {...defaultProps} />);
    await waitFor(() => {
      expect(
        screen.getByText('No connections found for this integration.')
      ).toBeInTheDocument();
    });
  });

  it('renames a connection via PATCH and refreshes the list', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(connections)); // list load
    fetchSpy.mockResolvedValueOnce(jsonResponse({}));           // PATCH
    fetchSpy.mockResolvedValue(jsonResponse([]));               // re-fetch
    render(<ManageConnectionsModal {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Work Gmail')).toBeInTheDocument();
    });
    fireEvent.click(rowButton('Work Gmail', 'Rename'));

    const input = document.querySelector('input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Work Inbox' } });
    fireEvent.click(
      input.closest('.group')!.querySelector('.lucide-check')!.closest('button')!
    );

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/connections/conn-1',
        expect.objectContaining({
          method: 'PATCH',
          body: JSON.stringify({ name: 'Work Inbox' }),
        })
      );
    });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Success',
        description: 'Connection renamed successfully',
      })
    );
    expect(defaultProps.onConnectionsUpdated).toHaveBeenCalled();
  });

  it('does not PATCH when the rename input is blank', async () => {
    render(<ManageConnectionsModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText('Work Gmail')).toBeInTheDocument();
    });
    fireEvent.click(rowButton('Work Gmail', 'Rename'));
    const input = document.querySelector('input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.click(
      input.closest('.group')!.querySelector('.lucide-check')!.closest('button')!
    );

    await waitFor(() => {
      expect(fetchSpy).not.toHaveBeenCalledWith(
        '/api/v1/connections/conn-1',
        expect.anything()
      );
    });
  });

  it('toasts an error when the rename PATCH fails', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(connections));
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, false));
    fetchSpy.mockResolvedValue(jsonResponse([]));
    render(<ManageConnectionsModal {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Work Gmail')).toBeInTheDocument();
    });
    fireEvent.click(rowButton('Work Gmail', 'Rename'));
    const input = document.querySelector('input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Renamed' } });
    fireEvent.click(
      input.closest('.group')!.querySelector('.lucide-check')!.closest('button')!
    );

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to rename connection',
          variant: 'error',
        })
      );
    });
    expect(defaultProps.onConnectionsUpdated).not.toHaveBeenCalled();
  });

  it('cancels an in-progress rename', async () => {
    render(<ManageConnectionsModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText('Work Gmail')).toBeInTheDocument();
    });
    fireEvent.click(rowButton('Work Gmail', 'Rename'));
    expect(screen.getByDisplayValue('Work Gmail')).toBeInTheDocument();

    fireEvent.click(
      screen
        .getByDisplayValue('Work Gmail')
        .closest('.group')!
        .querySelector('.lucide-x')!.closest('button')!
    );
    expect(screen.queryByDisplayValue('Work Gmail')).not.toBeInTheDocument();
    expect(screen.getByText('Work Gmail')).toBeInTheDocument();
  });

  it('deletes a connection after confirm and refreshes the list', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(connections)); // list load
    fetchSpy.mockResolvedValueOnce(jsonResponse({}));           // DELETE
    fetchSpy.mockResolvedValue(jsonResponse([]));               // re-fetch
    render(<ManageConnectionsModal {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Work Gmail')).toBeInTheDocument();
    });
    fireEvent.click(rowButton('Work Gmail', 'Delete'));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/connections/conn-1',
        expect.objectContaining({ method: 'DELETE' })
      );
    });
    expect(toastMock()).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Deleted',
        description: 'Connection removed successfully',
      })
    );
    expect(defaultProps.onConnectionsUpdated).toHaveBeenCalled();
  });

  it('skips the delete when the user declines the confirm dialog', async () => {
    (window.confirm as jest.Mock).mockReturnValue(false);
    render(<ManageConnectionsModal {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Work Gmail')).toBeInTheDocument();
    });
    fireEvent.click(rowButton('Work Gmail', 'Delete'));

    const deletes = fetchSpy.mock.calls.filter(
      ([url, init]: any) => init?.method === 'DELETE'
    );
    expect(deletes).toHaveLength(0);
    expect(toastMock()).not.toHaveBeenCalled();
  });

  it('toasts an error when the delete fails', async () => {
    fetchSpy.mockResolvedValueOnce(jsonResponse(connections));
    fetchSpy.mockResolvedValueOnce(jsonResponse({}, false));
    fetchSpy.mockResolvedValue(jsonResponse([]));
    render(<ManageConnectionsModal {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText('Work Gmail')).toBeInTheDocument();
    });
    fireEvent.click(rowButton('Work Gmail', 'Delete'));

    await waitFor(() => {
      expect(toastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to delete connection',
          variant: 'error',
        })
      );
    });
  });

  it('closes via the Done button', async () => {
    render(<ManageConnectionsModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText('Work Gmail')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /done/i }));
    expect(defaultProps.onClose).toHaveBeenCalled();
  });
});
