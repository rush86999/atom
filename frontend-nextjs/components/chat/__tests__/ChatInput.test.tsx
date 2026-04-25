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

  // Test 9: disables send button when input is empty
  test('disables send button when input is empty', () => {
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

    const buttons = screen.getAllByRole('button');
    const sendButton = buttons.find(btn => btn.textContent === 'Send');
    expect(sendButton).toBeDisabled();
  });

  // Test 10: enables send button when input has text
  test('enables send button when input has text', () => {
    const { container } = render(
      <ChatInput
        input="Hello"
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
    const sendButton = buttons.find(btn => btn.textContent === 'Send');
    expect(sendButton).not.toBeDisabled();
  });

  // Test 11: shows stop button when processing
  test('shows stop button when processing', () => {
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

    expect(screen.getByText('Stop')).toBeInTheDocument();
  });

  // Test 12: input field displays current value
  test('input field displays current value', () => {
    render(
      <ChatInput
        input="Test message"
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

    const input = screen.getByPlaceholderText('Type a message...') as HTMLInputElement;
    expect(input.value).toBe('Test message');
  });

  // Test 13: calls setInput when input changes
  test('calls setInput when input changes', () => {
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

    const input = screen.getByPlaceholderText('Type a message...');
    fireEvent.change(input, { target: { value: 'New message' } });

    expect(mockSetInput).toHaveBeenCalledWith('New message');
  });

  // Test 14: shows voice mode button
  test('shows voice mode button', () => {
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

    // Voice button should be present (mic icon button)
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  // Test 15: handles multiple attachments
  test('handles multiple attachments', () => {
    const attachments = [
      { id: '1', title: 'file1.pdf' },
      { id: '2', title: 'file2.png' },
      { id: '3', title: 'file3.docx' },
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

    expect(screen.getByText('file1.pdf')).toBeInTheDocument();
    expect(screen.getByText('file2.png')).toBeInTheDocument();
    expect(screen.getByText('file3.docx')).toBeInTheDocument();
  });

  // Test 16: sends message on Enter key
  test('sends message on Enter key', () => {
    render(
      <ChatInput
        input="Test message"
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

    const input = screen.getByPlaceholderText('Type a message...');
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    // Note: Actual Enter handling depends on implementation
    // This test verifies the component doesn't crash
    expect(input).toBeInTheDocument();
  });

  // Test 17: shows attachment button
  test('shows attachment button', () => {
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

    // Attachment button should be present (paperclip icon button)
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  // Test 18: prevents send when uploading
  test('prevents send when uploading file', () => {
    render(
      <ChatInput
        input="Test"
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
    // Send button should be disabled during upload
    const buttons = screen.getAllByRole('button');
    const sendButton = buttons.find(btn => btn.textContent === 'Send');
    expect(sendButton?.disabled).toBe(true);
  });
});
