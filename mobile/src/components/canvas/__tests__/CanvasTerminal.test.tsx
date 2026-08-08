/**
 * CanvasTerminal Component Tests
 *
 * Testing suite for CanvasTerminal covering:
 * - Output line rendering by type (stdout/stderr/command/system)
 * - ANSI color parsing
 * - Timestamps, empty state, maxLines trimming
 * - Font size controls (increase/decrease/reset via menu)
 * - Wrap toggle, copy-all to clipboard, clear
 * - Command input: submit, disabled send, keyboard history navigation
 * - Auto-scroll on new output
 * - Light theme colors
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { ScrollView } from 'react-native';
import { Provider } from 'react-native-paper';
import { CanvasTerminal } from '../CanvasTerminal';

// Mock dependencies
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: {
    Light: 'light',
    Medium: 'medium',
    Heavy: 'heavy',
  },
}));

jest.mock('expo-clipboard', () => ({
  setStringAsync: jest.fn().mockResolvedValue(undefined),
  getStringAsync: jest.fn().mockResolvedValue(''),
}), { virtual: true });

const mockSetStringAsync = require('expo-clipboard').setStringAsync;

// CanvasTerminal renders a paper <Portal> (Dialog + Menu), which requires
// the paper Provider in the tree.
const renderTerminal = (el: React.ReactElement) =>
  render(
    <Provider>{el}</Provider>
  );

const output = [
  { type: 'stdout', content: 'hello world' },
  { type: 'stderr', content: 'oops' },
  { type: 'command', content: 'npm test' },
  { type: 'system', content: 'session started', timestamp: '12:00:01' },
];

const textStyle = (textEl: any) => {
  const style = textEl.props.style;
  return Array.isArray(style) ? style[1] : style;
};

describe('CanvasTerminal Component', () => {
  describe('Rendering', () => {
    test('renders output lines for each type', () => {
      const { getByText } = renderTerminal(<CanvasTerminal output={output} />);

      expect(getByText('hello world')).toBeTruthy();
      expect(getByText('oops')).toBeTruthy();
      expect(getByText('npm test')).toBeTruthy();
      expect(getByText('session started')).toBeTruthy();
      expect(getByText('Terminal')).toBeTruthy();
    });

    test('applies type-specific colors in dark theme', () => {
      const { getByText } = renderTerminal(<CanvasTerminal output={output} />);

      expect(textStyle(getByText('hello world')).color).toBe('#e5e5e5'); // stdout
      expect(textStyle(getByText('oops')).color).toBe('#f14c4c');        // stderr
      expect(textStyle(getByText('npm test')).color).toBe('#0dbc79');    // command
      expect(textStyle(getByText('session started')).color).toBe('#2472c8'); // system
    });

    test('applies light theme colors when darkTheme is false', () => {
      const { getByText } = renderTerminal(<CanvasTerminal output={output} darkTheme={false} />);

      expect(textStyle(getByText('hello world')).color).toBe('#000000');
      expect(textStyle(getByText('oops')).color).toBe('#d32f2f');
      expect(textStyle(getByText('npm test')).color).toBe('#388e3c');
    });

    test('renders timestamp prefix when present', () => {
      const { getByText } = renderTerminal(<CanvasTerminal output={output} />);
      expect(getByText(/\[12:00:01\]/)).toBeTruthy();
    });

    test('renders empty state when there is no output', () => {
      const { getByText } = renderTerminal(<CanvasTerminal output={[]} />);
      expect(getByText('No output yet...')).toBeTruthy();
    });

    test('trims output to maxLines keeping the newest lines', () => {
      const longOutput = Array.from({ length: 5 }, (_, i) => ({
        type: 'stdout' as const,
        content: `line-${i + 1}`,
      }));
      const { getByText, queryByText } = renderTerminal(
        <CanvasTerminal output={longOutput} maxLines={3} />
      );

      expect(queryByText('line-1')).toBeNull();
      expect(queryByText('line-2')).toBeNull();
      expect(getByText('line-3')).toBeTruthy();
      expect(getByText('line-5')).toBeTruthy();
    });
  });

  describe('ANSI colors', () => {
    test('parses ANSI color codes into colored segments', () => {
      const { getByText } = renderTerminal(
        <CanvasTerminal output={[{ type: 'stdout', content: '\x1b[31mred\x1b[32m green' }]} />
      );

      expect(textStyle(getByText('red')).color).toBe('#cd3131');
      expect(textStyle(getByText(' green')).color).toBe('#0dbc79');
    });

    test('handles ANSI reset code', () => {
      const { getByText } = renderTerminal(
        <CanvasTerminal output={[{ type: 'stdout', content: '\x1b[31mred\x1b[0m plain' }]} />
      );

      expect(textStyle(getByText('red')).color).toBe('#cd3131');
      expect(textStyle(getByText(' plain')).color).toBe('#e5e5e5'); // fallback to line color
    });

    test('renders plain text without ANSI codes unchanged', () => {
      const { getByText } = renderTerminal(
        <CanvasTerminal output={[{ type: 'stdout', content: 'just text' }]} />
      );
      expect(getByText('just text')).toBeTruthy();
    });
  });

  describe('Font controls', () => {
    test('increases font size', () => {
      const { getByText, getByTestId } = renderTerminal(<CanvasTerminal output={output} />);

      expect(textStyle(getByText('hello world')).fontSize).toBe(13);

      fireEvent.press(getByTestId('icon-format-font-size-increase'));

      expect(textStyle(getByText('hello world')).fontSize).toBe(14);
    });

    test('caps font size at 24', () => {
      const { getByText, getByTestId } = renderTerminal(<CanvasTerminal output={output} />);

      for (let i = 0; i < 15; i++) {
        fireEvent.press(getByTestId('icon-format-font-size-increase'));
      }

      expect(textStyle(getByText('hello world')).fontSize).toBe(24);
    });

    test('decreases font size with a floor of 10', () => {
      const { getByText, getByTestId } = renderTerminal(<CanvasTerminal output={output} />);

      for (let i = 0; i < 5; i++) {
        fireEvent.press(getByTestId('icon-format-font-size-decrease'));
      }

      expect(textStyle(getByText('hello world')).fontSize).toBe(10);
    });

    test('resets font size via the menu', () => {
      const { getByText, getByTestId } = renderTerminal(<CanvasTerminal output={output} />);

      fireEvent.press(getByTestId('icon-format-font-size-increase'));
      expect(textStyle(getByText('hello world')).fontSize).toBe(14);

      fireEvent.press(getByTestId('icon-dots-vertical'));
      fireEvent.press(getByText('Reset Font'));

      expect(textStyle(getByText('hello world')).fontSize).toBe(13);
    });

    test('adjusts font size and wrap via the menu items', () => {
      const { getByText, getByTestId } = renderTerminal(<CanvasTerminal output={output} />);

      fireEvent.press(getByTestId('icon-dots-vertical'));
      fireEvent.press(getByText('Increase Font'));
      expect(textStyle(getByText('hello world')).fontSize).toBe(14);

      fireEvent.press(getByTestId('icon-dots-vertical'));
      fireEvent.press(getByText('Decrease Font'));
      expect(textStyle(getByText('hello world')).fontSize).toBe(13);

      fireEvent.press(getByTestId('icon-dots-vertical'));
      fireEvent.press(getByText('Disable Wrap'));
      expect(getByText('hello world').props.style[2]).toBeTruthy();
    });

    test('copies all output via the menu item', async () => {
      const { getByText, getByTestId } = renderTerminal(<CanvasTerminal output={output} />);

      fireEvent.press(getByTestId('icon-dots-vertical'));
      fireEvent.press(getByText('Copy All'));

      await waitFor(() => {
        expect(mockSetStringAsync).toHaveBeenCalledWith(
          'hello world\noops\nnpm test\n[12:00:01] session started'
        );
      });
    });
  });

  describe('Wrap and copy', () => {
    test('toggles text wrap', () => {
      const { getByText, getByTestId } = renderTerminal(<CanvasTerminal output={output} />);

      // Default: wrapped (no noWrap style — third style slot is `false`)
      const wrappedText = getByText('hello world');
      expect(wrappedText.props.style[2]).toBeFalsy();

      fireEvent.press(getByTestId('icon-wrap-text'));

      const unwrappedText = getByText('hello world');
      expect(unwrappedText.props.style[2]).toBeTruthy(); // noWrap applied
    });

    test('copies all output to clipboard and shows confirmation dialog', async () => {
      const { getByText, getByTestId } = renderTerminal(<CanvasTerminal output={output} />);

      fireEvent.press(getByTestId('icon-content-copy'));

      await waitFor(() => {
        expect(mockSetStringAsync).toHaveBeenCalledWith(
          'hello world\noops\nnpm test\n[12:00:01] session started'
        );
      });

      await waitFor(() => {
        expect(getByText('All output copied to clipboard')).toBeTruthy();
      });
    });

    test('copies timestamped lines with bracket prefixes', async () => {
      const { getByTestId } = renderTerminal(
        <CanvasTerminal output={[{ type: 'system', content: 'boot', timestamp: 'T1' }]} />
      );

      fireEvent.press(getByTestId('icon-content-copy'));

      await waitFor(() => {
        expect(mockSetStringAsync).toHaveBeenCalledWith('[T1] boot');
      });
    });

    test('dismisses the copied confirmation dialog with OK', async () => {
      const { getByText, getByTestId, getByRole, UNSAFE_getByType } = renderTerminal(<CanvasTerminal output={output} />);

      fireEvent.press(getByTestId('icon-content-copy'));

      await waitFor(() => {
        expect(getByText('All output copied to clipboard')).toBeTruthy();
      });
      const { Dialog } = require('react-native-paper');
      expect(UNSAFE_getByType(Dialog).props.visible).toBe(true);

      fireEvent.press(getByRole('button', { name: 'OK' }));

      expect(UNSAFE_getByType(Dialog).props.visible).toBe(false);
    });
  });

  describe('Command input', () => {
    const inputProps = {
      enableInput: true,
      readonly: false,
      onCommand: jest.fn(),
    };

    test('submits command and clears the input', () => {
      const onCommand = jest.fn();
      const { getByPlaceholderText, getByTestId } = renderTerminal(
        <CanvasTerminal output={[]} enableInput readonly={false} onCommand={onCommand} />
      );

      const input = getByPlaceholderText('Type a command...');
      fireEvent.changeText(input, 'ls -la');
      fireEvent(getByTestId('icon-send'), 'press');

      expect(onCommand).toHaveBeenCalledWith('ls -la');
      expect(input.props.value).toBe('');
    });

    test('submits command via onSubmitEditing', () => {
      const onCommand = jest.fn();
      const { getByPlaceholderText } = renderTerminal(
        <CanvasTerminal output={[]} enableInput readonly={false} onCommand={onCommand} />
      );

      const input = getByPlaceholderText('Type a command...');
      fireEvent.changeText(input, 'echo hi');
      fireEvent(input, 'submitEditing');

      expect(onCommand).toHaveBeenCalledWith('echo hi');
    });

    test('send button is inert when input is empty', () => {
      const onCommand = jest.fn();
      const { getByTestId } = renderTerminal(
        <CanvasTerminal output={[]} enableInput readonly={false} onCommand={onCommand} />
      );

      fireEvent.press(getByTestId('icon-send'));

      expect(onCommand).not.toHaveBeenCalled();
    });

    test('does not call onCommand for whitespace-only input', () => {
      const onCommand = jest.fn();
      const { getByPlaceholderText } = renderTerminal(
        <CanvasTerminal output={[]} enableInput readonly={false} onCommand={onCommand} />
      );

      fireEvent.changeText(getByPlaceholderText('Type a command...'), '   ');
      fireEvent(getByPlaceholderText('Type a command...'), 'submitEditing');

      expect(onCommand).not.toHaveBeenCalled();
    });

    test('navigates command history with arrow keys', () => {
      const onCommand = jest.fn();
      const { getByPlaceholderText } = renderTerminal(
        <CanvasTerminal output={[]} enableInput readonly={false} onCommand={onCommand} />
      );

      const input = getByPlaceholderText('Type a command...');

      fireEvent.changeText(input, 'first');
      fireEvent(input, 'submitEditing');
      fireEvent.changeText(input, 'second');
      fireEvent(input, 'submitEditing');

      // ArrowUp: newest command
      fireEvent(input, 'keyPress', { nativeEvent: { key: 'ArrowUp' } });
      expect(input.props.value).toBe('second');

      // ArrowUp again: older command
      fireEvent(input, 'keyPress', { nativeEvent: { key: 'ArrowUp' } });
      expect(input.props.value).toBe('first');

      // ArrowDown: forward again
      fireEvent(input, 'keyPress', { nativeEvent: { key: 'ArrowDown' } });
      expect(input.props.value).toBe('second');

      // ArrowDown past newest: clear
      fireEvent(input, 'keyPress', { nativeEvent: { key: 'ArrowDown' } });
      expect(input.props.value).toBe('');
    });

    test('hides input when readonly', () => {
      const { queryByPlaceholderText } = renderTerminal(
        <CanvasTerminal output={output} enableInput readonly />
      );
      expect(queryByPlaceholderText('Type a command...')).toBeNull();
    });
  });

  describe('Auto-scroll', () => {
    test('scrolls to end when output changes', () => {
      const scrollSpy = jest.spyOn(ScrollView.prototype, 'scrollToEnd').mockImplementation(() => {});

      const { rerender } = renderTerminal(<CanvasTerminal output={output} />);
      act(() => { jest.advanceTimersByTime(100); });
      const callsAfterMount = scrollSpy.mock.calls.length;
      expect(callsAfterMount).toBeGreaterThan(0);

      rerender(
        <Provider>
          <CanvasTerminal output={[...output, { type: 'stdout', content: 'more' }]} />
        </Provider>
      );

      act(() => { jest.advanceTimersByTime(100); });

      expect(scrollSpy.mock.calls.length).toBeGreaterThan(callsAfterMount);
      scrollSpy.mockRestore();
    });

    test('does not auto-scroll when autoScroll is disabled', () => {
      const scrollSpy = jest.spyOn(ScrollView.prototype, 'scrollToEnd').mockImplementation(() => {});

      renderTerminal(<CanvasTerminal output={output} autoScroll={false} />);

      act(() => { jest.advanceTimersByTime(100); });

      expect(scrollSpy).not.toHaveBeenCalled();
      scrollSpy.mockRestore();
    });
  });

  describe('Clear terminal', () => {
    test('clear action is available in the menu without crashing', () => {
      const { getByTestId, getByText } = renderTerminal(<CanvasTerminal output={output} />);

      fireEvent.press(getByTestId('icon-dots-vertical'));
      fireEvent.press(getByText('Clear Terminal'));

      // Output is unchanged (clear is a no-op hook today) but no crash
      expect(getByText('hello world')).toBeTruthy();
    });
  });
});
