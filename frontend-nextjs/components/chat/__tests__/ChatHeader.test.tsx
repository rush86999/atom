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
});
