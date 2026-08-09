/**
 * CommunicationHub Component Tests
 *
 * Verifies the real shared CommunicationHub (components/shared/CommunicationHub.tsx):
 * - message list rendering (from, subject, preview, priority/unread badges)
 * - search filtering + clear
 * - unread-only filter, platform dropdown filter, mark-all-read
 * - message viewer: open, mark-as-read, delete, reply
 * - compose flow: new message (ingest POST → onMessageSend), failure path
 * - quick-reply templates, empty state, conversations, compact view
 * - controlled/uncontrolled compose open state
 *
 * Uses the shared MSW server for the /api/atom/communication/memory/ingest call.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import CommunicationHub, {
  Message,
  Conversation,
  QuickReplyTemplate,
} from '../CommunicationHub';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: any) => children,
}));

const mockMessage: Message = {
  id: '1',
  platform: 'email',
  from: 'team@company.com',
  to: 'user@example.com',
  subject: 'Weekly Team Update',
  preview: 'Here are the updates...',
  content: 'Dear Team, here are the updates.',
  timestamp: new Date('2025-10-20T09:00:00'),
  unread: true,
  priority: 'normal',
  status: 'received',
};

const readMessage: Message = {
  ...mockMessage,
  id: '2',
  platform: 'slack',
  from: 'john.doe',
  subject: 'Meeting Reminder',
  preview: "Don't forget the standup",
  content: 'Standup at 10am.',
  timestamp: new Date('2025-10-20T10:30:00'),
  unread: false,
  priority: 'high' as const,
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

const template: QuickReplyTemplate = {
  id: 'temp-1',
  name: 'Meeting Confirmation',
  content: 'Thank you for scheduling.',
  category: 'meetings',
  platform: ['email'],
};

let ingestBody: any = null;

const defaultProps = {
  onMessageSend: jest.fn(),
  onMessageUpdate: jest.fn(),
  onMessageDelete: jest.fn(),
  onConversationCreate: jest.fn(),
  currentUser: 'test@example.com',
};

const fillComposeForm = (to = 'bob@example.com', subject = 'Hello Bob', content = 'Are you around?') => {
  fireEvent.change(screen.getByPlaceholderText('Recipient email or username'), {
    target: { value: to },
  });
  fireEvent.change(screen.getByPlaceholderText('Message subject'), {
    target: { value: subject },
  });
  fireEvent.change(screen.getByPlaceholderText('Type your message here...'), {
    target: { value: content },
  });
};

describe('CommunicationHub', () => {
  beforeEach(() => {
    mockToast.mockClear();
    ingestBody = null;
    server.resetHandlers();
    server.use(
      rest.post('/api/atom/communication/memory/ingest', (req, res, ctx) => {
        ingestBody = req.body;
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );
  });

  test('renders messages with details and badges', () => {
    render(<CommunicationHub {...defaultProps} initialMessages={[mockMessage]} />);

    expect(screen.getByText('Communication Hub')).toBeInTheDocument();
    expect(screen.getByText('team@company.com')).toBeInTheDocument();
    expect(screen.getByText('Weekly Team Update')).toBeInTheDocument();
    expect(screen.getByText('Here are the updates...')).toBeInTheDocument();
    expect(screen.getByText('New')).toBeInTheDocument();
    expect(screen.getByText('normal')).toBeInTheDocument();
  });

  test('sorts messages newest first by default', () => {
    const { container } = render(
      <CommunicationHub {...defaultProps} initialMessages={[mockMessage, readMessage]} />
    );

    const list = container.querySelector('.space-y-2')!;
    expect(list.children[0].textContent).toContain('Meeting Reminder');
    expect(list.children[1].textContent).toContain('Weekly Team Update');
  });

  test('filters messages by search and clears the query', () => {
    render(
      <CommunicationHub {...defaultProps} initialMessages={[mockMessage, readMessage]} />
    );

    const input = screen.getByPlaceholderText('Search messages...');
    fireEvent.change(input, { target: { value: 'reminder' } });

    expect(screen.getByText('Meeting Reminder')).toBeInTheDocument();
    expect(screen.queryByText('Weekly Team Update')).not.toBeInTheDocument();

    const clearButton = document.querySelector('button.absolute') as HTMLButtonElement;
    expect(clearButton).toBeInTheDocument();
    fireEvent.click(clearButton);

    expect(screen.getByText('Weekly Team Update')).toBeInTheDocument();
    expect(screen.getByText('Meeting Reminder')).toBeInTheDocument();
  });

  test('search matches the from field', () => {
    render(
      <CommunicationHub {...defaultProps} initialMessages={[mockMessage, readMessage]} />
    );

    fireEvent.change(screen.getByPlaceholderText('Search messages...'), {
      target: { value: 'john' },
    });

    expect(screen.getByText('Meeting Reminder')).toBeInTheDocument();
    expect(screen.queryByText('Weekly Team Update')).not.toBeInTheDocument();
  });

  test('filters to unread messages only', () => {
    render(
      <CommunicationHub {...defaultProps} initialMessages={[mockMessage, readMessage]} />
    );

    fireEvent.click(screen.getByRole('button', { name: /unread only/i }));

    expect(screen.getByText('Weekly Team Update')).toBeInTheDocument();
    expect(screen.queryByText('Meeting Reminder')).not.toBeInTheDocument();
  });

  test('mark all read clears badges and toasts', () => {
    render(
      <CommunicationHub
        {...defaultProps}
        initialMessages={[mockMessage, { ...readMessage, unread: true }]}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /mark all read/i }));

    expect(
      mockToast
    ).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'All messages marked as read' })
    );
    expect(screen.queryAllByText('New')).toHaveLength(0);
  });

  test('filters by platform via the dropdown', async () => {
    const user = userEvent.setup();
    render(
      <CommunicationHub {...defaultProps} initialMessages={[mockMessage, readMessage]} />
    );

    await user.click(screen.getByRole('button', { name: /platform: all/i }));
    await user.click(
      await screen.findByRole('menuitemcheckbox', { name: 'Email' })
    );

    expect(screen.getByText('Weekly Team Update')).toBeInTheDocument();
    expect(screen.queryByText('Meeting Reminder')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /platform: 1/i })).toBeInTheDocument();
  });

  test('clicking a message opens the viewer with content and attachments', async () => {
    render(
      <CommunicationHub
        {...defaultProps}
        initialMessages={[{ ...mockMessage, attachments: ['document.pdf'] }]}
      />
    );

    fireEvent.click(screen.getByText('Weekly Team Update'));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Dear Team, here are the updates.')).toBeInTheDocument();
    expect(screen.getByText('Attachments:')).toBeInTheDocument();
    expect(screen.getByText('document.pdf')).toBeInTheDocument();
  });

  test('clicking an unread message auto-marks it read', async () => {
    const onMessageUpdate = jest.fn();
    render(
      <CommunicationHub
        {...defaultProps}
        initialMessages={[mockMessage]}
        onMessageUpdate={onMessageUpdate}
      />
    );

    fireEvent.click(screen.getByText('Weekly Team Update'));

    await waitFor(() =>
      expect(onMessageUpdate).toHaveBeenCalledWith('1', { unread: false })
    );
  });

  test('marks a message as read from the viewer', async () => {
    const onMessageUpdate = jest.fn();
    render(
      <CommunicationHub
        {...defaultProps}
        initialMessages={[mockMessage]}
        onMessageUpdate={onMessageUpdate}
      />
    );

    fireEvent.click(screen.getByText('Weekly Team Update'));
    fireEvent.click(await screen.findByRole('button', { name: /mark as read/i }));

    expect(onMessageUpdate).toHaveBeenCalledWith('1', { unread: false });
    expect(
      mockToast
    ).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Message updated' })
    );
  });

  test('deletes a message from the viewer', async () => {
    const onMessageDelete = jest.fn();
    render(
      <CommunicationHub
        {...defaultProps}
        initialMessages={[mockMessage]}
        onMessageDelete={onMessageDelete}
      />
    );

    fireEvent.click(screen.getByText('Weekly Team Update'));
    fireEvent.click(await screen.findByRole('button', { name: /delete/i }));

    expect(onMessageDelete).toHaveBeenCalledWith('1');
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    );
    expect(screen.queryByText('Weekly Team Update')).not.toBeInTheDocument();
    expect(screen.getByText('No messages found')).toBeInTheDocument();
  });

  test('reply prefills the composer and sends as a reply', async () => {
    const onMessageSend = jest.fn();
    render(
      <CommunicationHub
        {...defaultProps}
        initialMessages={[mockMessage]}
        onMessageSend={onMessageSend}
      />
    );

    fireEvent.click(screen.getByText('Weekly Team Update'));
    fireEvent.click(await screen.findByRole('button', { name: /reply/i }));

    expect(
      await screen.findByRole('heading', { name: /reply to team@company\.com/i })
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Message subject')).toHaveValue(
      'Re: Weekly Team Update'
    );

    fireEvent.change(screen.getByPlaceholderText('Type your message here...'), {
      target: { value: 'Sounds good!' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send message/i }));

    await waitFor(() => expect(onMessageSend).toHaveBeenCalledTimes(1));
    expect(onMessageSend).toHaveBeenCalledWith(
      expect.objectContaining({
        isReply: true,
        subject: 'Re: Weekly Team Update',
        from: 'test@example.com',
      })
    );
  });

  test('sends a new message: ingests, appends to list, and toasts', async () => {
    const onMessageSend = jest.fn();
    render(
      <CommunicationHub
        {...defaultProps}
        initialMessages={[mockMessage]}
        onMessageSend={onMessageSend}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /new message/i }));
    expect(
      screen.getByRole('heading', { name: /compose new message/i })
    ).toBeInTheDocument();

    fillComposeForm('bob@example.com', 'Hello Bob', 'Are you around?');
    fireEvent.click(screen.getByRole('button', { name: /send message/i }));

    await waitFor(() => expect(onMessageSend).toHaveBeenCalledTimes(1));
    expect(onMessageSend).toHaveBeenCalledWith(
      expect.objectContaining({
        to: 'bob@example.com',
        from: 'test@example.com',
        subject: 'Hello Bob',
        priority: 'normal',
      })
    );
    expect(ingestBody).toMatchObject({
      app_type: 'email',
      sender: 'test@example.com',
      direction: 'outbound',
    });
    expect(await screen.findByText('Hello Bob')).toBeInTheDocument();
    expect(screen.getByText('Messages (2)')).toBeInTheDocument();
    expect(
      mockToast
    ).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Message sent' })
    );
  });

  test('shows an error toast when ingest fails and does not append the message', async () => {
    server.use(
      rest.post('/api/atom/communication/memory/ingest', (req, res, ctx) =>
        res(ctx.status(500))
      )
    );
    const onMessageSend = jest.fn();
    render(
      <CommunicationHub
        {...defaultProps}
        initialMessages={[mockMessage]}
        onMessageSend={onMessageSend}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /new message/i }));
    fillComposeForm();
    fireEvent.click(screen.getByRole('button', { name: /send message/i }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', variant: 'error' })
      )
    );
    expect(onMessageSend).not.toHaveBeenCalled();
    expect(screen.getByText('Messages (1)')).toBeInTheDocument();
  });

  test('shows an empty state with a compose action', () => {
    render(<CommunicationHub {...defaultProps} />);

    expect(screen.getByText('No messages found')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /compose new message/i }));
    expect(
      screen.getByRole('heading', { name: /compose new message/i })
    ).toBeInTheDocument();
  });

  test('renders recent conversations with unread badges', () => {
    render(
      <CommunicationHub
        {...defaultProps}
        initialConversations={[mockConversation]}
      />
    );

    expect(screen.getByText('Recent Conversations')).toBeInTheDocument();
    expect(screen.getByText('Weekly Team Updates')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(
      screen.getByText('team@company.com, user@example.com')
    ).toBeInTheDocument();

    expect(() => fireEvent.click(screen.getByText('Weekly Team Updates'))).not.toThrow();
  });

  test('compact view caps conversations at three and shrinks the layout', () => {
    const convs = [1, 2, 3, 4].map((i) => ({
      ...mockConversation,
      id: `c${i}`,
      title: `Conv ${i}`,
      lastMessage: new Date(2025, 9, 20, i),
    }));

    render(<CommunicationHub {...defaultProps} initialConversations={convs} compactView />);

    expect(screen.getByText('Conv 4')).toBeInTheDocument();
    expect(screen.getByText('Conv 3')).toBeInTheDocument();
    expect(screen.getByText('Conv 2')).toBeInTheDocument();
    expect(screen.queryByText('Conv 1')).not.toBeInTheDocument();
  });

  test('hides navigation controls when showNavigation is false', () => {
    render(
      <CommunicationHub
        {...defaultProps}
        showNavigation={false}
        initialMessages={[mockMessage]}
      />
    );

    expect(screen.queryByPlaceholderText('Search messages...')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /new message/i })).not.toBeInTheDocument();
    expect(screen.getByText('Weekly Team Update')).toBeInTheDocument();
  });

  test('applies a quick-reply template inside the composer', async () => {
    const onMessageSend = jest.fn();
    render(
      <CommunicationHub
        {...defaultProps}
        initialTemplates={[template]}
        onMessageSend={onMessageSend}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /new message/i }));
    fireEvent.click(
      await screen.findByRole('button', { name: /meeting confirmation/i })
    );

    const content = screen.getByPlaceholderText('Type your message here...');
    expect(content).toHaveValue('Thank you for scheduling.');

    fireEvent.change(screen.getByPlaceholderText('Recipient email or username'), {
      target: { value: 'alice@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Message subject'), {
      target: { value: 'Confirming' },
    });
    fireEvent.click(screen.getByRole('button', { name: /send message/i }));

    await waitFor(() => expect(onMessageSend).toHaveBeenCalledTimes(1));
    expect(onMessageSend).toHaveBeenCalledWith(
      expect.objectContaining({ content: 'Thank you for scheduling.' })
    );
  });

  test('supports a controlled compose-open state', () => {
    const onComposeChange = jest.fn();

    render(
      <CommunicationHub
        {...defaultProps}
        isComposeOpen={true}
        onComposeChange={onComposeChange}
      />
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(onComposeChange).toHaveBeenCalledWith(false);
  });

  test('uncontrolled compose: clicking New Message reports via onComposeChange', () => {
    const onComposeChange = jest.fn();

    render(
      <CommunicationHub {...defaultProps} onComposeChange={onComposeChange} />
    );

    fireEvent.click(screen.getByRole('button', { name: /new message/i }));
    expect(onComposeChange).toHaveBeenCalledWith(true);
  });
});
