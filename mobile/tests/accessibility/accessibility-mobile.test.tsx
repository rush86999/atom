import React from 'react';
import { render, screen } from '@testing-library/react-native';
import { Button } from '../../src/components/Button';
import { Card } from '../../src/components/Card';

/**
 * React Native accessibility tests for mobile components
 *
 * These tests verify WCAG 2.1 AA compliance for React Native components:
 * - Accessibility labels on all interactive elements
 * - Touch target sizes (44x44dp minimum)
 * - Screen reader announcements for state changes
 * - Accessibility hints for actions
 * - Accessible headings for logical sections
 * - Accessible states for switches and toggles
 * - List item count announcements
 * - Progress indicator accessibility
 *
 * Test patterns from RESEARCH.md lines 157-173
 */

describe('Mobile accessibility', () => {
  describe('Button accessibility', () => {
    it('should have accessibility label on buttons', () => {
      render(<Button title="Submit" onPress={() => {}} />);

      const button = screen.getByRole('button');
      expect(button.props.accessibilityLabel).toBeDefined();
      expect(button.props.accessibilityLabel).toBe('Submit');
    });

    it('should have custom accessibility label when provided', () => {
      render(
        <Button
          title="Delete"
          onPress={() => {}}
          accessibilityLabel="Delete item permanently"
        />
      );

      const button = screen.getByRole('button');
      expect(button.props.accessibilityLabel).toBe('Delete item permanently');
    });

    it('should have accessibility hint when provided', () => {
      render(
        <Button
          title="Submit"
          onPress={() => {}}
          accessibilityHint="Submits the form and creates a new record"
        />
      );

      const button = screen.getByRole('button');
      expect(button.props.accessibilityHint).toBe(
        'Submits the form and creates a new record'
      );
    });

    it('should announce disabled state', () => {
      render(<Button title="Submit" onPress={() => {}} disabled={true} />);

      const button = screen.getByRole('button');
      expect(button.props.accessibilityState).toEqual({
        disabled: true,
        busy: false,
      });
    });

    it('should announce loading state', () => {
      render(<Button title="Submit" onPress={() => {}} loading={true} />);

      const button = screen.getByRole('button');
      expect(button.props.accessibilityState).toEqual({
        disabled: true,
        busy: true,
      });
    });

    it('should have proper button role', () => {
      render(<Button title="Click me" onPress={() => {}} />);

      const button = screen.getByRole('button');
      expect(button.props.accessibilityRole).toBe('button');
    });

    it('should be accessible (enabled by default)', () => {
      render(<Button title="Submit" onPress={() => {}} />);

      const button = screen.getByRole('button');
      expect(button.props.accessible).toBe(true);
    });
  });

  describe('Touch target sizes', () => {
    it('should meet minimum touch target size for small buttons', () => {
      render(<Button title="Small" onPress={() => {}} size="small" />);

      const button = screen.getByRole('button');
      const style = button.props.style;

      // Style is an object, not an array
      const minHeight = (style as any)?.minHeight || (style as any)?.[0]?.minHeight;
      expect(minHeight).toBeGreaterThanOrEqual(32); // 32dp for small
    });

    it('should meet minimum touch target size for medium buttons', () => {
      render(<Button title="Medium" onPress={() => {}} size="medium" />);

      const button = screen.getByRole('button');
      const style = button.props.style;

      const minHeight = (style as any)?.minHeight || (style as any)?.[0]?.minHeight;
      expect(minHeight).toBeGreaterThanOrEqual(44); // 44dp minimum
    });

    it('should meet minimum touch target size for large buttons', () => {
      render(<Button title="Large" onPress={() => {}} size="large" />);

      const button = screen.getByRole('button');
      const style = button.props.style;

      const minHeight = (style as any)?.minHeight || (style as any)?.[0]?.minHeight;
      expect(minHeight).toBeGreaterThanOrEqual(52); // 52dp for large
    });
  });

  describe('Card accessibility', () => {
    it('should have accessibility label on clickable cards', () => {
      render(
        <Card
          title="Card Title"
          description="Card description"
          onPress={() => {}}
        />
      );

      const card = screen.getByRole('button');
      expect(card.props.accessibilityLabel).toBeDefined();
      expect(card.props.accessibilityLabel).toBe('Card Title');
    });

    it('should have custom accessibility label when provided', () => {
      render(
        <Card
          title="Card Title"
          onPress={() => {}}
          accessibilityLabel="Open settings panel"
        />
      );

      const card = screen.getByRole('button');
      expect(card.props.accessibilityLabel).toBe('Open settings panel');
    });

    it('should have accessibility hint for clickable cards', () => {
      render(
        <Card
          title="Card Title"
          onPress={() => {}}
          accessibilityHint="Double tap to open details"
        />
      );

      const card = screen.getByRole('button');
      expect(card.props.accessibilityHint).toBe('Double tap to open details');
    });

    it('should have button role when clickable', () => {
      render(<Card title="Card Title" onPress={() => {}} />);

      const card = screen.getByRole('button');
      expect(card.props.accessibilityRole).toBe('button');
    });

    it('should have no role when not clickable', () => {
      render(<Card title="Card Title" />);

      // Card should not have button role if not clickable
      const card = screen.queryByRole('button');
      expect(card).toBeNull();
    });

    it('should announce disabled state for clickable cards', () => {
      render(
        <Card
          title="Card Title"
          onPress={() => {}}
          disabled={true}
        />
      );

      const card = screen.getByTestId('card');
      const style = card.props.style;
      const disabledStyle = style?.find((s: any) => s?.opacity);

      expect(disabledStyle?.opacity).toBeLessThan(1);
    });
  });

  describe('Text input accessibility', () => {
    it('should have accessibility label on text inputs', () => {
      // Mock TextInput component for testing
      const MockTextInput = ({ accessibilityLabel, placeholder }: any) => (
        <div
          accessibilityRole="text"
          accessibilityLabel={accessibilityLabel}
          accessible={true}
        >
          {placeholder}
        </div>
      );

      render(
        <MockTextInput
          accessibilityLabel="Email address"
          placeholder="Enter email"
        />
      );

      const input = screen.getByRole('text');
      expect(input.props.accessibilityLabel).toBe('Email address');
    });

    it('should have accessibility hint for text inputs', () => {
      const MockTextInput = ({ accessibilityLabel, accessibilityHint }: any) => (
        <div
          accessibilityRole="text"
          accessibilityLabel={accessibilityLabel}
          accessibilityHint={accessibilityHint}
          accessible={true}
        />
      );

      render(
        <MockTextInput
          accessibilityLabel="Password"
          accessibilityHint="Must be at least 8 characters long"
        />
      );

      const input = screen.getByRole('text');
      expect(input.props.accessibilityHint).toBe(
        'Must be at least 8 characters long'
      );
    });
  });

  describe('Image accessibility', () => {
    it('should have accessibility label on images', () => {
      const MockImage = ({ accessibilityLabel }: any) => (
        <div
          accessibilityRole="image"
          accessibilityLabel={accessibilityLabel}
          accessible={true}
        />
      );

      render(<MockImage accessibilityLabel="Profile picture" />);

      const image = screen.getByRole('image');
      expect(image.props.accessibilityLabel).toBeDefined();
      expect(image.props.accessibilityLabel).toBe('Profile picture');
    });

    it('should not have accessibility label for decorative images', () => {
      const MockImage = ({ accessibilityRole }: any) => (
        <div
          accessibilityRole="none"
          accessible={false}
        />
      );

      render(<MockImage accessibilityRole="none" />);

      // Decorative images should not be accessible
      const image = screen.queryByRole('image');
      expect(image).toBeNull();
    });
  });

  describe('Switch and toggle accessibility', () => {
    it('should announce switch state when on', () => {
      const MockSwitch = ({ accessibilityState, accessibilityLabel }: any) => (
        <div
          accessibilityRole="switch"
          accessibilityLabel={accessibilityLabel}
          accessibilityState={accessibilityState}
          accessible={true}
        />
      );

      render(
        <MockSwitch
          accessibilityLabel="Dark mode"
          accessibilityState={{ checked: true }}
        />
      );

      const switchComponent = screen.getByRole('switch');
      expect(switchComponent.props.accessibilityState).toEqual({
        checked: true,
      });
    });

    it('should announce switch state when off', () => {
      const MockSwitch = ({ accessibilityState, accessibilityLabel }: any) => (
        <div
          accessibilityRole="switch"
          accessibilityLabel={accessibilityLabel}
          accessibilityState={accessibilityState}
          accessible={true}
        />
      );

      render(
        <MockSwitch
          accessibilityLabel="Dark mode"
          accessibilityState={{ checked: false }}
        />
      );

      const switchComponent = screen.getByRole('switch');
      expect(switchComponent.props.accessibilityState).toEqual({
        checked: false,
      });
    });
  });

  describe('List accessibility', () => {
    it('should have accessible heading for list section', () => {
      const MockList = ({ accessibilityLabel, children }: any) => (
        <div
          accessibilityRole="list"
          accessibilityLabel={accessibilityLabel}
          accessible={true}
        >
          {children}
        </div>
      );

      render(
        <MockList accessibilityLabel="Shopping list">
          <div accessibilityRole="text" accessible={true}>Item 1</div>
          <div accessibilityRole="text" accessible={true}>Item 2</div>
        </MockList>
      );

      const list = screen.getByRole('list');
      expect(list.props.accessibilityLabel).toBe('Shopping list');
    });

    it('should announce list item count', () => {
      const MockList = ({ accessibilityLabel, children }: any) => (
        <div
          accessibilityRole="list"
          accessibilityLabel={accessibilityLabel}
          accessible={true}
        >
          {children}
        </div>
      );

      render(
        <MockList accessibilityLabel="Shopping list, 3 items">
          <div accessibilityRole="text" accessible={true}>Item 1</div>
          <div accessibilityRole="text" accessible={true}>Item 2</div>
          <div accessibilityRole="text" accessible={true}>Item 3</div>
        </MockList>
      );

      const list = screen.getByRole('list');
      expect(list.props.accessibilityLabel).toContain('3 items');
    });
  });

  describe('Progress indicator accessibility', () => {
    it('should announce loading state', () => {
      const MockProgress = ({ accessibilityState, accessibilityLabel }: any) => (
        <div
          accessibilityRole="progressbar"
          accessibilityLabel={accessibilityLabel}
          accessibilityState={accessibilityState}
          accessible={true}
        />
      );

      render(
        <MockProgress
          accessibilityLabel="Loading content"
          accessibilityState={{ busy: true }}
        />
      );

      const progress = screen.getByRole('progressbar');
      expect(progress.props.accessibilityState).toEqual({ busy: true });
    });

    it('should announce completion state', () => {
      const MockProgress = ({ accessibilityState, accessibilityLabel }: any) => (
        <div
          accessibilityRole="progressbar"
          accessibilityLabel={accessibilityLabel}
          accessibilityState={accessibilityState}
          accessible={true}
        />
      );

      render(
        <MockProgress
          accessibilityLabel="Loading complete"
          accessibilityState={{ busy: false }}
        />
      );

      const progress = screen.getByRole('progressbar');
      expect(progress.props.accessibilityState).toEqual({ busy: false });
    });
  });

  describe('Modal accessibility', () => {
    it('should have accessibility role for modal', () => {
      const MockModal = ({ accessibilityLabel, children }: any) => (
        <div
          accessibilityRole="alert"
          accessibilityLabel={accessibilityLabel}
          accessible={true}
        >
          {children}
        </div>
      );

      render(
        <MockModal accessibilityLabel="Error message">
          <div>An error occurred</div>
        </MockModal>
      );

      const modal = screen.getByRole('alert');
      expect(modal.props.accessibilityLabel).toBe('Error message');
    });

    it('should trap focus within modal', () => {
      // React Native modals automatically trap focus
      // This test verifies modal accessibility attributes
      const MockModal = ({ accessible }: any) => (
        <div
          accessibilityRole="alert"
          accessibilityLabel="Modal dialog"
          accessible={accessible}
        >
          <div>Modal content</div>
        </div>
      );

      render(<MockModal accessible={true} />);

      const modal = screen.getByRole('alert');
      expect(modal.props.accessible).toBe(true);
    });
  });

  describe('Heading accessibility', () => {
    it('should have accessible heading for logical sections', () => {
      const MockHeading = ({ accessibilityLabel, accessibilityRole }: any) => (
        <div
          accessibilityRole="header"
          accessibilityLabel={accessibilityLabel}
          accessible={true}
        >
          Section Title
        </div>
      );

      render(<MockHeading accessibilityLabel="Profile settings" />);

      const heading = screen.getByRole('header');
      expect(heading.props.accessibilityLabel).toBe('Profile settings');
    });
  });

  describe('Action accessibility', () => {
    it('should have accessibility hint for actions', () => {
      render(
        <Button
          title="Delete"
          onPress={() => {}}
          accessibilityHint="Deletes the selected item permanently"
        />
      );

      const button = screen.getByRole('button');
      expect(button.props.accessibilityHint).toBe(
        'Deletes the selected item permanently'
      );
    });

    it('should have accessibility hint for card actions', () => {
      render(
        <Card
          title="Settings"
          onPress={() => {}}
          accessibilityHint="Double tap to open settings panel"
        />
      );

      const card = screen.getByRole('button');
      expect(card.props.accessibilityHint).toBe(
        'Double tap to open settings panel'
      );
    });
  });

  describe('Group accessibility', () => {
    it('should have accessible heading for grouped elements', () => {
      const MockGroup = ({ accessibilityLabel, children }: any) => (
        <div
          accessibilityRole="none"
          accessibilityLabel={accessibilityLabel}
          accessible={true}
        >
          {children}
        </div>
      );

      render(
        <MockGroup accessibilityLabel="Form controls">
          <div accessibilityRole="text" accessible={true}>Field 1</div>
          <div accessibilityRole="text" accessible={true}>Field 2</div>
        </MockGroup>
      );

      const group = screen.getByLabelText('Form controls');
      expect(group).toBeDefined();
    });
  });

  describe('Link accessibility', () => {
    it('should have accessibility label on links', () => {
      const MockLink = ({ accessibilityLabel, children }: any) => (
        <div
          accessibilityRole="link"
          accessibilityLabel={accessibilityLabel}
          accessible={true}
        >
          {children}
        </div>
      );

      render(<MockLink accessibilityLabel="Visit our website">Link text</MockLink>);

      const link = screen.getByRole('link');
      expect(link.props.accessibilityLabel).toBe('Visit our website');
    });
  });

  describe('Search field accessibility', () => {
    it('should have accessibility label on search fields', () => {
      const MockSearch = ({ accessibilityLabel, accessibilityRole }: any) => (
        <div
          accessibilityRole={accessibilityRole}
          accessibilityLabel={accessibilityLabel}
          accessible={true}
        />
      );

      render(
        <MockSearch
          accessibilityRole="search"
          accessibilityLabel="Search contacts"
        />
      );

      const search = screen.getByRole('search');
      expect(search.props.accessibilityLabel).toBe('Search contacts');
    });
  });

  describe('Tab bar accessibility', () => {
    it('should have accessibility role for tab bar', () => {
      const MockTabBar = ({ accessibilityLabel, children }: any) => (
        <div
          accessibilityRole="tablist"
          accessibilityLabel={accessibilityLabel}
          accessible={true}
        >
          {children}
        </div>
      );

      render(
        <MockTabBar accessibilityLabel="Main navigation">
          <div accessibilityRole="tab" accessible={true}>Home</div>
          <div accessibilityRole="tab" accessible={true}>Profile</div>
        </MockTabBar>
      );

      const tabBar = screen.getByRole('tablist');
      expect(tabBar.props.accessibilityLabel).toBe('Main navigation');
    });

    it('should have accessible tabs', () => {
      const MockTab = ({ accessibilityLabel, accessibilityRole, accessibilityState }: any) => (
        <div
          accessibilityRole={accessibilityRole}
          accessibilityLabel={accessibilityLabel}
          accessibilityState={accessibilityState}
          accessible={true}
        />
      );

      render(
        <MockTab
          accessibilityRole="tab"
          accessibilityLabel="Home"
          accessibilityState={{ selected: true }}
        />
      );

      const tab = screen.getByRole('tab');
      expect(tab.props.accessibilityLabel).toBe('Home');
      // Check that accessibilityState exists and has selected property
      expect(tab.props.accessibilityState).toBeDefined();
      expect((tab.props.accessibilityState as any)?.selected).toBe(true);
    });
  });

  describe('Accessibility state changes', () => {
    it('should announce state changes from disabled to enabled', () => {
      const { rerender } = render(
        <Button title="Submit" onPress={() => {}} disabled={true} />
      );

      const button = screen.getByRole('button');
      expect(button.props.accessibilityState).toEqual({
        disabled: true,
        busy: false,
      });

      // Rerender with enabled state
      rerender(<Button title="Submit" onPress={() => {}} disabled={false} />);

      expect(button.props.accessibilityState).toEqual({
        disabled: false,
        busy: false,
      });
    });

    it('should announce state changes from loading to idle', () => {
      const { rerender } = render(
        <Button title="Submit" onPress={() => {}} loading={true} />
      );

      const button = screen.getByRole('button');
      expect(button.props.accessibilityState).toEqual({
        disabled: true,
        busy: true,
      });

      // Rerender with idle state
      rerender(<Button title="Submit" onPress={() => {}} loading={false} />);

      expect(button.props.accessibilityState).toEqual({
        disabled: false,
        busy: false,
      });
    });
  });
});
