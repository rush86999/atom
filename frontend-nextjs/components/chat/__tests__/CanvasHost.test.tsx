/**
 * CanvasHost Component Tests
 *
 * Tests verify CanvasHost renders and reacts to canvas:present, canvas:update,
 * and action:close message types. Covers email metadata, sheet data, and save behavior.
 *
 * Source: components/chat/canvas-host.tsx (93 lines, 0% coverage)
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { CanvasHost } from '../canvas-host';

// Mock marked to avoid ESM import issues
jest.mock('marked', () => ({
  marked: {
    parse: jest.fn((s: string) => s),
  },
}));

// Mock Monaco editor to avoid heavy import
jest.mock('@monaco-editor/react', () => ({
  __esModule: true,
  default: ({ value, onChange }: any) => (
    <div data-testid="mock-editor">
      <textarea
        data-testid="editor-content"
        defaultValue={value}
        onChange={(e) => onChange?.(e.target.value)}
      />
    </div>
  ),
}));

// Use the mockFetch that setup.ts exports on global scope
const getMockFetch = () => (global as any).mockFetch as jest.Mock;

describe('CanvasHost', () => {
  beforeEach(() => {
    // jest config has clearMocks, resetMocks, restoreMocks so we need to re-setup fetch spy
    jest.spyOn(global, 'fetch').mockResolvedValue(
      (global as any).createMockResponse() as any
    );
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  // Test 1: renders nothing when lastMessage is null
  test('renders nothing when lastMessage is null', () => {
    const { container } = render(<CanvasHost lastMessage={null} />);
    expect(container.innerHTML).toBe('');
  });

  // Test 2: renders markdown canvas on canvas:present message
  test('renders markdown canvas on canvas:present message', () => {
    const message = {
      type: 'canvas:present',
      data: {
        component: 'markdown',
        title: 'Test Doc',
        data: { content: '# Hello World' },
      },
    };

    render(<CanvasHost lastMessage={message} />);

    expect(screen.getByText('Test Doc')).toBeInTheDocument();
    expect(screen.getByText('markdown')).toBeInTheDocument();
  });

  // Test 3: renders code component on eval type
  test('renders code component on eval type', () => {
    const message = {
      type: 'canvas:update',
      data: {
        component: 'eval',
        title: 'Code',
        data: { content: 'print("hello")' },
      },
    };

    render(<CanvasHost lastMessage={message} />);

    expect(screen.getByText('Code')).toBeInTheDocument();
    expect(screen.getByText('code')).toBeInTheDocument();
  });

  // Test 4: closes canvas on action:close
  test('closes canvas on action:close', () => {
    const { rerender } = render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: { component: 'markdown', title: 'Test', data: { content: 'Hello' } },
        }}
      />
    );

    expect(screen.getByText('Test')).toBeInTheDocument();

    // Rerender with close action
    rerender(
      <CanvasHost
        lastMessage={{
          type: 'canvas:update',
          data: { action: 'close' },
        }}
      />
    );

    expect(screen.queryByText('Test')).not.toBeInTheDocument();
  });

  // Test 5: handles email component metadata
  test('handles email component metadata', () => {
    const message = {
      type: 'canvas:present',
      data: {
        component: 'email',
        title: 'New Email',
        data: { content: 'Hello via email' },
        metadata: { to: 'test@example.com', subject: 'Test Subject' },
      },
    };

    render(<CanvasHost lastMessage={message} />);

    expect(screen.getByText('New Email')).toBeInTheDocument();
    expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Test Subject')).toBeInTheDocument();
  });

  // Test 6: handles sheet component data
  test('handles sheet component data with rows', () => {
    const message = {
      type: 'canvas:present',
      data: {
        component: 'sheet',
        title: 'Sheet 1',
        data: { rows: [['a', 'b'], ['c', 'd']] },
      },
    };

    render(<CanvasHost lastMessage={message} />);

    expect(screen.getByText('Sheet 1')).toBeInTheDocument();
    expect(screen.getByText('sheet')).toBeInTheDocument();
    // Sheet has input fields for each cell
    expect(screen.getByDisplayValue('a')).toBeInTheDocument();
    expect(screen.getByDisplayValue('b')).toBeInTheDocument();
  });

  // Test 7: handleSave triggers save API call
  test('handleSave triggers save API call', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch').mockResolvedValue(
      (global as any).createMockResponse({
        ok: true,
        json: async () => ({ id: 'artifact-1', version: 2 }),
      }) as any
    );

    render(
      <CanvasHost
        lastMessage={{
          type: 'canvas:present',
          data: {
            component: 'sheet',
            title: 'Sheet',
            data: { rows: [['x', 'y']] },
          },
        }}
      />
    );

    const saveButton = screen.getByText('Save Changes');
    expect(saveButton).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(saveButton);
    });

    expect(fetchSpy).toHaveBeenCalled();
    const callUrl = fetchSpy.mock.calls[0][0];
    expect(callUrl).toContain('/api/artifacts');
  });

  // Test 8: handleSave does nothing when state is null
  test('handleSave does nothing when state is null', () => {
    const fetchSpy = jest.spyOn(global, 'fetch');

    // No canvas message passed - state remains null
    render(<CanvasHost lastMessage={null} />);

    // Save button should not exist since canvas is not open
    expect(screen.queryByText('Save Changes')).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
