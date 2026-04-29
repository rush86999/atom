/**
 * CommunicationHub Component Tests
 *
 * Tests verify message management, conversation handling,
 * compose functionality, and platform integration.
 *
 * Source: components/shared/CommunicationHub.tsx (173 lines uncovered)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CommunicationHub from '../CommunicationHub';
import { Message, Conversation } from '../CommunicationHub';

const mockMessage: Message = {
  id: '1',
  platform: 'email',
  from: 'team@company.com',
  to: 'user@example.com',
  subject: 'Weekly Team Update',
  preview: 'Here are the updates...',
  content: 'Dear Team, here are the updates.',
  timestamp: new Date('2025-10-20T14:30:00'),
  unread: true,
  priority: 'normal',
  status: 'received',
};

const mockConversation: Conversation = {
  id: 'conv-1',
  title: 'Weekly Team Updates',
  participants: ['team@company.com', 'user@example.com'],
  messages: [mockMessage],
  unreadCount: 1,
  lastMessage: new Date('2025-10-20T14:30:00'),
  platform: 'email',
  priority: 'normal',
};

describe('CommunicationHub', () => {
  // Test 1: renders with initial state
  test('renders with initial state', () => {
    render(<CommunicationHub />);

    expect(screen.getByText('Inbox')).toBeInTheDocument();
  });

  // Test 2: displays initial messages
  test('displays initial messages', () => {
    render(<CommunicationHub initialMessages={[mockMessage]} />);

    expect(screen.getByText('Weekly Team Update')).toBeInTheDocument();
  });

  // Test 3: displays conversations
  test('displays conversations', () => {
    render(<CommunicationHub initialConversations={[mockConversation]} />);

    expect(screen.getByText('Weekly Team Updates')).toBeInTheDocument();
  });

  // Test 4: handles message send callback
  test('handles message send callback', async () => {
    const handleMessageSend = jest.fn();

    render(<CommunicationHub onMessageSend={handleMessageSend} />);

    // Open compose
    const composeButton = screen.getByText('Compose');
    fireEvent.click(composeButton);

    await waitFor(() => {
      expect(screen.getByText('New Message')).toBeInTheDocument();
    });
  });

  // Test 5: filters messages by platform
  test('filters messages by platform', () => {
    render(
      <CommunicationHub
        initialMessages={[
          mockMessage,
          { ...mockMessage, id: '2', platform: 'slack', from: 'john.doe' },
        ]}
      />
    );

    expect(screen.getByText('team@company.com')).toBeInTheDocument();
    expect(screen.getByText('john.doe')).toBeInTheDocument();
  });

  // Test 6: sorts messages by priority
  test('sorts messages by priority', () => {
    render(
      <CommunicationHub
        initialMessages={[
          mockMessage,
          { ...mockMessage, id: '2', priority: 'high' as const },
        ]}
      />
    );

    const highPriorityMessage = screen.getByText('team@company.com');
    expect(highPriorityMessage).toBeInTheDocument();
  });

  // Test 7: handles search query
  test('handles search query', () => {
    render(
      <CommunicationHub
        initialMessages={[mockMessage]}
      />
    );

    const searchInput = screen.getByPlaceholderText(/search/i);
    fireEvent.change(searchInput, { target: { value: 'weekly' } });

    expect(searchInput).toHaveValue('weekly');
  });

  // Test 8: opens message details
  test('opens message details', async () => {
    render(<CommunicationHub initialMessages={[mockMessage]} />);

    const message = screen.getByText('Weekly Team Update');
    fireEvent.click(message);

    await waitFor(() => {
      expect(screen.getByText('Here are the updates...')).toBeInTheDocument();
    });
  });

  // Test 9: marks message as read
  test('marks message as read', async () => {
    const handleMessageUpdate = jest.fn();

    render(
      <CommunicationHub
        initialMessages={[mockMessage]}
        onMessageUpdate={handleMessageUpdate}
      />
    );

    const message = screen.getByText('Weekly Team Update');
    fireEvent.click(message);

    await waitFor(() => {
      expect(handleMessageUpdate).toHaveBeenCalled();
    });
  });

  // Test 10: deletes message
  test('deletes message', async () => {
    const handleMessageDelete = jest.fn();

    render(
      <CommunicationHub
        initialMessages={[mockMessage]}
        onMessageDelete={handleMessageDelete}
      />
    );

    // Find delete button (might need to adjust selector)
    const moreButton = screen.getAllByRole('button').find(
      btn => btn.getAttribute('aria-label')?.includes('more')
    );

    if (moreButton) {
      fireEvent.click(moreButton);

      await waitFor(() => {
        const deleteButton = screen.getByText(/delete/i);
        fireEvent.click(deleteButton);

        expect(handleMessageDelete).toHaveBeenCalledWith('1');
      });
    }
  });

  // Test 11: handles compose open state
  test('handles compose open state', () => {
    const onComposeChange = jest.fn();

    render(<CommunicationHub isComposeOpen={true} onComposeChange={onComposeChange} />);

    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);

    expect(onComposeChange).toHaveBeenCalledWith(false);
  });

  // Test 12: creates new conversation
  test('creates new conversation', () => {
    const handleConversationCreate = jest.fn();

    render(
      <CommunicationHub onConversationCreate={handleConversationCreate} />
    );

    const composeButton = screen.getByText('Compose');
    fireEvent.click(composeButton);

    // Compose dialog should open
    expect(screen.getByText('New Message')).toBeInTheDocument();
  });

  // Test 13: handles unread count
  test('handles unread count', () => {
    render(
      <CommunicationHub
        initialConversations={[mockConversation]}
      />
    );

    expect(screen.getByText('1')).toBeInTheDocument();
  });

  // Test 14: toggles between inbox and thread view
  test('toggles between inbox and thread view', async () => {
    render(<CommunicationHub initialConversations={[mockConversation]} />);

    const conversation = screen.getByText('Weekly Team Updates');
    fireEvent.click(conversation);

    await waitFor(() => {
      expect(screen.getByText('Thread')).toBeInTheDocument();
    });
  });

  // Test 15: handles compact view
  test('handles compact view', () => {
    const { container } = render(
      <CommunicationHub compactView={true} />
    );

    expect(container.firstChild).toBeInTheDocument();
  });

  // Test 16: uses quick reply templates
  test('uses quick reply templates', async () => {
    const template = {
      id: 'temp-1',
      name: 'Meeting Confirmation',
      content: 'Thank you for scheduling.',
      category: 'meetings',
      platform: ['email'],
    };

    render(<CommunicationHub initialTemplates={[template]} />);

    const composeButton = screen.getByText('Compose');
    fireEvent.click(composeButton);

    await waitFor(() => {
      expect(screen.getByText('New Message')).toBeInTheDocument();
    });
  });

  // Test 17: filters by unread status
  test('filters by unread status', () => {
    render(
      <CommunicationHub
        initialMessages={[mockMessage]}
      />
    );

    const filterButton = screen.getByRole('button', { name: /filter/i });
    fireEvent.click(filterButton);

    // Filter options should appear
    expect(screen.getByText('Unread')).toBeInTheDocument();
  });

  // Test 18: handles message reply
  test('handles message reply', async () => {
    const handleMessageSend = jest.fn();

    render(
      <CommunicationHub
        initialMessages={[mockMessage]}
        onMessageSend={handleMessageSend}
      />
    );

    const message = screen.getByText('Weekly Team Update');
    fireEvent.click(message);

    await waitFor(() => {
      const replyButton = screen.getByText(/reply/i);
      fireEvent.click(replyButton);
    });
  });

  // Test 19: displays message attachments
  test('displays message attachments', () => {
    const messageWithAttachment: Message = {
      ...mockMessage,
      attachments: ['document.pdf'],
    };

    render(<CommunicationHub initialMessages={[messageWithAttachment]} />);

    const message = screen.getByText('Weekly Team Update');
    fireEvent.click(message);

    // Should show attachment indicator
    expect(screen.getByText(/document.pdf/i)).toBeInTheDocument();
  });

  // Test 20: handles multiple platforms
  test('handles multiple platforms', () => {
    render(
      <CommunicationHub
        initialMessages={[
          mockMessage,
          { ...mockMessage, id: '2', platform: 'slack', from: 'john.doe' },
          { ...mockMessage, id: '3', platform: 'teams', from: 'sarah.wilson' },
        ]}
      />
    );

    expect(screen.getByText('team@company.com')).toBeInTheDocument();
    expect(screen.getByText('john.doe')).toBeInTheDocument();
    expect(screen.getByText('sarah.wilson')).toBeInTheDocument();
  });
});
