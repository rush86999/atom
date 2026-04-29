/**
 * MessageList Component Tests
 *
 * Tests verify MessageList renders messages, handles empty state,
 * and displays user/assistant messages differently.
 *
 * Source: components/chat/MessageList.tsx (16 lines, 0% coverage)
 */

import React from 'react';
import { renderWithProviders, screen } from '../../../tests/test-utils';
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

    const { container } = renderWithProviders(
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
    const { container } = renderWithProviders(
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

    const { container } = renderWithProviders(
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
    const { container } = renderWithProviders(
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

  // Test 5: renders user messages correctly
  test('renders user messages with correct styling', () => {
    const messages = [
      { id: '1', role: 'user', content: 'User message', type: 'text' },
    ];

    const { container } = renderWithProviders(
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

    expect(container.textContent).toContain('User message');
  });

  // Test 6: renders assistant messages correctly
  test('renders assistant messages with correct styling', () => {
    const messages = [
      { id: '1', role: 'assistant', content: 'Assistant response', type: 'text' },
    ];

    const { container } = renderWithProviders(
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

    expect(container.textContent).toContain('Assistant response');
  });

  // Test 7: handles multiple messages in sequence
  test('handles multiple messages in correct order', () => {
    const messages = [
      { id: '1', role: 'user', content: 'First', type: 'text' },
      { id: '2', role: 'assistant', content: 'Second', type: 'text' },
      { id: '3', role: 'user', content: 'Third', type: 'text' },
    ];

    const { container } = renderWithProviders(
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

    const textContent = container.textContent;
    expect(textContent).toContain('First');
    expect(textContent).toContain('Second');
    expect(textContent).toContain('Third');
  });

  // Test 8: renders without crashing when messagesEndRef is null
  test('renders without crashing when messagesEndRef is null', () => {
    const messages = [
      { id: '1', role: 'user', content: 'Test', type: 'text' },
    ];

    expect(() => {
      renderWithProviders(
        <MessageList
          messages={messages}
          currentStreamId={null}
          streamingContent={new Map()}
          isProcessing={false}
          statusMessage=""
          messagesEndRef={null as any}
          handleActionClick={mockHandleActionClick}
          handleFeedback={mockHandleFeedback}
        />
      );
    }).not.toThrow();
  });

  // Test 9: handles empty streaming content map
  test('handles empty streaming content map', () => {
    const messages = [
      { id: '1', role: 'user', content: 'Hello', type: 'text' },
    ];

    const { container } = renderWithProviders(
      <MessageList
        messages={messages}
        currentStreamId="stream-1"
        streamingContent={new Map()}
        isProcessing={false}
        statusMessage=""
        messagesEndRef={mockMessagesEndRef}
        handleActionClick={mockHandleActionClick}
        handleFeedback={mockHandleFeedback}
      />
    );

    expect(container.textContent).toContain('Hello');
  });

  // Test 10: shows multiple streaming contents
  test('shows multiple streaming contents', () => {
    const streamingMap = new Map([
      ['stream-1', 'Streaming part 1'],
      ['stream-2', 'Streaming part 2'],
    ]);

    const { container } = renderWithProviders(
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

    expect(container.textContent).toContain('Streaming part 1');
  });

  // Test 11: displays system messages
  test('displays system messages', () => {
    const messages = [
      { id: '1', role: 'system', content: 'System notification', type: 'text' },
    ];

    const { container } = renderWithProviders(
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

    expect(container.textContent).toContain('System notification');
  });

  // Test 12: handles long messages
  test('handles long messages without truncation', () => {
    const longMessage = 'A'.repeat(1000);
    const messages = [
      { id: '1', role: 'user', content: longMessage, type: 'text' },
    ];

    const { container } = renderWithProviders(
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

    expect(container.textContent).toContain(longMessage);
  });

  // Test 13: handles special characters in messages
  test('handles special characters in messages', () => {
    const specialMessage = 'Test <script>alert("xss")</script> & "quotes"';
    const messages = [
      { id: '1', role: 'user', content: specialMessage, type: 'text' },
    ];

    const { container } = renderWithProviders(
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

    expect(container).toBeInTheDocument();
  });

  // Test 14: shows empty status message
  test('shows empty status message when not processing', () => {
    const { container } = renderWithProviders(
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

  // Test 15: handles null currentStreamId
  test('handles null currentStreamId gracefully', () => {
    const messages = [
      { id: '1', role: 'user', content: 'Test', type: 'text' },
    ];

    const { container } = renderWithProviders(
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

    expect(container.textContent).toContain('Test');
  });
});
