/**
 * Manual canvas type switch tests (chat-side CanvasHost).
 *
 * When the agent-chat classifier creates a canvas with the wrong type, the
 * type badge in the panel header becomes a dropdown that retypes the canvas:
 * content converts into the target type's shape, the renderer swaps, and the
 * retype persists via PUT /api/canvas/{id}?canvas_type=…&retype=true (which
 * pins the choice server-side against read-time email coercion).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { CanvasHost } from '../canvas-host';

jest.mock('marked', () => ({
  marked: { parse: jest.fn((s: string) => s) },
}));

jest.mock('@monaco-editor/react', () => ({
  __esModule: true,
  default: ({ value }: any) => (
    <textarea data-testid="canvas-editor" value={value} readOnly />
  ),
}));

jest.mock('@/components/canvas/LineChart', () => ({
  LineChartCanvas: () => <div data-testid="line-chart" />,
}));
jest.mock('@/components/canvas/BarChart', () => ({
  BarChartCanvas: () => <div data-testid="bar-chart" />,
}));
jest.mock('@/components/canvas/PieChart', () => ({
  PieChartCanvas: () => <div data-testid="pie-chart" />,
}));
jest.mock('@/components/canvas/InteractiveForm', () => ({
  InteractiveForm: () => <div data-testid="interactive-form" />,
}));
jest.mock('@/components/canvas/OfficeFileCanvas', () => ({
  OfficeFileCanvas: () => <div data-testid="office-canvas" />,
}));

const mockApiPut = jest.fn().mockResolvedValue({ data: { success: true } });
const mockApiPost = jest.fn().mockResolvedValue({ data: { success: true } });
jest.mock('@/lib/api', () => ({
  apiClient: {
    put: (...args: any[]) => mockApiPut(...args),
    post: (...args: any[]) => mockApiPost(...args),
  },
}));

describe('CanvasHost manual type switch', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const send = (msg: any) => {
    const { rerender } = render(<CanvasHost lastMessage={null} />);
    rerender(<CanvasHost lastMessage={msg} />);
    return rerender;
  };

  test('email → document: swaps the composer for the editor and PUTs a pinned retype', async () => {
    send({
      type: 'canvas:present',
      data: {
        action: 'present',
        component: 'email',
        title: 'Q3 numbers',
        id: 'cv-1',
        data: { to: 'boss@corp.com', subject: 'Q3 numbers', body: 'Here are the numbers.' },
        metadata: { to: 'boss@corp.com', subject: 'Q3 numbers' },
      },
    });

    // Composer renders first.
    expect(screen.getByPlaceholderText('recipient@example.com')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('canvas-type-email'));
    fireEvent.click(screen.getByTestId('canvas-type-option-document'));

    // Editor replaces the composer; the subject is kept as the heading and
    // the body carried verbatim (not the JSON blob of the whole payload).
    const editor = await screen.findByTestId('canvas-editor');
    expect(editor).toHaveValue('# Q3 numbers\n\nHere are the numbers.');
    expect(screen.queryByPlaceholderText('recipient@example.com')).not.toBeInTheDocument();

    // The retype persists with the pin flag.
    await waitFor(() => expect(mockApiPut).toHaveBeenCalledTimes(1));
    const [url, body] = mockApiPut.mock.calls[0];
    expect(String(url)).toContain('/api/canvas/cv-1');
    expect(String(url)).toContain('canvas_type=document');
    expect(String(url)).toContain('retype=true');
    expect(body).toBe('# Q3 numbers\n\nHere are the numbers.');
  });

  test('document → email: opens the composer with the text as the body', async () => {
    send({
      type: 'canvas:present',
      data: {
        action: 'present',
        component: 'document',
        title: 'Follow-up',
        id: 'cv-2',
        data: { content: 'See below for the follow-up notes.' },
      },
    });

    expect(screen.getByTestId('canvas-editor')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('canvas-type-document'));
    fireEvent.click(screen.getByTestId('canvas-type-option-email'));

    const editor = await screen.findByTestId('canvas-editor');
    expect(editor).toHaveValue('See below for the follow-up notes.');
    expect(screen.getByPlaceholderText('recipient@example.com')).toBeInTheDocument();

    await waitFor(() => expect(mockApiPut).toHaveBeenCalledTimes(1));
    const [url, body] = mockApiPut.mock.calls[0];
    expect(String(url)).toContain('canvas_type=email');
    expect(String(url)).toContain('retype=true');
    expect(body).toEqual({
      to: '',
      cc: '',
      subject: 'Follow-up',
      body: 'See below for the follow-up notes.',
    });
  });

  test('specialized canvases keep a plain, non-switchable badge', () => {
    send({
      type: 'canvas:present',
      data: {
        action: 'present',
        component: 'office_word',
        title: 'Contract',
        id: 'cv-3',
        data: { office_file: true, format: 'docx', text: 'Words' },
      },
    });

    const badge = screen.getByTestId('canvas-type-office_word');
    expect(badge.tagName).toBe('SPAN');
    fireEvent.click(badge);
    expect(screen.queryByTestId('canvas-type-menu')).not.toBeInTheDocument();
  });

  test('an unsaved canvas (no id) switches locally without a PUT', async () => {
    send({
      type: 'canvas:present',
      data: {
        action: 'present',
        component: 'markdown',
        title: 'Scratch',
        data: 'Some scratch notes.',
      },
    });

    fireEvent.click(screen.getByTestId('canvas-type-markdown'));
    fireEvent.click(screen.getByTestId('canvas-type-option-code'));

    const editor = await screen.findByTestId('canvas-editor');
    expect(editor).toHaveValue('Some scratch notes.');
    // Unsaved → the switch stays local; Save is the persist path.
    expect(mockApiPut).not.toHaveBeenCalled();
    expect(screen.getByText('Save Changes')).toBeInTheDocument();
  });
});
