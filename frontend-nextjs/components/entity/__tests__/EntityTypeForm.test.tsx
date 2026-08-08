/**
 * EntityTypeForm Component Tests
 *
 * Covers the REAL EntityTypeForm (components/entity/EntityTypeForm.tsx):
 * - Fetches available skills on mount (GET /api/skills) with X-Workspace-ID
 * - Renders Display Name / Slug / Description / Schema Definition / skills UI
 * - Create flow POSTs /api/entity-types and calls onSuccess
 * - Edit flow PUTs /api/entity-types/:id with the slug locked
 * - Invalid JSON schema blocks submission with a toast error (no API call)
 * - AI suggest requires a display name; otherwise POSTs
 *   /api/entity-types/suggest-schema and replaces the schema in the editor
 * - Skill pills toggle membership in available_skills
 * - API failure surfaces the server detail and does not call onSuccess
 * - Cancel invokes onCancel
 *
 * axios is mocked with URL routing (pattern: EntitySchemaModal.test.tsx).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import EntityTypeForm from '../EntityTypeForm';

jest.mock('react-hot-toast', () => ({
  toast: { success: jest.fn(), error: jest.fn(), loading: jest.fn(), dismiss: jest.fn() },
}));

const mockToast = require('react-hot-toast').toast as {
  success: jest.Mock;
  error: jest.Mock;
  loading: jest.Mock;
  dismiss: jest.Mock;
};

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
    <textarea data-testid="monaco-editor" value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));

jest.mock('../VisualSchemaBuilder', () => ({
  __esModule: true,
  default: ({ schema, onChange }: { schema: any; onChange: (s: any) => void }) => (
    <div data-testid="visual-builder">
      <button type="button" onClick={() => onChange({ ...schema, properties: { ...(schema?.properties || {}), extra: { type: 'string' } } })}>
        visual-onchange
      </button>
    </div>
  ),
}));

const axiosMock = require('axios').default as {
  get: jest.Mock;
  post: jest.Mock;
  put: jest.Mock;
  delete: jest.Mock;
};

const SKILLS = [
  { id: 'skill-1', name: 'Email Drafting' },
  { id: 'skill-2', name: 'Data Analysis' },
];

const createdPayload = {
  success: true,
  entity_type: { id: 'et-1', slug: 'customer', display_name: 'Customer' },
};

const routeAxios = (overrides: Record<string, jest.Mock> = {}) => {
  axiosMock.get.mockImplementation((url: string) => {
    if (url === '/api/skills') return Promise.resolve({ data: SKILLS });
    return Promise.resolve({ data: [] });
  });
  axiosMock.post.mockImplementation((url: string) => {
    if (url === '/api/entity-types/suggest-schema') {
      return Promise.resolve({
        data: { success: true, data: { type: 'object', properties: { ai_field: { type: 'string' } } } },
      });
    }
    return Promise.resolve({ data: createdPayload });
  });
  axiosMock.put.mockResolvedValue({ data: { success: true } });
  Object.assign(axiosMock, overrides);
};

describe('EntityTypeForm', () => {
  const mockOnSuccess = jest.fn();
  const mockOnCancel = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    routeAxios();
  });

  const renderForm = (entityType?: any) =>
    render(
      <EntityTypeForm
        entityType={entityType}
        onSuccess={mockOnSuccess}
        onCancel={mockOnCancel}
        workspaceId="ws-1"
      />
    );

  test('renders all form fields and loads skills with workspace header', async () => {
    renderForm();

    expect(screen.getByLabelText(/Display Name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Slug/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Description/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /AI SUGGEST/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Create Type/i })).toBeInTheDocument();

    await waitFor(() => {
      expect(axiosMock.get).toHaveBeenCalledWith('/api/skills', {
        headers: { 'X-Workspace-ID': 'ws-1' },
      });
    });
    expect(await screen.findByText('Email Drafting')).toBeInTheDocument();
    expect(screen.getByText('Data Analysis')).toBeInTheDocument();
  });

  test('creates a new entity type on submit', async () => {
    renderForm();

    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Customer' } });
    fireEvent.change(screen.getByLabelText(/Slug/i), { target: { value: 'customer' } });
    fireEvent.change(screen.getByLabelText(/Description/i), { target: { value: 'A customer record' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Type/i }));

    await waitFor(() => {
      expect(axiosMock.post).toHaveBeenCalledWith(
        '/api/entity-types',
        expect.objectContaining({
          slug: 'customer',
          display_name: 'Customer',
          description: 'A customer record',
          json_schema: expect.objectContaining({ type: 'object' }),
          available_skills: [],
        }),
        { headers: { 'X-Workspace-ID': 'ws-1' } }
      );
    });
    expect(mockToast.success).toHaveBeenCalledWith('Entity type created successfully');
    expect(mockOnSuccess).toHaveBeenCalledWith(createdPayload);
  });

  test('edits an existing entity type with the slug locked', async () => {
    const existing = {
      id: 'et-7',
      slug: 'vendor',
      display_name: 'Vendor',
      description: 'Old description',
      json_schema: { type: 'object', properties: {} },
      available_skills: ['skill-1'],
    };

    renderForm(existing);

    await waitFor(() => {
      expect(screen.getByLabelText(/Display Name/i)).toHaveValue('Vendor');
    });
    const slugInput = screen.getByLabelText(/Slug/i);
    expect(slugInput).toHaveValue('vendor');
    expect(slugInput).toBeDisabled();
    expect(screen.getByRole('button', { name: /Update Type/i })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Preferred Vendor' } });
    fireEvent.click(screen.getByRole('button', { name: /Update Type/i }));

    await waitFor(() => {
      expect(axiosMock.put).toHaveBeenCalledWith(
        '/api/entity-types/et-7',
        expect.objectContaining({ slug: 'vendor', display_name: 'Preferred Vendor' }),
        expect.any(Object)
      );
    });
    expect(mockToast.success).toHaveBeenCalledWith('Entity type updated successfully');
    expect(mockOnSuccess).toHaveBeenCalled();
  });

  test('toggling a skill pill adds/removes it from available_skills', async () => {
    renderForm();
    await screen.findByText('Email Drafting');

    fireEvent.click(screen.getByText('Email Drafting'));
    fireEvent.click(screen.getByText('Data Analysis'));

    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Customer' } });
    fireEvent.change(screen.getByLabelText(/Slug/i), { target: { value: 'customer' } });
    fireEvent.click(screen.getByRole('button', { name: /Create Type/i }));

    await waitFor(() => {
      expect(axiosMock.post).toHaveBeenCalledWith(
        '/api/entity-types',
        expect.objectContaining({ available_skills: ['skill-1', 'skill-2'] }),
        expect.any(Object)
      );
    });

    fireEvent.click(screen.getByText('Email Drafting'));
    fireEvent.click(screen.getByRole('button', { name: /Create Type/i }));
    await waitFor(() => {
      expect(axiosMock.post).toHaveBeenLastCalledWith(
        '/api/entity-types',
        expect.objectContaining({ available_skills: ['skill-2'] }),
        expect.any(Object)
      );
    });
  });

  test('blocks submission on an invalid JSON schema and never calls the API', async () => {
    renderForm();
    await screen.findByText('Email Drafting');

    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Customer' } });
    fireEvent.change(screen.getByLabelText(/Slug/i), { target: { value: 'customer' } });

    fireEvent.click(screen.getByRole('button', { name: /CODE EDITOR/i }));
    const editor = screen.getByTestId('monaco-editor');
    fireEvent.change(editor, { target: { value: '{ not valid json' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Type/i }));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith(expect.stringMatching(/Parse error/i));
    });
    expect(axiosMock.post).not.toHaveBeenCalled();
    expect(mockOnSuccess).not.toHaveBeenCalled();
  });

  test('blocks submission when the schema root is not an object', async () => {
    renderForm();
    await screen.findByText('Email Drafting');

    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Customer' } });
    fireEvent.change(screen.getByLabelText(/Slug/i), { target: { value: 'customer' } });

    fireEvent.click(screen.getByRole('button', { name: /CODE EDITOR/i }));
    fireEvent.change(screen.getByTestId('monaco-editor'), { target: { value: '{"type": "string"}' } });

    fireEvent.click(screen.getByRole('button', { name: /Create Type/i }));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith(expect.stringMatching(/Invalid Schema/i));
    });
    expect(axiosMock.post).not.toHaveBeenCalled();
  });

  test('AI suggest is disabled until a display name is entered', async () => {
    renderForm();
    await screen.findByText('Email Drafting');

    const suggestBtn = screen.getByRole('button', { name: /AI SUGGEST/i });
    expect(suggestBtn).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Lead' } });
    expect(suggestBtn).not.toBeDisabled();
    expect(axiosMock.post).not.toHaveBeenCalled();
  });

  test('AI suggest replaces the schema in the editor', async () => {
    renderForm();
    await screen.findByText('Email Drafting');

    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Lead' } });
    fireEvent.change(screen.getByLabelText(/Description/i), { target: { value: 'Lead entity' } });

    fireEvent.click(screen.getByRole('button', { name: /AI SUGGEST/i }));

    await waitFor(() => {
      expect(axiosMock.post).toHaveBeenCalledWith(
        '/api/entity-types/suggest-schema',
        { display_name: 'Lead', description: 'Lead entity' },
        { headers: { 'X-Workspace-ID': 'ws-1' } }
      );
    });

    // The editor now holds the AI-suggested schema
    fireEvent.click(screen.getByRole('button', { name: /CODE EDITOR/i }));
    const editor = screen.getByTestId('monaco-editor') as HTMLTextAreaElement;
    expect(JSON.parse(editor.value)).toEqual({
      type: 'object',
      properties: { ai_field: { type: 'string' } },
    });
    expect(mockToast.success).toHaveBeenCalledWith('Schema suggested by AI!');
  });

  test('surfaces the API error detail from the server', async () => {
    axiosMock.post.mockRejectedValue({
      response: { data: { detail: 'slug already exists' } },
    });

    renderForm();
    await screen.findByText('Email Drafting');

    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Customer' } });
    fireEvent.change(screen.getByLabelText(/Slug/i), { target: { value: 'customer' } });
    fireEvent.click(screen.getByRole('button', { name: /Create Type/i }));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('slug already exists');
    });
    expect(mockOnSuccess).not.toHaveBeenCalled();
  });

  test('cancel invokes onCancel', async () => {
    renderForm();
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(mockOnCancel).toHaveBeenCalled();
  });
});
