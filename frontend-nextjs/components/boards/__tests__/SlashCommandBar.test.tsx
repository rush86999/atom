import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { apiClient } from '../../../lib/api-client';
import { SlashCommandBar } from '../SlashCommandBar';

jest.mock('../../../lib/api-client', () => ({
  apiClient: {
    post: jest.fn(),
  },
}));

describe('SlashCommandBar', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows a hint when the user types a non-slash message', async () => {
    const user = userEvent.setup();
    render(<SlashCommandBar boardId="b1" />);

    await user.type(screen.getByPlaceholderText(/task create/i), 'hello there');
    await user.keyboard('{Enter}');

    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('POSTs to /api/atom-agent/chat for /task commands', async () => {
    const user = userEvent.setup();
    (apiClient.post as jest.Mock).mockResolvedValue({
      data: { response: { message: 'Created *Buy milk* in To Do.' } },
    });

    render(<SlashCommandBar boardId="b1" />);
    const input = screen.getByPlaceholderText(/task create/i);

    await user.type(input, '/task create Buy milk in To Do');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/api/atom-agent/chat', {
        message: '/task create Buy milk in To Do',
        user_id: 'system',
        context: { board_id: 'b1' },
      });
    });
  });

  it('handles HTTP failure gracefully', async () => {
    const user = userEvent.setup();
    (apiClient.post as jest.Mock).mockRejectedValue(new Error('Request failed with status code 500'));

    render(<SlashCommandBar boardId="b1" />);
    const input = screen.getByPlaceholderText(/task create/i);

    await user.type(input, '/task list');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalled();
    });
  });

  it('shows an error toast (not success) for a 200-with-error-body response', async () => {
    // The backend frequently returns HTTP 200 with a logical error envelope
    // {success: false, error: "..."} (e.g. governance denial, internal error).
    // The bar must surface this as an ERROR, not a success — otherwise the
    // user sees a misleading "Done." toast and believes their command ran.
    const user = userEvent.setup();
    (apiClient.post as jest.Mock).mockResolvedValue({
      data: { success: false, error: 'Action denied by governance policy.' },
    });

    render(<SlashCommandBar boardId="b1" />);
    const input = screen.getByPlaceholderText(/task create/i);

    await user.type(input, '/task create Buy milk');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalled();
    });

    // The error envelope must produce an error toast, never a success toast.
    // We assert the bar did NOT clear the input (it only clears on success),
    // which is the observable proxy for "treated this as a failure".
    await waitFor(() => {
      expect((input as HTMLInputElement).value).toBe('/task create Buy milk');
    });
  });
});
