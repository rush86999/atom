/**
 * ShareWorkflowModal Component Tests
 *
 * Tests verify the real ShareWorkflowModal component
 * (components/Collaboration/ShareWorkflowModal.tsx):
 * - renders title, permission switches, expiration/usage controls
 * - Generate Share Link POSTs to /api/collaboration/shares with the selected
 *   permissions/expiry and renders the returned link + active share list
 * - Copy button writes the link to the clipboard and flips to "Copied"
 * - Revoke deletes the share via DELETE and removes it from the list
 * - Email invite tab validates input and shows the coming-soon toast
 * - error toasts on API failure; Close closes the dialog
 *
 * API: POST /api/collaboration/shares, DELETE /api/collaboration/shares/:id
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import ShareWorkflowModal from '../ShareWorkflowModal';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const renderModal = (props: Partial<React.ComponentProps<typeof ShareWorkflowModal>> = {}) =>
  render(
    <ShareWorkflowModal
      workflowId="wf-1"
      workflowName="Sales Flow"
      open={true}
      onOpenChange={jest.fn()}
      currentUserId="user-1"
      {...props}
    />
  );

describe('ShareWorkflowModal', () => {
  let postedBodies: any[];
  let deletedShares: string[];

  beforeEach(() => {
    jest.clearAllMocks();
    postedBodies = [];
    deletedShares = [];
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: jest.fn().mockResolvedValue(undefined) },
    });

    server.resetHandlers();
    server.use(
      rest.post('/api/collaboration/shares', async (req, res, ctx) => {
        postedBodies.push(req.body);
        return res(
          ctx.status(200),
          ctx.json({ share_id: 'sh-1', share_link: 'http://localhost/share/sh-1', use_count: 0 })
        );
      }),
      rest.delete('/api/collaboration/shares/:shareId', (req, res, ctx) => {
        deletedShares.push(req.params.shareId as string);
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );
  });

  it('renders the dialog title, description and permission switches', () => {
    renderModal();

    expect(screen.getByText('Share "Sales Flow"')).toBeInTheDocument();
    expect(screen.getByText('Share this workflow with your team members')).toBeInTheDocument();
    expect(screen.getByText('View workflow')).toBeInTheDocument();
    expect(screen.getByText('Edit workflow')).toBeInTheDocument();
    expect(screen.getByText('Comment')).toBeInTheDocument();
    expect(screen.getByText('Share with others')).toBeInTheDocument();
    expect(screen.getAllByRole('switch')).toHaveLength(4);
    expect(screen.getByText('Never')).toBeInTheDocument();
    expect(screen.getByText('7 Days')).toBeInTheDocument();
    expect(screen.getByText('30 Days')).toBeInTheDocument();
  });

  it('creates a share link with the default permissions', async () => {
    renderModal();

    fireEvent.click(screen.getByRole('button', { name: /generate share link/i }));

    await waitFor(() => {
      expect(postedBodies).toHaveLength(1);
    });
    expect(postedBodies[0]).toMatchObject({
      workflow_id: 'wf-1',
      share_type: 'link',
      permissions: { can_view: true, can_edit: false, can_comment: true, can_share: false },
    });

    await waitFor(() => {
      expect(screen.getByDisplayValue('http://localhost/share/sh-1')).toBeInTheDocument();
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Success', description: 'Share link created successfully' })
    );
  });

  it('includes toggled permissions and expiry in the share payload', async () => {
    renderModal();

    const switches = screen.getAllByRole('switch');
    fireEvent.click(switches[1]); // can_edit
    fireEvent.click(switches[3]); // can_share
    fireEvent.click(screen.getByRole('button', { name: '7 Days' }));
    fireEvent.change(screen.getByPlaceholderText('10'), { target: { value: '5' } });

    fireEvent.click(screen.getByRole('button', { name: /generate share link/i }));

    await waitFor(() => {
      expect(postedBodies).toHaveLength(1);
    });
    expect(postedBodies[0].permissions).toMatchObject({
      can_edit: true,
      can_share: true,
      can_view: true,
      can_comment: true,
    });
    expect(postedBodies[0].expires_in_days).toBe(7);
    expect(postedBodies[0].max_uses).toBe(5);
  });

  it('copies the share link to the clipboard and shows the Copied state', async () => {
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: /generate share link/i }));
    await screen.findByDisplayValue('http://localhost/share/sh-1');

    fireEvent.click(screen.getByRole('button', { name: /copy/i }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('http://localhost/share/sh-1');
    });
    expect(screen.getByText('Copied')).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Copied!', description: 'Share link copied to clipboard' })
    );
  });

  it('lists the active share and revokes it via DELETE', async () => {
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: /generate share link/i }));
    await screen.findByText('Active Share Links');

    expect(screen.getByText('0 uses')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /revoke/i }));

    await waitFor(() => {
      expect(deletedShares).toContain('sh-1');
    });
    await waitFor(() => {
      expect(screen.queryByText('Active Share Links')).not.toBeInTheDocument();
    });
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Success', description: 'Share link revoked' })
    );
  });

  it('shows an error toast when share creation fails', async () => {
    server.use(
      rest.post('/api/collaboration/shares', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    renderModal();
    fireEvent.click(screen.getByRole('button', { name: /generate share link/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create share link' })
      );
    });
  });

  it('sends email invites and reports the coming-soon toast with the recipients', () => {
    renderModal();

    fireEvent.click(screen.getByRole('button', { name: /email invite/i }));
    fireEvent.change(screen.getByLabelText('Email Addresses'), {
      target: { value: 'a@example.com, b@example.com' },
    });

    fireEvent.click(screen.getByRole('button', { name: /send invites/i }));

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Coming Soon',
        description: 'Invites would be sent to: a@example.com, b@example.com',
      })
    );
  });

  it('validates that at least one email address is required', () => {
    renderModal();

    fireEvent.click(screen.getByRole('button', { name: /email invite/i }));
    fireEvent.click(screen.getByRole('button', { name: /send invites/i }));

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Error',
        description: 'Please enter at least one email address',
      })
    );
  });

  it('calls onOpenChange(false) when Close is clicked', () => {
    const onOpenChange = jest.fn();
    renderModal({ onOpenChange });

    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
