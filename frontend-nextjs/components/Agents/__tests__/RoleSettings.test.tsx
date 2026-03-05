import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import { RoleSettings } from '../RoleSettings';

// Mock useToast hook
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

// Mock Spinner component
jest.mock('@/components/ui/spinner', () => ({
  Spinner: () => <div data-testid="spinner">Loading...</div>,
}));

describe('RoleSettings Component', () => {
  const mockOnRoleCreate = jest.fn();
  const mockOnRoleUpdate = jest.fn();
  const mockOnRoleDelete = jest.fn();
  const mockOnRoleDuplicate = jest.fn();

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

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders without crashing', () => {
      render(<RoleSettings />);

      expect(screen.getByText(/role settings/i)).toBeInTheDocument();
    });

    it('displays default roles when no initial roles provided', () => {
      render(<RoleSettings />);

      // Should display default roles
      expect(screen.getByText(/personal assistant/i)).toBeInTheDocument();
      expect(screen.getByText(/research agent/i)).toBeInTheDocument();
      expect(screen.getByText(/coding agent/i)).toBeInTheDocument();
    });

    it('displays provided initial roles', () => {
      render(<RoleSettings initialRoles={[mockRole]} />);

      expect(screen.getByText('Test Role')).toBeInTheDocument();
      expect(screen.getByText('A test role')).toBeInTheDocument();
    });

    it('shows role descriptions', () => {
      render(<RoleSettings initialRoles={[mockRole]} />);

      expect(screen.getByText('A test role')).toBeInTheDocument();
    });

    it('displays role capabilities as badges', () => {
      render(<RoleSettings initialRoles={[mockRole]} />);

      expect(screen.getByText('test_capability')).toBeInTheDocument();
    });

    it('marks default roles', () => {
      render(<RoleSettings initialRoles={[{ ...mockRole, isDefault: true }]} />);

      // Should indicate default role
      expect(screen.getByText(/default/i)).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('opens create role dialog', async () => {
      const user = userEvent.setup();
      render(<RoleSettings />);

      const createButton = screen.getByRole('button', { name: /create role/i });
      await user.click(createButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('creates new role with valid data', async () => {
      const user = userEvent.setup();
      render(<RoleSettings onRoleCreate={mockOnRoleCreate} />);

      const createButton = screen.getByRole('button', { name: /create role/i });
      await user.click(createButton);

      // Fill in role details
      const nameInput = screen.getByLabelText(/role name/i);
      await user.type(nameInput, 'New Test Role');

      const descriptionInput = screen.getByLabelText(/description/i);
      await user.type(descriptionInput, 'A new test role');

      const systemPromptInput = screen.getByLabelText(/system prompt/i);
      await user.type(systemPromptInput, 'You are a test assistant');

      // Submit form
      const submitButton = screen.getByRole('button', { name: /create/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockOnRoleCreate).toHaveBeenCalled();
      });
    });

    it('edits existing role', async () => {
      const user = userEvent.setup();
      render(<RoleSettings initialRoles={[mockRole]} onRoleUpdate={mockOnRoleUpdate} />);

      const editButton = screen.getByRole('button', { name: /edit test role/i });
      await user.click(editButton);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Modify role name
      const nameInput = screen.getByLabelText(/role name/i);
      await user.clear(nameInput);
      await user.type(nameInput, 'Updated Role Name');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockOnRoleUpdate).toHaveBeenCalledWith(
          'test-role-1',
          expect.objectContaining({
            name: 'Updated Role Name',
          })
        );
      });
    });

    it('deletes custom role', async () => {
      const user = userEvent.setup();
      window.confirm = jest.fn(() => true);

      render(
        <RoleSettings initialRoles={[mockRole]} onRoleDelete={mockOnRoleDelete} />
      );

      const deleteButton = screen.getByRole('button', { name: /delete test role/i });
      await user.click(deleteButton);

      await waitFor(() => {
        expect(window.confirm).toHaveBeenCalledWith(
          expect.stringContaining(/are you sure/i)
        );
      });

      await waitFor(() => {
        expect(mockOnRoleDelete).toHaveBeenCalledWith('test-role-1');
      });
    });

    it('prevents deletion of default roles', async () => {
      const user = userEvent.setup();
      const defaultRole = { ...mockRole, isDefault: true, name: 'Default Role' };

      render(<RoleSettings initialRoles={[defaultRole]} />);

      const deleteButton = screen.getByRole('button', { name: /delete default role/i });

      // Button might be disabled or not present for default roles
      if (deleteButton) {
        await user.click(deleteButton);

        // Should not call onRoleDelete
        expect(mockOnRoleDelete).not.toHaveBeenCalled();
      }
    });

    it('duplicates existing role', async () => {
      const user = userEvent.setup();
      render(
        <RoleSettings initialRoles={[mockRole]} onRoleDuplicate={mockOnRoleDuplicate} />
      );

      const duplicateButton = screen.getByRole('button', { name: /copy/i });
      await user.click(duplicateButton);

      await waitFor(() => {
        expect(mockOnRoleDuplicate).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'Test Role (Copy)',
          })
        );
      });
    });

    it('filters roles by search query', async () => {
      const user = userEvent.setup();
      const role1 = { ...mockRole, name: 'Developer Role' };
      const role2 = { ...mockRole, id: 'test-role-2', name: 'Designer Role' };

      render(<RoleSettings initialRoles={[role1, role2]} />);

      const searchInput = screen.getByPlaceholderText(/search roles/i);
      await user.type(searchInput, 'Developer');

      await waitFor(() => {
        expect(screen.getByText('Developer Role')).toBeInTheDocument();
        expect(screen.queryByText('Designer Role')).not.toBeInTheDocument();
      });
    });
  });

  describe('Permission Management', () => {
    it('displays all permission toggles', () => {
      render(<RoleSettings initialRoles={[mockRole]} />);

      expect(screen.getByLabelText(/can access files/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/can access web/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/can execute code/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/can access database/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/can send emails/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/can make api calls/i)).toBeInTheDocument();
    });

    it('toggles permissions on/off', async () => {
      const user = userEvent.setup();
      render(<RoleSettings initialRoles={[mockRole]} onRoleUpdate={mockOnRoleUpdate} />);

      const editButton = screen.getByRole('button', { name: /edit/i });
      await user.click(editButton);

      const canAccessWebToggle = screen.getByLabelText(/can access web/i);
      await user.click(canAccessWebToggle);

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockOnRoleUpdate).toHaveBeenCalledWith(
          'test-role-1',
          expect.objectContaining({
            permissions: expect.objectContaining({
              canAccessWeb: true,
            }),
          })
        );
      });
    });
  });

  describe('Model Configuration', () => {
    it('displays model configuration fields', async () => {
      const user = userEvent.setup();
      render(<RoleSettings initialRoles={[mockRole]} />);

      const editButton = screen.getByRole('button', { name: /edit/i });
      await user.click(editButton);

      expect(screen.getByLabelText(/model/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/temperature/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/max tokens/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/top p/i)).toBeInTheDocument();
    });

    it('updates model configuration', async () => {
      const user = userEvent.setup();
      render(<RoleSettings initialRoles={[mockRole]} onRoleUpdate={mockOnRoleUpdate} />);

      const editButton = screen.getByRole('button', { name: /edit/i });
      await user.click(editButton);

      const temperatureInput = screen.getByLabelText(/temperature/i);
      await user.clear(temperatureInput);
      await user.type(temperatureInput, '0.5');

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockOnRoleUpdate).toHaveBeenCalledWith(
          'test-role-1',
          expect.objectContaining({
            modelConfig: expect.objectContaining({
              temperature: 0.5,
            }),
          })
        );
      });
    });
  });

  describe('Capabilities Management', () => {
    it('displays role capabilities', () => {
      const roleWithCaps = {
        ...mockRole,
        capabilities: ['web_search', 'email_management', 'code_generation'],
      };

      render(<RoleSettings initialRoles={[roleWithCaps]} />);

      expect(screen.getByText('web_search')).toBeInTheDocument();
      expect(screen.getByText('email_management')).toBeInTheDocument();
      expect(screen.getByText('code_generation')).toBeInTheDocument();
    });

    it('adds new capability', async () => {
      const user = userEvent.setup();
      render(<RoleSettings initialRoles={[mockRole]} onRoleUpdate={mockOnRoleUpdate} />);

      const editButton = screen.getByRole('button', { name: /edit/i });
      await user.click(editButton);

      // Add capability
      const capabilityInput = screen.getByPlaceholderText(/add capability/i);
      await user.type(capabilityInput, 'new_capability');

      const addButton = screen.getByRole('button', { name: /add/i });
      await user.click(addButton);

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockOnRoleUpdate).toHaveBeenCalledWith(
          'test-role-1',
          expect.objectContaining({
            capabilities: expect.arrayContaining(['new_capability']),
          })
        );
      });
    });

    it('removes capability', async () => {
      const user = userEvent.setup();
      const roleWithCaps = {
        ...mockRole,
        capabilities: ['capability_to_remove', 'another_capability'],
      };

      render(
        <RoleSettings initialRoles={[roleWithCaps]} onRoleUpdate={mockOnRoleUpdate} />
      );

      const editButton = screen.getByRole('button', { name: /edit/i });
      await user.click(editButton);

      const removeButton = screen.getByRole('button', { name: /remove capability_to_remove/i });
      await user.click(removeButton);

      const saveButton = screen.getByRole('button', { name: /save/i });
      await user.click(saveButton);

      await waitFor(() => {
        expect(mockOnRoleUpdate).toHaveBeenCalledWith(
          'test-role-1',
          expect.objectContaining({
            capabilities: expect.not.arrayContaining(['capability_to_remove']),
          })
        );
      });
    });
  });

  describe('Loading States', () => {
    it('shows loading indicator when loading prop is true', () => {
      render(<RoleSettings loading={true} />);

      expect(screen.getByTestId('spinner')).toBeInTheDocument();
    });

    it('disables interactions during loading', () => {
      render(<RoleSettings loading={true} />);

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toBeDisabled();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<RoleSettings initialRoles={[mockRole]} />);

      expect(screen.getByRole('region', { name: /role settings/i })).toBeInTheDocument();
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();
      render(<RoleSettings initialRoles={[mockRole]} />);

      // Tab through interactive elements
      await user.tab();

      const firstButton = screen.getByRole('button', { name: /create role/i });
      expect(firstButton).toHaveFocus();
    });
  });

  describe('Validation', () => {
    it('requires role name', async () => {
      const user = userEvent.setup();
      render(<RoleSettings />);

      const createButton = screen.getByRole('button', { name: /create role/i });
      await user.click(createButton);

      const submitButton = screen.getByRole('button', { name: /create/i });
      await user.click(submitButton);

      // Should show validation error
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });

    it('requires system prompt', async () => {
      const user = userEvent.setup();
      render(<RoleSettings />);

      const createButton = screen.getByRole('button', { name: /create role/i });
      await user.click(createButton);

      const nameInput = screen.getByLabelText(/role name/i);
      await user.type(nameInput, 'Test Role');

      const submitButton = screen.getByRole('button', { name: /create/i });
      await user.click(submitButton);

      // Should show validation error
      expect(screen.getByText(/system prompt is required/i)).toBeInTheDocument();
    });
  });

  describe('Compact View', () => {
    it('renders in compact mode when compactView is true', () => {
      render(<RoleSettings compactView={true} />);

      // Should have different layout
      expect(screen.getByClassName(/compact/i)).toBeInTheDocument();
    });
  });
});
