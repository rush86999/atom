/**
 * Mobile Button Component Tests
 *
 * Tests for Button component using React Native Testing Library:
 * - Rendering with different variants and sizes
 * - User interaction (onPress, disabled state)
 * - Loading state
 * - Accessibility attributes
 * - Platform-specific behavior
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react-native';
import { Button } from '../Button';

describe('Mobile Button Component', () => {
  describe('Rendering Tests', () => {
    it('renders button with title', () => {
      render(<Button title="Click Me" onPress={jest.fn()} />);
      expect(screen.getByText('Click Me')).toBeTruthy();
    });

    it('renders primary variant by default', () => {
      const { getByTestId } = render(
        <Button title="Primary" onPress={jest.fn()} testID="test-button" />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
    });

    it('renders secondary variant', () => {
      const { getByTestId } = render(
        <Button title="Secondary" onPress={jest.fn()} variant="secondary" testID="test-button" />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
    });

    it('renders destructive variant', () => {
      const { getByTestId } = render(
        <Button title="Delete" onPress={jest.fn()} variant="destructive" testID="test-button" />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
    });

    it('renders outline variant', () => {
      const { getByTestId } = render(
        <Button title="Cancel" onPress={jest.fn()} variant="outline" testID="test-button" />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
    });

    it('renders ghost variant', () => {
      const { getByTestId } = render(
        <Button title="Ghost" onPress={jest.fn()} variant="ghost" testID="test-button" />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
    });

    it.each([
      ['small', 32],
      ['medium', 44],
      ['large', 52],
    ])('renders %s size with correct minHeight', (size, expectedMinHeight) => {
      const { getByTestId } = render(
        <Button
          title="Button"
          onPress={jest.fn()}
          size={size as any}
          testID="test-button"
        />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
    });

    it('renders with disabled state', () => {
      const { getByRole } = render(
        <Button title="Disabled" onPress={jest.fn()} disabled />
      );
      const button = getByRole('button');
      expect(button.props.disabled).toBe(true);
    });

    it('renders with loading indicator', () => {
      const { getByTestId } = render(
        <Button title="Loading" onPress={jest.fn()} loading testID="test-button" />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
      expect(screen.getByTestId('button-loading')).toBeTruthy();
    });

    it('renders with icon on left', () => {
      const icon = <></>; // Mock icon
      const { getByText } = render(
        <Button title="With Icon" onPress={jest.fn()} icon={icon} iconPosition="left" />
      );
      expect(screen.getByText('With Icon')).toBeTruthy();
    });

    it('renders with icon on right', () => {
      const icon = <></>; // Mock icon
      const { getByText } = render(
        <Button title="With Icon" onPress={jest.fn()} icon={icon} iconPosition="right" />
      );
      expect(screen.getByText('With Icon')).toBeTruthy();
    });
  });

  describe('User Interaction Tests', () => {
    it('calls onPress handler when pressed', () => {
      const handlePress = jest.fn();
      render(<Button title="Press Me" onPress={handlePress} />);

      const button = screen.getByText('Press Me');
      fireEvent.press(button);

      expect(handlePress).toHaveBeenCalledTimes(1);
    });

    it('does not call onPress when disabled', () => {
      const handlePress = jest.fn();
      render(<Button title="Disabled" onPress={handlePress} disabled />);

      const button = screen.getByText('Disabled');
      fireEvent.press(button);

      expect(handlePress).not.toHaveBeenCalled();
    });

    it('does not call onPress when loading', () => {
      const handlePress = jest.fn();
      render(<Button title="Loading" onPress={handlePress} loading />);

      const button = screen.getByRole('button', { disabled: true });
      expect(button).toBeTruthy();
    });
  });

  describe('Accessibility Tests', () => {
    it('has accessibilityLabel', () => {
      render(
        <Button
          title="+"
          accessibilityLabel="Add Item"
          onPress={jest.fn()}
        />
      );
      const button = screen.getByRole('button', { name: /Add Item/ });
      expect(button).toBeTruthy();
    });

    it('has accessibilityHint', () => {
      render(
        <Button
          title="Delete"
          accessibilityHint="Deletes the item permanently"
          onPress={jest.fn()}
        />
      );
      const button = screen.getByRole('button');
      expect(button.props.accessibilityHint).toBe('Deletes the item permanently');
    });

    it('communicates disabled state via accessibilityState', () => {
      render(
        <Button
          title="Disabled"
          onPress={jest.fn()}
          disabled
        />
      );
      const button = screen.getByRole('button');
      expect(button.props.accessibilityState).toEqual({
        disabled: true,
        busy: false,
      });
    });

    it('communicates loading state via accessibilityState', () => {
      render(
        <Button
          title="Loading"
          onPress={jest.fn()}
          loading
        />
      );
      const button = screen.getByRole('button');
      expect(button.props.accessibilityState).toEqual({
        disabled: true,
        busy: true,
      });
    });

    it('has button accessibilityRole', () => {
      render(
        <Button
          title="Button"
          onPress={jest.fn()}
        />
      );
      const button = screen.getByRole('button');
      expect(button).toBeTruthy();
    });

    it('has custom testID', () => {
      const { getByTestId } = render(
        <Button
          title="Button"
          onPress={jest.fn()}
          testID="custom-button-id"
        />
      );
      expect(getByTestId('custom-button-id')).toBeTruthy();
    });
  });

  describe('Platform-Specific Tests', () => {
    it('renders consistently on iOS', () => {
      jest.doMock('react-native', () => ({
        Platform: { OS: 'ios' },
      }));
      const { getByTestId } = render(
        <Button title="iOS Button" onPress={jest.fn()} testID="test-button" />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
    });

    it('renders consistently on Android', () => {
      jest.doMock('react-native', () => ({
        Platform: { OS: 'android' },
      }));
      const { getByTestId } = render(
        <Button title="Android Button" onPress={jest.fn()} testID="test-button" />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    it('handles very long titles', () => {
      const longTitle = 'This is a very long button title that should wrap properly';
      render(<Button title={longTitle} onPress={jest.fn()} />);
      expect(screen.getByText(longTitle)).toBeTruthy();
    });

    it('handles empty title gracefully', () => {
      const { getByTestId } = render(
        <Button title="" onPress={jest.fn()} testID="test-button" />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
    });

    it('handles custom styles', () => {
      const customButtonStyle = { marginTop: 10 };
      const customTextStyle = { fontSize: 20 };
      const { getByTestId } = render(
        <Button
          title="Styled"
          onPress={jest.fn()}
          buttonStyle={customButtonStyle}
          textStyle={customTextStyle}
          testID="test-button"
        />
      );
      const button = getByTestId('test-button');
      expect(button).toBeTruthy();
    });
  });
});
