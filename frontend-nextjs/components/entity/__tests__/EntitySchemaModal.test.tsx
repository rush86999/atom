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
import EntitySchemaModal from '../EntitySchemaModal';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

jest.mock('react-hot-toast', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    loading: jest.fn(),
    dismiss: jest.fn(),
  },
}));

jest.mock('axios', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

jest.mock('../MonacoSchemaEditor', () => ({
  __esModule: true,
  default: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea
      data-testid="monaco-editor"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}));

// @rjsf pulls ESM-only deps (@x0k/json-schema-merge) that jest's CJS parser
// cannot load — the modal renders its own form fields, so stub the Form out
jest.mock('@rjsf/core', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@rjsf/validator-ajv8', () => ({
  __esModule: true,
  default: () => null,
}));

const defaultHandlers = [
  rest.post('*/api/entity-types', (req, res, ctx) => {
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

  rest.patch('*/api/entity-types/:id', (req, res, ctx) => {
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

  rest.post('*/api/entity-types/generate-schema', (req, res, ctx) => {
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
];

// Re-register default handlers after setup.ts's afterEach resetHandlers()
beforeEach(() => {
  server.use(...defaultHandlers);
});

const axiosDefault = require('axios').default;
const hotToast = require('react-hot-toast').toast;

describe('EntitySchemaModal', () => {
  const mockOnSuccess = jest.fn();
  const mockOnClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (axiosDefault.get as jest.Mock).mockResolvedValue({ data: [] });
    (axiosDefault.post as jest.Mock).mockResolvedValue({ data: { success: true } });
    (axiosDefault.put as jest.Mock).mockResolvedValue({ data: { success: true } });
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

    fireEvent.submit(document.getElementById('entity-schema-form') as HTMLFormElement);

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
      json_schema: { type: 'object', properties: {} },
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

    // jsdom does not trigger submission for submit buttons that reference a
    // form via the form="" attribute, so submit the form directly
    fireEvent.submit(document.getElementById('entity-schema-form') as HTMLFormElement);

    await waitFor(() => {
      expect(axiosDefault.put).toHaveBeenCalledWith(
        expect.stringContaining('/api/entity-types/entity-1'),
        expect.any(Object),
        expect.any(Object)
      );
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

    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument();

    const visualButton = screen.getByRole('button', { name: /visual/i });
    fireEvent.click(visualButton);

    expect(screen.getByText(/editor canvas/i)).toBeInTheDocument();
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

    // Break the schema in the code editor — submission must be blocked with a
    // toast error and onSuccess must NOT fire
    fireEvent.click(screen.getByRole('button', { name: /code/i }));
    const editor = screen.getByTestId('monaco-editor');
    fireEvent.change(editor, { target: { value: '{ invalid json' } });

    fireEvent.submit(document.getElementById('entity-schema-form') as HTMLFormElement);

    await waitFor(() => {
      expect(hotToast.error).toHaveBeenCalledWith(expect.stringMatching(/parse error|invalid schema/i));
    });
    expect(mockOnSuccess).not.toHaveBeenCalled();
  });

  // Test 7: generates schema with AI
  test('generates schema with AI', async () => {
    (axiosDefault.post as jest.Mock).mockResolvedValue({
      data: { success: true, data: { type: 'object', properties: { name: { type: 'string' } } } },
    });

    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const nameInput = screen.getByLabelText(/display name/i);
    fireEvent.change(nameInput, { target: { value: 'Customer' } });
    const descriptionInput = screen.getByLabelText(/description/i);
    fireEvent.change(descriptionInput, {
      target: { value: 'Customer with name and email' },
    });

    const generateButton = screen.getByRole('button', { name: /ai suggest/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(axiosDefault.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/entity-types/suggest-schema'),
        expect.any(Object),
        expect.any(Object)
      );
      // The suggestion opens the diff view for review
      expect(screen.getByText(/schema diff/i)).toBeInTheDocument();
    });
  });

  // Test 8: handles schema generation error
  test('handles schema generation error', async () => {
    (axiosDefault.post as jest.Mock).mockRejectedValue(new Error('suggest failed'));

    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const nameInput = screen.getByLabelText(/display name/i);
    fireEvent.change(nameInput, { target: { value: 'Customer' } });

    const generateButton = screen.getByRole('button', { name: /ai suggest/i });
    fireEvent.click(generateButton);

    await waitFor(() => {
      expect(hotToast.error).toHaveBeenCalledWith('Failed to get AI suggestion');
    });
  });

  // Test 9: shows diff preview for AI suggestions
  test('shows diff preview for updates', async () => {
    (axiosDefault.post as jest.Mock).mockResolvedValue({
      data: { success: true, data: { type: 'object', properties: { name: { type: 'string' } } } },
    });

    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    const nameInput = screen.getByLabelText(/display name/i);
    fireEvent.change(nameInput, { target: { value: 'Customer' } });

    fireEvent.click(screen.getByRole('button', { name: /ai suggest/i }));

    // The diff view offers accept / reject actions
    await waitFor(() => {
      expect(screen.getByText(/schema diff/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /apply ai schema/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /keep current/i })).toBeInTheDocument();
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

    // The visual builder is the default mode; its constructor palette adds
    // fields to the canvas
    fireEvent.click(screen.getByRole('button', { name: /text/i }));

    // The default schema already defines name + description, so the new
    // constructor field is the third one (rendered as a field card)
    await waitFor(() => {
      expect(screen.getByText('Field 3')).toBeInTheDocument();
    });
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
    const editor = screen.getByTestId('monaco-editor');
    fireEvent.change(editor, { target: { value: '{ invalid json' } });

    fireEvent.submit(document.getElementById('entity-schema-form') as HTMLFormElement);

    await waitFor(() => {
      expect(hotToast.error).toHaveBeenCalledWith(expect.stringMatching(/parse error|invalid schema/i));
    });
    expect(mockOnSuccess).not.toHaveBeenCalled();
  });

  // Test 13: displays loading state during submission
  test('displays loading state during submission', async () => {
    let resolvePost: (v: unknown) => void = () => {};
    (axiosDefault.post as jest.Mock).mockReturnValue(
      new Promise((res) => { resolvePost = res; })
    );

    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    fireEvent.submit(document.getElementById('entity-schema-form') as HTMLFormElement);

    // The submit button shows "Saving…" while the request is in flight
    expect(screen.getByRole('button', { name: /saving/i })).toBeInTheDocument();

    resolvePost({ data: { success: true } });
    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
    });
  });

  // Test 14: shows entity type validation errors — schema validation blocks submission
  test('shows entity type validation errors', async () => {
    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    // A non-object root schema fails validation
    fireEvent.click(screen.getByRole('button', { name: /code/i }));
    const editor = screen.getByTestId('monaco-editor');
    fireEvent.change(editor, { target: { value: '{"type": "string"}' } });

    fireEvent.submit(document.getElementById('entity-schema-form') as HTMLFormElement);

    await waitFor(() => {
      expect(hotToast.error).toHaveBeenCalledWith(expect.stringMatching(/invalid schema/i));
    });
    expect(mockOnSuccess).not.toHaveBeenCalled();
  });

  // Test 15: handles API error during creation
  test('handles API error during creation', async () => {
    (axiosDefault.post as jest.Mock).mockRejectedValue(new Error('server down'));

    render(
      <EntitySchemaModal
        open={true}
        onSuccess={mockOnSuccess}
        onClose={mockOnClose}
        workspaceId="workspace-1"
      />
    );

    fireEvent.submit(document.getElementById('entity-schema-form') as HTMLFormElement);

    await waitFor(() => {
      expect(hotToast.error).toHaveBeenCalledWith('Failed to save entity type');
    });
    expect(mockOnSuccess).not.toHaveBeenCalled();
  });
});
