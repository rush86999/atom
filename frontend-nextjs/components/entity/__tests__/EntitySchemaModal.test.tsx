/**
 * EntitySchemaModal Component Tests
 *
 * Tests verify entity schema creation, editing, validation,
 * visual/Monaco editor modes, and AI schema generation.
 *
 * Source: components/entity/EntitySchemaModal.tsx (158 lines uncovered)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EntitySchemaModal } from '../EntitySchemaModal';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  rest.post('/api/entity-types', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        entity_type: {
          id: 'entity-1',
          slug: 'test-entity',
          display_name: 'Test Entity',
          json_schema: { type: 'object' },
        },
      })
    );
  }),

  rest.patch('/api/entity-types/:id', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        entity_type: {
          id: 'entity-1',
          slug: 'test-entity',
          display_name: 'Updated Entity',
          json_schema: { type: 'object' },
        },
      })
    );
  }),

  rest.post('/api/entity-types/generate-schema', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        schema: {
          type: 'object',
          properties: {
            name: { type: 'string' },
            email: { type: 'string' },
          },
        },
      })
    );
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('EntitySchemaModal', () => {
  const mockOnSuccess = jest.fn();
  const mockOnClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders modal when open
  test('renders modal when open', () => {
    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    expect(screen.getByText(/create entity type/i)).toBeInTheDocument();
  });

  // Test 2: does not render when closed
  test('does not render when closed', () => {
    render(
      <EntitySchemaModal
        open={false}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    expect(screen.queryByText(/create entity type/i)).not.toBeInTheDocument();
  });

  // Test 3: creates new entity type
  test('creates new entity type', async () => {
    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const nameInput = screen.getByLabelText(/name/i);
    fireEvent.change(nameInput, { target: { value: 'Customer' } });

    const slugInput = screen.getByLabelText(/slug/i);
    fireEvent.change(slugInput, { target: { value: 'customer' } });

    const descriptionInput = screen.getByLabelText(/description/i);
    fireEvent.change(descriptionInput, { target: { value: 'Customer entity' } });

    const createButton = screen.getByRole('button', { name: /create/i });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  // Test 4: edits existing entity type
  test('edits existing entity type', async () => {
    const existingEntity = {
      id: 'entity-1',
      slug: 'customer',
      display_name: 'Customer',
      description: 'Customer entity',
      json_schema: { type: 'object' },
    };

    render(
      <EntitySchemaModal
        open={true}
        entityType={existingEntity}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    await waitFor(() => {
      expect(screen.getByDisplayValue('Customer')).toBeInTheDocument();
    });

    const nameInput = screen.getByLabelText(/name/i);
    fireEvent.change(nameInput, { target: { value: 'Updated Customer' } });

    const updateButton = screen.getByRole('button', { name: /update/i });
    fireEvent.click(updateButton);

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  // Test 5: switches between visual and Monaco editor modes
  test('switches between visual and Monaco editor modes', async () => {
    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const monacoButton = screen.getByRole('button', { name: /code/i });
    fireEvent.click(monacoButton);

    expect(screen.getByTestId(/monaco-editor/i)).toBeInTheDocument();

    const visualButton = screen.getByRole('button', { name: /visual/i });
    fireEvent.click(visualButton);

    expect(screen.getByTestId(/visual-builder/i)).toBeInTheDocument();
  });

  // Test 6: validates schema before submission
  test('validates schema before submission', async () => {
    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const nameInput = screen.getByLabelText(/name/i);
    fireEvent.change(nameInput, { target: { value: '' } });

    const createButton = screen.getByRole('button', { name: /create/i });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });
  });

  // Test 7: generates schema with AI
  test('generates schema with AI', async () => {
    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const descriptionInput = screen.getByLabelText(/description/i);
    fireEvent.change(descriptionInput, {
      target: { value: 'Customer with name and email' },
    });

    const generateButton = screen.getByRole('button', { name: /generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByText(/analyzing/i)).toBeInTheDocument();
    });
  });

  // Test 8: handles schema generation error
  test('handles schema generation error', async () => {
    server.use(
      rest.post('/api/entity-types/generate-schema', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const generateButton = screen.getByRole('button', { name: /generate/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(screen.getByText(/failed to generate/i)).toBeInTheDocument();
    });
  });

  // Test 9: shows diff preview for updates
  test('shows diff preview for updates', async () => {
    const existingEntity = {
      id: 'entity-1',
      slug: 'customer',
      display_name: 'Customer',
      json_schema: { type: 'object' },
    };

    render(
      <EntitySchemaModal
        open={true}
        entityType={existingEntity}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const diffButton = screen.getByRole('button', { name: /preview/i });
    fireEvent.click(diffButton);

    expect(screen.getByText(/changes/i)).toBeInTheDocument();
  });

  // Test 10: closes modal on cancel
  test('closes modal on cancel', () => {
    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    fireEvent.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  // Test 11: adds custom field to schema
  test('adds custom field to schema', async () => {
    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const visualButton = screen.getByRole('button', { name: /visual/i });
    fireEvent.click(visualButton);

    const addButton = screen.getByRole('button', { name: /add field/i });
    fireEvent.click(addButton);

    const fieldName = screen.getByPlaceholderText(/field name/i);
    fireEvent.change(fieldName, { target: { value: 'phone' } });

    expect(fieldName).toHaveValue('phone');
  });

  // Test 12: handles schema syntax error in Monaco editor
  test('handles schema syntax error in Monaco editor', async () => {
    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const monacoButton = screen.getByRole('button', { name: /code/i });
    fireEvent.click(monacoButton);

    // Simulate invalid JSON
    const editor = screen.getByTestId(/monaco-editor/i);
    fireEvent.change(editor, { target: { value: '{ invalid json' } });

    const createButton = screen.getByRole('button', { name: /create/i });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByText(/invalid schema/i)).toBeInTheDocument();
    });
  });

  // Test 13: displays loading state during submission
  test('displays loading state during submission', async () => {
    server.use(
      rest.post('/api/entity-types', (req, res, ctx) => {
        return res(
          ctx.delay(100),
          ctx.json({ success: true })
        );
      })
    );

    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const nameInput = screen.getByLabelText(/name/i);
    fireEvent.change(nameInput, { target: { value: 'Customer' } });

    const createButton = screen.getByRole('button', { name: /create/i });
    fireEvent.click(createButton);

    expect(screen.getByRole('button', { name: /loading/i })).toBeInTheDocument();
  });

  // Test 14: shows entity type validation errors
  test('shows entity type validation errors', async () => {
    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const slugInput = screen.getByLabelText(/slug/i);
    fireEvent.change(slugInput, { target: { value: 'Invalid Slug!' } });

    await waitFor(() => {
      expect(screen.getByText(/invalid slug/i)).toBeInTheDocument();
    });
  });

  // Test 15: handles API error during creation
  test('handles API error during creation', async () => {
    server.use(
      rest.post('/api/entity-types', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const nameInput = screen.getByLabelText(/name/i);
    fireEvent.change(nameInput, { target: { value: 'Customer' } });

    const createButton = screen.getByRole('button', { name: /create/i });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByText(/failed to create/i)).toBeInTheDocument();
    });
  });
});
