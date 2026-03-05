import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axe from '@/tests/accessibility-config';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator
} from '@/components/ui/dropdown-menu';

/**
 * Dropdown Accessibility Test Suite
 *
 * Tests WCAG 2.1 AA compliance for DropdownMenu component:
 * - ARIA attributes: aria-expanded, aria-haspopup
 * - Keyboard navigation: Arrow keys, Enter, Space, Escape
 * - Role management: role="menu", role="menuitem"
 * - Radix UI handles ARIA automatically
 *
 * Reference: WAI-ARIA Authoring Practices 1.2 - Menu Pattern
 * https://www.w3.org/WAI/ARIA/apg/patterns/menu/
 */

describe('Dropdown Accessibility', () => {
  const renderDropdown = () => {
    return render(
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button>Open menu</button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>My Account</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem>Profile</DropdownMenuItem>
          <DropdownMenuItem>Settings</DropdownMenuItem>
          <DropdownMenuItem>Logout</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    );
  };

  it('should have no accessibility violations when open', async () => {
    const { baseElement } = renderDropdown();
    const user = userEvent.setup();

    // Open dropdown
    await user.click(screen.getByRole('button', { name: 'Open menu' }));

    // Use baseElement for Portal rendering
    const results = await axe(baseElement);
    expect(results).toHaveNoViolations();
  });

  it('should have aria-expanded attribute', async () => {
    const user = userEvent.setup();
    renderDropdown();

    const trigger = screen.getByRole('button', { name: 'Open menu' });

    // Initially closed
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    // Open dropdown
    await user.click(trigger);

    // Should be expanded
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('should have aria-haspopup attribute', () => {
    renderDropdown();

    const trigger = screen.getByRole('button', { name: 'Open menu' });

    // Radix UI adds aria-haspopup automatically
    expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
  });

  it('should open with Enter key', async () => {
    const user = userEvent.setup();
    renderDropdown();

    const trigger = screen.getByRole('button', { name: 'Open menu' });

    // Focus trigger
    trigger.focus();
    expect(trigger).toHaveFocus();

    // Press Enter to open
    await user.keyboard('{Enter}');

    // Menu should be visible
    expect(screen.getByText('Profile')).toBeVisible();
  });

  it('should open with Space key', async () => {
    const user = userEvent.setup();
    renderDropdown();

    const trigger = screen.getByRole('button', { name: 'Open menu' });

    // Focus trigger
    trigger.focus();
    expect(trigger).toHaveFocus();

    // Press Space to open
    await user.keyboard(' ');

    // Menu should be visible
    expect(screen.getByText('Profile')).toBeVisible();
  });

  it('should navigate with Arrow keys', async () => {
    const user = userEvent.setup();
    renderDropdown();

    const trigger = screen.getByRole('button', { name: 'Open menu' });

    // Open menu
    await user.click(trigger);

    // Get menu items
    const profileItem = screen.getByRole('menuitem', { name: 'Profile' });
    const settingsItem = screen.getByRole('menuitem', { name: 'Settings' });

    // Focus should be on first item
    await user.keyboard('{ArrowDown}');
    expect(profileItem).toHaveFocus();

    // ArrowDown should move to next item
    await user.keyboard('{ArrowDown}');
    expect(settingsItem).toHaveFocus();
  });

  it('should close on Escape key', async () => {
    const user = userEvent.setup();
    renderDropdown();

    const trigger = screen.getByRole('button', { name: 'Open menu' });

    // Open menu
    await user.click(trigger);
    expect(screen.getByText('Profile')).toBeVisible();

    // Close with Escape
    await user.keyboard('{Escape}');

    // Menu should be closed
    expect(screen.queryByText('Profile')).not.toBeInTheDocument();
  });

  it('should activate item with Enter', async () => {
    const user = userEvent.setup();
    renderDropdown();

    const trigger = screen.getByRole('button', { name: 'Open menu' });

    // Open menu
    await user.click(trigger);

    // Navigate to Profile
    await user.keyboard('{ArrowDown}');

    // Press Enter to activate
    await user.keyboard('{Enter}');

    // Menu should close after activation
    expect(screen.queryByText('Profile')).not.toBeInTheDocument();
  });

  it('should have role="menu" on content', async () => {
    const user = userEvent.setup();
    renderDropdown();

    const trigger = screen.getByRole('button', { name: 'Open menu' });

    // Open menu
    await user.click(trigger);

    // Radix UI adds role="menu" automatically
    const menu = screen.getByRole('menu');
    expect(menu).toBeInTheDocument();
  });

  it('should have role="menuitem" on items', async () => {
    const user = userEvent.setup();
    renderDropdown();

    const trigger = screen.getByRole('button', { name: 'Open menu' });

    // Open menu
    await user.click(trigger);

    // Radix UI adds role="menuitem" automatically
    const profileItem = screen.getByRole('menuitem', { name: 'Profile' });
    expect(profileItem).toBeInTheDocument();
  });

  it('should render via React Portal', async () => {
    const user = userEvent.setup();
    renderDropdown();

    const trigger = screen.getByRole('button', { name: 'Open menu' });

    // Open dropdown
    await user.click(trigger);

    // Content should be rendered via Portal
    const menu = screen.getByRole('menu');
    expect(document.body.contains(menu)).toBe(true);
  });
});
