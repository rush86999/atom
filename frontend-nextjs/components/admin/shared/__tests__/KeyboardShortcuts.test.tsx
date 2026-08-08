/**
 * KeyboardShortcuts tests.
 *
 * Covers the REAL components/admin/shared/KeyboardShortcuts.tsx:
 * - useKeyboardShortcuts hook: single-key match ("?"), modifier combos
 *   (ctrl+shift / cmd+key), suppression while typing in inputs unless a
 *   modifier is held, preventDefault on match, listener cleanup on unmount.
 *   NOTE: the matcher requires every `+`-separated key to match a single
 *   keydown event, so only one non-modifier key per shortcut is meaningful —
 *   exactly how the admin pages use it ("?", "r", "n", "/", "1".."6").
 * - KeyboardShortcutsHelp dialog: renders shortcut groups/descriptions/kbd
 *   keys, Close button calls onClose, nothing renders when closed
 */
import React from 'react';
import { render, screen, fireEvent, renderHook } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useKeyboardShortcuts, KeyboardShortcutsHelp } from '../KeyboardShortcuts';

interface Shortcut {
  key: string;
  description: string;
  action: () => void;
}

const makeGroups = (actions: Record<string, () => void>): { title: string; shortcuts: Shortcut[] }[] => {
  const groups: { title: string; shortcuts: Shortcut[] }[] = [];
  const dashboard: Shortcut[] = [];
  if (actions['?']) {
    dashboard.push({ key: '?', description: 'Show keyboard shortcuts', action: actions['?'] });
  }
  if (actions['ctrl+shift+n']) {
    dashboard.push({ key: 'ctrl+shift+n', description: 'New workflow', action: actions['ctrl+shift+n'] });
  }
  if (dashboard.length) groups.push({ title: 'Dashboard', shortcuts: dashboard });
  if (actions['cmd+s']) {
    groups.push({
      title: 'Actions',
      shortcuts: [{ key: 'cmd+s', description: 'Save all', action: actions['cmd+s'] }],
    });
  }
  return groups;
};

describe('useKeyboardShortcuts', () => {
  it('triggers the action when a single-key shortcut matches', () => {
    const action = jest.fn();
    const groups = makeGroups({ '?': action });
    renderHook(() => useKeyboardShortcuts(groups));

    fireEvent.keyDown(window, { key: '?' });

    expect(action).toHaveBeenCalledTimes(1);
  });

  it('does not trigger when a different key is pressed', () => {
    const action = jest.fn();
    const groups = makeGroups({ '?': action });
    renderHook(() => useKeyboardShortcuts(groups));

    fireEvent.keyDown(window, { key: 'x' });
    expect(action).not.toHaveBeenCalled();
  });

  it('matches ctrl/cmd and shift modifier combinations', () => {
    const action = jest.fn();
    const groups = makeGroups({ 'ctrl+shift+n': action });
    renderHook(() => useKeyboardShortcuts(groups));

    fireEvent.keyDown(window, { key: 'n', ctrlKey: true, shiftKey: true });
    expect(action).toHaveBeenCalledTimes(1);

    const saveAction = jest.fn();
    const saveGroups = makeGroups({ 'cmd+s': saveAction });
    renderHook(() => useKeyboardShortcuts(saveGroups));

    fireEvent.keyDown(window, { key: 's', metaKey: true });
    expect(saveAction).toHaveBeenCalledTimes(1);
  });

  it('requires every key of a combo to match the same event', () => {
    const action = jest.fn();
    const groups = makeGroups({ 'ctrl+shift+n': action });
    renderHook(() => useKeyboardShortcuts(groups));

    // Shift alone is not enough — ctrl is also required
    fireEvent.keyDown(window, { key: 'n', shiftKey: true });
    expect(action).not.toHaveBeenCalled();
  });

  it('prevents default on a matched shortcut', () => {
    const action = jest.fn();
    const groups = makeGroups({ '?': action });
    renderHook(() => useKeyboardShortcuts(groups));

    const event = new KeyboardEvent('keydown', { key: '?' });
    const preventDefault = jest.spyOn(event, 'preventDefault');
    window.dispatchEvent(event);

    expect(action).toHaveBeenCalled();
    expect(preventDefault).toHaveBeenCalled();
  });

  it('does not trigger while typing in an input without a modifier', () => {
    const action = jest.fn();
    const groups = makeGroups({ '?': action });
    const Harness: React.FC = () => {
      useKeyboardShortcuts(groups);
      return <input data-testid="txt" />;
    };
    render(<Harness />);

    fireEvent.keyDown(screen.getByTestId('txt'), { key: '?' });
    expect(action).not.toHaveBeenCalled();
  });

  it('triggers modifier shortcuts even while typing in an input', () => {
    const action = jest.fn();
    const groups = makeGroups({ 'cmd+s': action });
    const Harness: React.FC = () => {
      useKeyboardShortcuts(groups);
      return <textarea data-testid="txt" />;
    };
    render(<Harness />);

    fireEvent.keyDown(screen.getByTestId('txt'), { key: 's', metaKey: true });
    expect(action).toHaveBeenCalledTimes(1);
  });

  it('removes the keydown listener on unmount', () => {
    const action = jest.fn();
    const groups = makeGroups({ '?': action });
    const { unmount } = renderHook(() => useKeyboardShortcuts(groups));

    unmount();
    fireEvent.keyDown(window, { key: '?' });

    expect(action).not.toHaveBeenCalled();
  });
});

describe('KeyboardShortcutsHelp', () => {
  const onClose = jest.fn();
  const groups = makeGroups({ '?': jest.fn(), 'ctrl+shift+n': jest.fn(), 'cmd+s': jest.fn() });

  it('renders nothing when closed', () => {
    render(<KeyboardShortcutsHelp open={false} onClose={onClose} groups={groups} />);
    expect(screen.queryByText('Keyboard Shortcuts')).not.toBeInTheDocument();
  });

  it('renders all shortcut groups, descriptions, and key badges', () => {
    render(<KeyboardShortcutsHelp open={true} onClose={onClose} groups={groups} />);

    expect(screen.getByText('Keyboard Shortcuts')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Actions')).toBeInTheDocument();
    expect(screen.getByText('Show keyboard shortcuts')).toBeInTheDocument();
    expect(screen.getByText('New workflow')).toBeInTheDocument();
    expect(screen.getByText('Save all')).toBeInTheDocument();

    // kbd keys rendered per component key, plus "+" separators
    // ("?" appears in both the shortcut list and the dialog description)
    expect(screen.getAllByText('?').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('ctrl')).toBeInTheDocument();
    expect(screen.getByText('shift')).toBeInTheDocument();
    expect(screen.getByText('n')).toBeInTheDocument();
    expect(screen.getByText('cmd')).toBeInTheDocument();
    expect(screen.getByText('s')).toBeInTheDocument();
    expect(screen.getAllByText('+').length).toBeGreaterThanOrEqual(2);
  });

  it('calls onClose from the Close button', () => {
    render(<KeyboardShortcutsHelp open={true} onClose={onClose} groups={groups} />);

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalled();
  });
});
