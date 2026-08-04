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
});
