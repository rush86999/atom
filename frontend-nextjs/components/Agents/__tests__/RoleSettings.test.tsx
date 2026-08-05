/**
 * RoleSettings Component Tests
 *
 * Tests verify role CRUD (create/edit/delete/duplicate), permission toggles,
 * and model configuration via callback props.
 *
 * Source: components/Agents/RoleSettings.tsx
 *
 * Real behavior (verified against source):
 * - RoleSettings is a DEFAULT export; the component renders a "Role Settings"
 *   card with a table of roles and a "Create Role" header button.
 * - With no initialRoles it populates three default roles (Personal Assistant,
 *   Research Agent, Coding Agent) via a mount effect (so assertions must wait).
 * - Create/Edit use a custom Dialog + form (Role Name, Description, Capabilities
 *   comma list, System Prompt, Permissions accordion of switches, Model
 *   Configuration accordion with Model/Temperature/Max Tokens). Submit button
 *   text is "Create Role" (create) or "Update Role" (edit).
 * - The row action buttons are icon-only (Edit/Copy/Trash2 lucide icons) with
 *   no accessible names -> located by .lucide-square-pen/.lucide-copy/.lucide-trash-2.
 *   (lucide-react aliases Edit -> SquarePen, class "lucide-square-pen".)
 * - Delete calls onRoleDelete directly (no window.confirm); default roles are
 *   blocked (shows an error toast, does NOT call onRoleDelete).
 * - There is no search box, no loading prop, and no custom validation messages.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import RoleSettings from '../RoleSettings';

// useToast + Spinner are already mocked in tests/setup.ts; keep explicit mocks
// so the component's toast()/Spinner usage never touches the real modules.
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({ toast: jest.fn() }),
}));
jest.mock('@/components/ui/spinner', () => ({
  Spinner: () => <div data-testid="spinner">Loading...</div>,
}));

const mockRole = {
  id: 'test-role-1',
  name: 'Test Role',
  description: 'A test role',
  capabilities: ['test_capability'],
  permissions: {
    canAccessFiles: true,
    canAccessWeb: false,
    canExecuteCode: false,
    canAccessDatabase: false,
    canSendEmails: false,
    canMakeAPICalls: false,
  },
  systemPrompt: 'You are a test assistant',
  modelConfig: {
    model: 'gpt-4',
    temperature: 0.7,
    maxTokens: 1000,
    topP: 1.0,
    frequencyPenalty: 0.0,
    presencePenalty: 0.0,
  },
  isDefault: false,
  createdAt: new Date('2024-01-01'),
  updatedAt: new Date('2024-01-01'),
};

const iconButton = (iconClass: string) =>
  screen.getAllByRole('button').find((btn) => btn.querySelector(`.${iconClass}`));

describe('RoleSettings Component', () => {
  const mockOnRoleCreate = jest.fn();
  const mockOnRoleUpdate = jest.fn();
  const mockOnRoleDelete = jest.fn();
  const mockOnRoleDuplicate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the Role Settings card', () => {
      render(<RoleSettings />);
      expect(screen.getByText('Role Settings')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create role/i })).toBeInTheDocument();
    });

    it('displays default roles when no initial roles are provided', async () => {
      render(<RoleSettings />);
      expect(await screen.findByText('Personal Assistant')).toBeInTheDocument();
      expect(screen.getByText('Research Agent')).toBeInTheDocument();
      expect(screen.getByText('Coding Agent')).toBeInTheDocument();
    });

    it('displays provided initial roles', async () => {
      render(<RoleSettings initialRoles={[mockRole]} />);
      expect(await screen.findByText('Test Role')).toBeInTheDocument();
      expect(screen.getByText('A test role')).toBeInTheDocument();
    });

    it('displays role capabilities as badges', async () => {
      render(<RoleSettings initialRoles={[mockRole]} />);
      expect(await screen.findByText('test_capability')).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('opens the create role dialog', async () => {
      const user = userEvent.setup();
      render(<RoleSettings />);

      await user.click(screen.getByRole('button', { name: /create role/i }));

      expect(await screen.findByRole('dialog')).toBeInTheDocument();
    });

    it('creates a new role', async () => {
      const user = userEvent.setup();
      render(<RoleSettings onRoleCreate={mockOnRoleCreate} />);
      await screen.findByText('Personal Assistant');

      await user.click(screen.getByRole('button', { name: /create role/i }));

      const dialog = await screen.findByRole('dialog');
      const form = within(dialog);

      await user.type(form.getByLabelText('Role Name'), 'New Test Role');
      await user.type(form.getByLabelText('Description'), 'A brand new role');
      await user.type(form.getByLabelText('System Prompt'), 'You are a test assistant');

      await user.click(form.getByRole('button', { name: 'Create Role' }));

      await waitFor(() => {
        expect(mockOnRoleCreate).toHaveBeenCalledWith(
          expect.objectContaining({ name: 'New Test Role' })
        );
      });
      expect(await screen.findByText('New Test Role')).toBeInTheDocument();
    });

    it('edits an existing role', async () => {
      const user = userEvent.setup();
      render(<RoleSettings initialRoles={[mockRole]} onRoleUpdate={mockOnRoleUpdate} />);
      await screen.findByText('Test Role');

      await user.click(iconButton('lucide-square-pen')!);

      const dialog = await screen.findByRole('dialog');
      const form = within(dialog);
      expect(form.getByText('Edit Role')).toBeInTheDocument();

      const nameInput = form.getByLabelText('Role Name');
      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Role Name');

      await user.click(form.getByRole('button', { name: 'Update Role' }));

      await waitFor(() => {
        expect(mockOnRoleUpdate).toHaveBeenCalledWith(
          'test-role-1',
          expect.objectContaining({ name: 'Updated Role Name' })
        );
      });
    });

    it('deletes a custom role without a confirm prompt', async () => {
      render(<RoleSettings initialRoles={[mockRole]} onRoleDelete={mockOnRoleDelete} />);
      await screen.findByText('Test Role');

      fireEvent.click(iconButton('lucide-trash-2')!);

      await waitFor(() => {
        expect(mockOnRoleDelete).toHaveBeenCalledWith('test-role-1');
      });
      expect(screen.queryByText('Test Role')).not.toBeInTheDocument();
    });

    it('blocks deleting a default role', async () => {
      render(<RoleSettings onRoleDelete={mockOnRoleDelete} />);
      await screen.findByText('Personal Assistant');

      fireEvent.click(iconButton('lucide-trash-2')!);

      expect(mockOnRoleDelete).not.toHaveBeenCalled();
      expect(screen.getByText('Personal Assistant')).toBeInTheDocument();
    });

    it('duplicates a role as "(Copy)"', async () => {
      render(<RoleSettings initialRoles={[mockRole]} onRoleDuplicate={mockOnRoleDuplicate} />);
      await screen.findByText('Test Role');

      fireEvent.click(iconButton('lucide-copy')!);

      await waitFor(() => {
        expect(mockOnRoleDuplicate).toHaveBeenCalledWith(
          expect.objectContaining({ name: 'Test Role (Copy)' })
        );
      });
      expect(await screen.findByText('Test Role (Copy)')).toBeInTheDocument();
    });
  });

  describe('Permissions', () => {
    it('toggles a permission and persists it on update', async () => {
      const user = userEvent.setup();
      render(<RoleSettings initialRoles={[mockRole]} onRoleUpdate={mockOnRoleUpdate} />);
      await screen.findByText('Test Role');

      await user.click(iconButton('lucide-square-pen')!);

      const dialog = await screen.findByRole('dialog');
      const form = within(dialog);

      await user.click(form.getByRole('button', { name: 'Permissions' }));
      // Permission labels are derived via "canAccessWeb" -> "can Access Web"
      // (CSS-only capitalize; text content stays lowercase).
      await user.click(form.getByLabelText(/can access web/i));
      await user.click(form.getByRole('button', { name: 'Update Role' }));

      await waitFor(() => {
        expect(mockOnRoleUpdate).toHaveBeenCalledWith(
          'test-role-1',
          expect.objectContaining({
            permissions: expect.objectContaining({ canAccessWeb: true }),
          })
        );
      });
    });
  });

  describe('Model Configuration', () => {
    it('updates the temperature and persists it on update', async () => {
      const user = userEvent.setup();
      render(<RoleSettings initialRoles={[mockRole]} onRoleUpdate={mockOnRoleUpdate} />);
      await screen.findByText('Test Role');

      await user.click(iconButton('lucide-square-pen')!);

      const dialog = await screen.findByRole('dialog');
      const form = within(dialog);

      await user.click(form.getByRole('button', { name: 'Model Configuration' }));
      // Temperature/Max Tokens inputs have NO id, so <label for="..."> does not
      // associate. Number inputs expose role "spinbutton"; Temperature is first.
      fireEvent.change(form.getAllByRole('spinbutton')[0], { target: { value: '0.5' } });
      await user.click(form.getByRole('button', { name: 'Update Role' }));

      await waitFor(() => {
        expect(mockOnRoleUpdate).toHaveBeenCalledWith(
          'test-role-1',
          expect.objectContaining({
            modelConfig: expect.objectContaining({ temperature: 0.5 }),
          })
        );
      });
    });
  });
});
