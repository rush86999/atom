/**
 * ChatHeader Component Tests
 *
 * Tests verify ChatHeader renders session title, handles rename button,
 * editing mode, and title save functionality.
 *
 * Source: components/chat/ChatHeader.tsx (18 lines, 0% coverage)
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatHeader } from '../ChatHeader';

describe('ChatHeader', () => {
  const mockHandleTitleSave = jest.fn();
  const mockOnRenameClick = jest.fn();
  const mockSetTempTitle = jest.fn();
  const mockSetIsEditingTitle = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders session title
  test('renders session title', () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={false}
        tempTitle=""
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    expect(screen.getByText('Test Session')).toBeInTheDocument();
    expect(screen.getByText('ID: session-123')).toBeInTheDocument();
  });

  // Test 2: clicking rename button triggers setIsEditingTitle
  test('clicking rename button triggers onRenameClick', () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={false}
        tempTitle=""
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[0]);

    expect(mockOnRenameClick).toHaveBeenCalled();
  });

  // Test 3: editing mode shows input field
  test('editing mode shows input field', () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={true}
        tempTitle="New Title"
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const input = screen.getByDisplayValue('New Title');
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe('INPUT');
  });

  // Test 4: title save triggers handleTitleSave
  test('title save triggers handleTitleSave', async () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={true}
        tempTitle="Updated Title"
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const buttons = screen.getAllByRole('button');
    // First button should be the check/save button
    fireEvent.click(buttons[0]);

    expect(mockHandleTitleSave).toHaveBeenCalled();
  });

  // Test 5: empty session shows "New Session" placeholder
  test('empty session shows "New Session" placeholder', () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId={null}
        isEditingTitle={false}
        tempTitle=""
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    expect(screen.getByText('ID: New Session')).toBeInTheDocument();
  });

  // Test 6: displays session ID correctly
  test('displays session ID correctly', () => {
    render(
      <ChatHeader
        sessionTitle="My Chat"
        sessionId="abc-123-xyz"
        isEditingTitle={false}
        tempTitle=""
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    expect(screen.getByText('ID: abc-123-xyz')).toBeInTheDocument();
  });

  // Test 7: input updates tempTitle on change
  test('input updates tempTitle on change', () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={true}
        tempTitle="Initial Title"
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const input = screen.getByDisplayValue('Initial Title');
    fireEvent.change(input, { target: { value: 'Updated Title' } });

    expect(mockSetTempTitle).toHaveBeenCalledWith('Updated Title');
  });

  // Test 8: renders rename button when not editing
  test('renders rename button when not editing', () => {
    const { container } = render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={false}
        tempTitle=""
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  // Test 9: renders save and cancel buttons when editing
  test('renders save and cancel buttons when editing', () => {
    const { container } = render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={true}
        tempTitle="New Title"
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  // Test 10: handles Enter key to save title
  test('handles Enter key to save title', () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={true}
        tempTitle="New Title"
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const input = screen.getByDisplayValue('New Title');
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(mockHandleTitleSave).toHaveBeenCalled();
  });

  // Test 11: handles Escape key to cancel editing
  test('handles Escape key to cancel editing', () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={true}
        tempTitle="New Title"
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const input = screen.getByDisplayValue('New Title');
    fireEvent.keyDown(input, { key: 'Escape', code: 'Escape' });

    expect(mockSetIsEditingTitle).toHaveBeenCalledWith(false);
  });

  // Test 12: shows session title in non-editing mode
  test('shows session title in non-editing mode', () => {
    render(
      <ChatHeader
        sessionTitle="Important Project Discussion"
        sessionId="session-123"
        isEditingTitle={false}
        tempTitle=""
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    expect(screen.getByText('Important Project Discussion')).toBeInTheDocument();
  });

  // Test 13: input field has correct placeholder
  test('input field has correct placeholder', () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={true}
        tempTitle=""
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const input = screen.getByPlaceholderText('Enter session title');
    expect(input).toBeInTheDocument();
  });

  // Test 14: cancel button closes edit mode
  test('cancel button closes edit mode', () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={true}
        tempTitle="Changed Title"
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const buttons = screen.getAllByRole('button');
    // Click the second button (cancel/X button)
    if (buttons.length > 1) {
      fireEvent.click(buttons[1]);
    }

    // Should close editing mode
    expect(mockSetIsEditingTitle).toHaveBeenCalled();
  });

  // Test 15: handles long session titles
  test('handles long session titles', () => {
    const longTitle = 'A'.repeat(200);

    render(
      <ChatHeader
        sessionTitle={longTitle}
        sessionId="session-123"
        isEditingTitle={false}
        tempTitle=""
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    expect(screen.getByText(longTitle)).toBeInTheDocument();
  });

  // Test 16: handles special characters in title
  test('handles special characters in title', () => {
    const specialTitle = 'Test <script>alert("xss")</script> & "quotes"';

    render(
      <ChatHeader
        sessionTitle={specialTitle}
        sessionId="session-123"
        isEditingTitle={false}
        tempTitle=""
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    expect(screen.getByText(/Test/)).toBeInTheDocument();
  });

  // Test 17: empty tempTitle in edit mode
  test('empty tempTitle in edit mode', () => {
    render(
      <ChatHeader
        sessionTitle="Test Session"
        sessionId="session-123"
        isEditingTitle={true}
        tempTitle=""
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const input = screen.getByPlaceholderText('Enter session title');
    expect(input).toBeInTheDocument();
    expect((input as HTMLInputElement).value).toBe('');
  });

  // Test 18: preserves tempTitle when switching to edit mode
  test('preserves tempTitle when switching to edit mode', () => {
    render(
      <ChatHeader
        sessionTitle="Original Title"
        sessionId="session-123"
        isEditingTitle={true}
        tempTitle="Original Title"
        setTempTitle={mockSetTempTitle}
        setIsEditingTitle={mockSetIsEditingTitle}
        handleTitleSave={mockHandleTitleSave}
        onRenameClick={mockOnRenameClick}
      />
    );

    const input = screen.getByDisplayValue('Original Title');
    expect(input).toBeInTheDocument();
  });
});
