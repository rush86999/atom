import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { apiClient } from '../../../lib/api-client';

jest.mock('../../../lib/api-client', () => ({
  apiClient: {
    fetch: jest.fn(),
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

    expect(apiClient.fetch).not.toHaveBeenCalled();
  });

  it('POSTs to /api/atom-agent/chat for /task commands', async () => {
    const user = userEvent.setup();
    (apiClient.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ response: { message: 'Created *Buy milk* in To Do.' } }),
    });

    render(<SlashCommandBar boardId="b1" />);
    const input = screen.getByPlaceholderText(/task create/i);

    await user.type(input, '/task create Buy milk in To Do');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(apiClient.fetch).toHaveBeenCalledWith('/api/atom-agent/chat', expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"board_id":"b1"'),
      }));
    });
  });

  it('handles HTTP failure gracefully', async () => {
    const user = userEvent.setup();
    (apiClient.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    render(<SlashCommandBar boardId="b1" />);
    const input = screen.getByPlaceholderText(/task create/i);

    await user.type(input, '/task list');
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(apiClient.fetch).toHaveBeenCalled();
    });
  });
});

import { SlashCommandBar } from '../SlashCommandBar';
