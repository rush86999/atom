/**
 * ChatInput Component Tests
 *
 * Tests verify ChatInput renders input field, handles upload indicator,
 * attachment chips, send/stop buttons, and keyboard interactions.
 *
 * Source: components/chat/ChatInput.tsx (30 lines, 0% coverage)
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatInput } from '../ChatInput';

describe('ChatInput', () => {
  const mockHandleSend = jest.fn();
  const mockHandleStop = jest.fn();
  const mockSetInput = jest.fn();
  const mockSetActiveAttachments = jest.fn();
  const mockUploadFile = jest.fn();
  const mockSetIsVoiceModeOpen = jest.fn();
  const mockToast = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders input field and send button
  test('renders input field and send button', () => {
    const { container } = render(
      <ChatInput
        input=""
        setInput={mockSetInput}
        isProcessing={false}
        isUploading={false}
        activeAttachments={[]}
        setActiveAttachments={mockSetActiveAttachments}
        handleSend={mockHandleSend}
        handleStop={mockHandleStop}
        setIsVoiceModeOpen={mockSetIsVoiceModeOpen}
        uploadFile={mockUploadFile}
        toast={mockToast}
        messagesCount={0}
      />
    );

    expect(screen.getByPlaceholderText('Type a message...')).toBeInTheDocument();
    expect(container.querySelector('button')).toBeInTheDocument();
  });

  // Test 2: shows uploading indicator when isUploading=true
  test('shows uploading indicator when isUploading=true', () => {
    render(
      <ChatInput
        input=""
        setInput={mockSetInput}
        isProcessing={false}
        isUploading={true}
        activeAttachments={[]}
        setActiveAttachments={mockSetActiveAttachments}
        handleSend={mockHandleSend}
        handleStop={mockHandleStop}
        setIsVoiceModeOpen={mockSetIsVoiceModeOpen}
        uploadFile={mockUploadFile}
        toast={mockToast}
        messagesCount={0}
      />
    );

    expect(screen.getByText('Uploading file...')).toBeInTheDocument();
  });

  // Test 3: shows attachment chips when activeAttachments is non-empty
  test('shows attachment chips when activeAttachments is non-empty', () => {
    const attachments = [
      { id: '1', title: 'test.pdf' },
      { id: '2', title: 'image.png' },
    ];

    render(
      <ChatInput
        input=""
        setInput={mockSetInput}
        isProcessing={false}
        isUploading={false}
        activeAttachments={attachments}
        setActiveAttachments={mockSetActiveAttachments}
        handleSend={mockHandleSend}
        handleStop={mockHandleStop}
        setIsVoiceModeOpen={mockSetIsVoiceModeOpen}
        uploadFile={mockUploadFile}
        toast={mockToast}
        messagesCount={0}
      />
    );

    expect(screen.getByText('test.pdf')).toBeInTheDocument();
    expect(screen.getByText('image.png')).toBeInTheDocument();
  });

  // Test 4: clicking send button triggers handleSend
  test('clicking send button triggers handleSend', async () => {
    render(
      <ChatInput
        input="Hello world"
        setInput={mockSetInput}
        isProcessing={false}
        isUploading={false}
        activeAttachments={[]}
        setActiveAttachments={mockSetActiveAttachments}
        handleSend={mockHandleSend}
        handleStop={mockHandleStop}
        setIsVoiceModeOpen={mockSetIsVoiceModeOpen}
        uploadFile={mockUploadFile}
        toast={mockToast}
        messagesCount={0}
      />
    );

    const buttons = screen.getAllByRole('button');
    const sendButton = buttons.find(btn => !btn.disabled);
    if (sendButton) {
      fireEvent.click(sendButton);
    }

    expect(mockHandleSend).toHaveBeenCalled();
  });

  // Test 5: clicking stop button triggers handleStop when processing
  test('clicking stop button triggers handleStop when processing', () => {
    render(
      <ChatInput
        input=""
        setInput={mockSetInput}
        isProcessing={true}
        isUploading={false}
        activeAttachments={[]}
        setActiveAttachments={mockSetActiveAttachments}
        handleSend={mockHandleSend}
        handleStop={mockHandleStop}
        setIsVoiceModeOpen={mockSetIsVoiceModeOpen}
        uploadFile={mockUploadFile}
        toast={mockToast}
        messagesCount={0}
      />
    );

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[buttons.length - 1]);

    expect(mockHandleStop).toHaveBeenCalled();
  });

  // Test 6: clicking remove on attachment chip removes it
  test('clicking remove on attachment chip removes it', () => {
    const attachments = [{ id: '1', title: 'test.pdf' }];

    render(
      <ChatInput
        input=""
        setInput={mockSetInput}
        isProcessing={false}
        isUploading={false}
        activeAttachments={attachments}
        setActiveAttachments={mockSetActiveAttachments}
        handleSend={mockHandleSend}
        handleStop={mockHandleStop}
        setIsVoiceModeOpen={mockSetIsVoiceModeOpen}
        uploadFile={mockUploadFile}
        toast={mockToast}
        messagesCount={0}
      />
    );

    // Find the close button in attachment chips
    const buttons = screen.getAllByRole('button');
    const closeButton = buttons.find(btn => btn.querySelector('svg'));
    if (closeButton) {
      fireEvent.click(closeButton);
    }

    expect(mockSetActiveAttachments).toHaveBeenCalled();
  });

  // Test 7: empty attachments renders no chips
  test('empty attachments renders no chips', () => {
    render(
      <ChatInput
        input=""
        setInput={mockSetInput}
        isProcessing={false}
        isUploading={false}
        activeAttachments={[]}
        setActiveAttachments={mockSetActiveAttachments}
        handleSend={mockHandleSend}
        handleStop={mockHandleStop}
        setIsVoiceModeOpen={mockSetIsVoiceModeOpen}
        uploadFile={mockUploadFile}
        toast={mockToast}
        messagesCount={0}
      />
    );

    // Should not find any attachment titles
    expect(screen.queryByText('test.pdf')).not.toBeInTheDocument();
  });

  // Test 8: shows disclaimer text
  test('shows disclaimer text', () => {
    render(
      <ChatInput
        input=""
        setInput={mockSetInput}
        isProcessing={false}
        isUploading={false}
        activeAttachments={[]}
        setActiveAttachments={mockSetActiveAttachments}
        handleSend={mockHandleSend}
        handleStop={mockHandleStop}
        setIsVoiceModeOpen={mockSetIsVoiceModeOpen}
        uploadFile={mockUploadFile}
        toast={mockToast}
        messagesCount={0}
      />
    );

    expect(screen.getByText(/AI can make mistakes/i)).toBeInTheDocument();
  });
});
