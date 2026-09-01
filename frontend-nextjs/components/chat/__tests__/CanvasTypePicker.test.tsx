/**
 * CanvasTypePicker — the styled dropdown on "Open latest draft in canvas".
 *
 * Covers: trigger shows the current choice; opens upward popover with the
 * recommended group first (auto/document/email) then all canvas apps;
 * selecting an option updates the value and closes; click-away closes.
 */

import React from 'react';
import { renderWithProviders, screen, fireEvent } from '../../../tests/test-utils';
import { CanvasTypePicker } from '../CanvasTypePicker';

describe('CanvasTypePicker', () => {
  test('trigger shows the current choice (auto recommended)', () => {
    renderWithProviders(<CanvasTypePicker value="auto" onChange={jest.fn()} />);
    expect(screen.getByTestId('canvas-type-select')).toHaveTextContent('Auto (recommended)');
    expect(screen.queryByTestId('canvas-type-menu')).not.toBeInTheDocument();
  });

  test('opens the menu: recommended group first, all apps after', () => {
    renderWithProviders(<CanvasTypePicker value="auto" onChange={jest.fn()} />);
    fireEvent.click(screen.getByTestId('canvas-type-select'));

    const menu = screen.getByTestId('canvas-type-menu');
    expect(menu).toBeInTheDocument();
    expect(screen.getByTestId('canvas-type-option-auto')).toBeInTheDocument();
    expect(screen.getByTestId('canvas-type-option-document')).toBeInTheDocument();
    expect(screen.getByTestId('canvas-type-option-email')).toBeInTheDocument();
    expect(screen.getByTestId('canvas-type-option-office_excel')).toBeInTheDocument();

    // Order: auto → document → email lead the list (best-match first).
    const ids = Array.from(menu.querySelectorAll('[role="option"]')).map(
      (el) => el.getAttribute('data-testid')
    );
    expect(ids.slice(0, 3)).toEqual([
      'canvas-type-option-auto',
      'canvas-type-option-document',
      'canvas-type-option-email',
    ]);
  });

  test('selecting an option reports the value and closes', () => {
    const onChange = jest.fn();
    renderWithProviders(<CanvasTypePicker value="auto" onChange={onChange} />);
    fireEvent.click(screen.getByTestId('canvas-type-select'));
    fireEvent.click(screen.getByTestId('canvas-type-option-email'));

    expect(onChange).toHaveBeenCalledWith('email');
    expect(screen.queryByTestId('canvas-type-menu')).not.toBeInTheDocument();
  });

  test('click-away closes without changing the value', () => {
    const onChange = jest.fn();
    renderWithProviders(<CanvasTypePicker value="auto" onChange={onChange} />);
    fireEvent.click(screen.getByTestId('canvas-type-select'));
    // the picker closes on mousedown outside (a click always starts with one)
    fireEvent.mouseDown(document.body);

    expect(screen.queryByTestId('canvas-type-menu')).not.toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });
});
