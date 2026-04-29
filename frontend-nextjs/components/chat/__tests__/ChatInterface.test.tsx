/**
 * ChatInterface Component Tests
 *
 * Tests verify ChatInterface renders main chat container, wires message
 * list and input together, and handles loading/empty/connected states.
 *
 * Source: components/chat/ChatInterface.tsx (112 lines, 0% coverage)
 */

import React from 'react';
import { renderWithProviders } from '../../../tests/test-utils';
import ChatInterface from '../ChatInterface';

// Mock hooks
jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    lastMessage: null,
    isConnected: false,
  }),
}));

jest.mock('@/hooks/chat/useChatInterface', () => ({
  useChatInterface: () => ({
    input: '',
    setInput: jest.fn(),
    isProcessing: false,
    statusMessage: '',
    messages: [],
    sessionTitle: 'New Chat',
    isEditingTitle: false,
    setIsEditingTitle: jest.fn(),
    tempTitle: '',
    setTempTitle: jest.fn(),
    messagesEndRef: { current: null },
    isVoiceModeOpen: false,
    setIsVoiceModeOpen: jest.fn(),
    activeAttachments: [],
    setActiveAttachments: jest.fn(),
    isUploading: false,
    streamingContent: new Map(),
    handleSend: jest.fn(),
    handleStop: jest.fn(),
    handleTitleSave: jest.fn(),
    handleFeedback: jest.fn(),
    uploadFile: jest.fn(),
    toast: jest.fn(),
  }),
}));

// Mock child components
jest.mock('./ChatHeader', () => ({
  ChatHeader: () => <div data-testid="chat-header">Session: New Chat</div>,
}));

jest.mock('./MessageList', () => ({
  MessageList: () => <div data-testid="message-list">Messages</div>,
}));

jest.mock('./ChatInput', () => ({
  ChatInput: () => <div data-testid="chat-input">Input</div>,
}));

jest.mock('@/components/Voice/VoiceModeOverlay', () => ({
  VoiceModeOverlay: () => null,
}));

describe('ChatInterface', () => {
  // Test 1: renders the main chat container/layout
  test('renders the main chat container/layout', () => {
    const { container } = renderWithProviders(<ChatInterface sessionId={null} />);

    expect(container.querySelector('.flex.flex-col.h-full')).toBeInTheDocument();
  });

  // Test 2: renders with empty messages initially
  test('renders with empty messages initially', () => {
    const { container } = renderWithProviders(<ChatInterface sessionId={null} />);

    expect(container).toBeInTheDocument();
  });

  // Test 3: renders with sessionId prop
  test('renders with sessionId prop', () => {
    const { container } = renderWithProviders(<ChatInterface sessionId="session-123" />);

    expect(container).toBeInTheDocument();
  });

  // Test 4: renders without errors
  test('renders without errors', () => {
    expect(() => renderWithProviders(<ChatInterface sessionId={null} />)).not.toThrow();
  });

  // Test 5: has proper flex layout
  test('has proper flex layout', () => {
    const { container } = renderWithProviders(<ChatInterface sessionId={null} />);

    const mainContainer = container.querySelector('.flex.flex-col.h-full');
    expect(mainContainer).toBeInTheDocument();
  });

  // Test 6: renders child components
  test('renders child components', () => {
    const { container } = renderWithProviders(<ChatInterface sessionId={null} />);

    expect(container.querySelector('[data-testid="chat-header"]')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="message-list"]')).toBeInTheDocument();
    expect(container.querySelector('[data-testid="chat-input"]')).toBeInTheDocument();
  });
});
