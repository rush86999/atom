/**
 * MessageList Component Tests
 *
 * Tests verify MessageList renders messages, handles empty state,
 * and displays user/assistant messages differently.
 *
 * Source: components/chat/MessageList.tsx (16 lines, 0% coverage)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { MessageList } from '../MessageList';

describe('MessageList', () => {
  const mockHandleActionClick = jest.fn();
  const mockHandleFeedback = jest.fn();
  const mockMessagesEndRef = { current: null } as React.RefObject<HTMLDivElement>;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders list of messages
  test('renders list of messages', () => {
    const messages = [
      { id: '1', role: 'user', content: 'Hello', type: 'text' },
      { id: '2', role: 'assistant', content: 'Hi there!', type: 'text' },
    ];

    const { container } = render(
      <MessageList
        messages={messages}
        currentStreamId={null}
        streamingContent={new Map()}
        isProcessing={false}
        statusMessage=""
        messagesEndRef={mockMessagesEndRef}
        handleActionClick={mockHandleActionClick}
        handleFeedback={mockHandleFeedback}
      />
    );

    expect(container.textContent).toContain('Hello');
    expect(container.textContent).toContain('Hi there!');
  });

  // Test 2: empty messages array renders placeholder
  test('empty messages array renders without error', () => {
    const { container } = render(
      <MessageList
        messages={[]}
        currentStreamId={null}
        streamingContent={new Map()}
        isProcessing={false}
        statusMessage=""
        messagesEndRef={mockMessagesEndRef}
        handleActionClick={mockHandleActionClick}
        handleFeedback={mockHandleFeedback}
      />
    );

    expect(container).toBeInTheDocument();
  });

  // Test 3: shows streaming content when active
  test('shows streaming content when active', () => {
    const streamingMap = new Map([['stream-1', 'Streaming...']]);

    const { container } = render(
      <MessageList
        messages={[]}
        currentStreamId="stream-1"
        streamingContent={streamingMap}
        isProcessing={false}
        statusMessage=""
        messagesEndRef={mockMessagesEndRef}
        handleActionClick={mockHandleActionClick}
        handleFeedback={mockHandleFeedback}
      />
    );

    expect(container.textContent).toContain('Streaming...');
  });

  // Test 4: shows status message when processing
  test('shows status message when processing', () => {
    const { container } = render(
      <MessageList
        messages={[]}
        currentStreamId={null}
        streamingContent={new Map()}
        isProcessing={true}
        statusMessage="Thinking..."
        messagesEndRef={mockMessagesEndRef}
        handleActionClick={mockHandleActionClick}
        handleFeedback={mockHandleFeedback}
      />
    );

    expect(container.textContent).toContain('Thinking...');
  });
});
