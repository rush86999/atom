/**
 * SalesChatSidebar Component Tests
 *
 * Verifies the real SalesChatSidebar (components/sales/SalesChatSidebar.tsx):
 * - renders collapsed with the vertical Sales AI label and opens on toggle
 * - opens with the welcome message, Online status and chat input
 * - sending a message POSTs to /api/atom-agent/chat with the workspace_id,
 *   appends the user message and renders the assistant response
 * - Enter key sends; empty input never sends
 * - loading indicator while the request is in flight
 * - failed requests append a system error message
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import SalesChatSidebar from '../SalesChatSidebar';

let chatBody: any = null;

// The send button and the open/close toggle both render with an empty
// accessible name (icon-only). The toggle is always the first button in the
// DOM; the send button is the second.
const getSendButton = (): HTMLButtonElement =>
  screen.getAllByRole('button')[1] as HTMLButtonElement;

describe('SalesChatSidebar', () => {
  beforeEach(() => {
    chatBody = null;
    server.resetHandlers();
    server.use(
      rest.post('/api/atom-agent/chat', (req, res, ctx) => {
        chatBody = req.body;
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            response: {
              message: 'Your weighted pipeline is $420k.',
              actions: [{ type: 'view_template', label: 'View details' }],
            },
          })
        );
      })
    );
  });

  it('renders collapsed with the vertical Sales AI label and opens on toggle', () => {
    render(<SalesChatSidebar workspaceId="ws-1" />);

    expect(screen.getByText('Sales AI')).toBeInTheDocument();
    expect(screen.queryByText('Sales Assistant')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button'));

    expect(screen.getByText('Sales Assistant')).toBeInTheDocument();
    expect(screen.getByText('Online')).toBeInTheDocument();
    expect(
      screen.getByText(/Hi! I'm your Sales Assistant/i)
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Ask Sales Assistant...')).toBeInTheDocument();
  });

  it('sends the message, renders user + assistant messages and clears the input', async () => {
    render(<SalesChatSidebar workspaceId="ws-1" />);
    fireEvent.click(screen.getByRole('button'));

    fireEvent.change(screen.getByPlaceholderText('Ask Sales Assistant...'), {
      target: { value: 'How is my weighted pipeline?' },
    });
    fireEvent.click(getSendButton());

    expect(await screen.findByText('Your weighted pipeline is $420k.')).toBeInTheDocument();
    expect(screen.getByText('How is my weighted pipeline?')).toBeInTheDocument();
    expect(chatBody).toEqual({
      message: 'How is my weighted pipeline?',
      user_id: 'anonymous_sales_user',
      workspace_id: 'ws-1',
    });
    expect((screen.getByPlaceholderText('Ask Sales Assistant...') as HTMLInputElement).value).toBe('');
  });

  it('sends on Enter and renders assistant action buttons', async () => {
    render(<SalesChatSidebar workspaceId="ws-1" />);
    fireEvent.click(screen.getByRole('button'));

    const input = screen.getByPlaceholderText('Ask Sales Assistant...');
    fireEvent.change(input, { target: { value: 'at-risk deals?' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(await screen.findByText('Your weighted pipeline is $420k.')).toBeInTheDocument();
    expect(chatBody.message).toBe('at-risk deals?');
    expect(screen.getByRole('button', { name: 'View details' })).toBeInTheDocument();
  });

  it('never sends for empty or whitespace input', () => {
    render(<SalesChatSidebar workspaceId="ws-1" />);
    fireEvent.click(screen.getByRole('button'));

    const input = screen.getByPlaceholderText('Ask Sales Assistant...');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
    fireEvent.click(getSendButton());

    expect(chatBody).toBeNull();
  });

  it('shows the analyzing indicator while the request is in flight', async () => {
    server.use(
      rest.post('/api/atom-agent/chat', (req, res, ctx) =>
        res(ctx.delay(150), ctx.status(200), ctx.json({ success: true, response: { message: 'Done' } }))
      )
    );
    render(<SalesChatSidebar workspaceId="ws-1" />);
    fireEvent.click(screen.getByRole('button'));

    fireEvent.change(screen.getByPlaceholderText('Ask Sales Assistant...'), {
      target: { value: 'hello' },
    });
    fireEvent.keyDown(screen.getByPlaceholderText('Ask Sales Assistant...'), {
      key: 'Enter',
      code: 'Enter',
    });

    expect(screen.getByText('Analyzing pipeline...')).toBeInTheDocument();
    expect(await screen.findByText('Done')).toBeInTheDocument();
    expect(screen.queryByText('Analyzing pipeline...')).not.toBeInTheDocument();
  });

  it('appends a system error message when the API call fails', async () => {
    server.use(
      rest.post('/api/atom-agent/chat', (req, res, ctx) => res(ctx.status(500), ctx.json({})))
    );
    render(<SalesChatSidebar workspaceId="ws-1" />);
    fireEvent.click(screen.getByRole('button'));

    fireEvent.change(screen.getByPlaceholderText('Ask Sales Assistant...'), {
      target: { value: 'hello' },
    });
    fireEvent.keyDown(screen.getByPlaceholderText('Ask Sales Assistant...'), {
      key: 'Enter',
      code: 'Enter',
    });

    expect(await screen.findByText('Error connecting to AI. Please try again.')).toBeInTheDocument();
  });

  it('keeps the send button disabled while processing', async () => {
    server.use(
      rest.post('/api/atom-agent/chat', (req, res, ctx) =>
        res(ctx.delay(200), ctx.status(200), ctx.json({ success: true, response: { message: 'Done' } }))
      )
    );
    render(<SalesChatSidebar workspaceId="ws-1" />);
    fireEvent.click(screen.getByRole('button'));

    fireEvent.change(screen.getByPlaceholderText('Ask Sales Assistant...'), {
      target: { value: 'hi' },
    });
    fireEvent.keyDown(screen.getByPlaceholderText('Ask Sales Assistant...'), {
      key: 'Enter',
      code: 'Enter',
    });

    await waitFor(() => {
      expect(getSendButton()).toBeDisabled();
    });

    expect(await screen.findByText('Done')).toBeInTheDocument();
    expect(getSendButton()).not.toBeDisabled();
  });
});
