/**
 * EntityTypeList Component Tests
 *
 * Covers the REAL EntityTypeList (components/entity/EntityTypeList.tsx):
 * - Fetches /api/entity-types on mount (workspace_id param, include_system off)
 * - Renders the count line and EntityTypeCard grid
 * - Search filters cards by name/slug/description; Clear resets
 * - "Include System Types" checkbox refetches with include_system=true
 * - Refresh button re-fetches; Retry re-fetches after an error
 * - Error state shows the message + toast; empty state shows the CTA
 * - "Create Entity Type" opens the real EntityTypeForm dialog; creating an
 *   entity refreshes the list
 * - Portability opens the import/export dialog
 *
 * next-auth session + sonner toast are mocked; axios is mocked with URL
 * routing; @rjsf (used by VisualSchemaBuilder's preview) is stubbed to null
 * (same as EntitySchemaModal.test.tsx).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { EntityTypeList } from '../EntityTypeList';

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

const mockSonner = require('sonner').toast as {
  success: jest.Mock;
  error: jest.Mock;
  info: jest.Mock;
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

const axiosMock = require('axios').default as {
  get: jest.Mock;
  post: jest.Mock;
  put: jest.Mock;
  delete: jest.Mock;
};

const mockUseSession = jest.fn();
jest.mock('next-auth/react', () => ({
  useSession: () => mockUseSession(),
}));

jest.mock('@rjsf/core', () => ({
  __esModule: true,
  default: () => null,
}));
jest.mock('@rjsf/validator-ajv8', () => ({
  __esModule: true,
  default: () => null,
}));

const entityTypes = [
  {
    id: 'et-1',
    tenant_id: 't1',
    slug: 'customer',
    display_name: 'Customer',
    description: 'A customer record',
    json_schema: { type: 'object', properties: { name: { type: 'string' } } },
    available_skills: [],
    is_active: true,
    is_system: false,
    version: 1,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'et-2',
    tenant_id: 't1',
    slug: 'vendor',
    display_name: 'Vendor',
    description: 'A vendor record',
    json_schema: { type: 'object', properties: { name: { type: 'string' } } },
    available_skills: [],
    is_active: true,
    is_system: false,
    version: 3,
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
  {
    id: 'et-3',
    tenant_id: 't1',
    slug: 'invoice',
    display_name: 'Invoice',
    description: 'Billing record',
    json_schema: { type: 'object', properties: { total: { type: 'number' } } },
    available_skills: [],
    is_active: true,
    is_system: true,
    version: 2,
    created_at: '2026-01-03T00:00:00Z',
    updated_at: '2026-01-03T00:00:00Z',
  },
];

describe('EntityTypeList', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseSession.mockReturnValue({ data: { user: { workspace_id: 'ws-1' } }, status: 'authenticated' });
    axiosMock.get.mockImplementation((url: string, config?: any) => {
      if (url === '/api/skills') return Promise.resolve({ data: [] });
      return Promise.resolve({ data: { success: true, data: entityTypes } });
    });
    axiosMock.post.mockResolvedValue({ data: { success: true, entity_type: { id: 'et-9' } } });
    axiosMock.put.mockResolvedValue({ data: { success: true } });
  });

  test('fetches entity types on mount and renders the cards', async () => {
    render(<EntityTypeList />);

    await waitFor(() => {
      expect(axiosMock.get).toHaveBeenCalledWith('/api/entity-types', {
        params: { workspace_id: 'ws-1', include_system: false },
      });
    });

    expect(await screen.findByText('Customer')).toBeInTheDocument();
    expect(screen.getByText('Vendor')).toBeInTheDocument();
    expect(screen.getByText('Showing 3 of 3 entity types')).toBeInTheDocument();
    expect(screen.getAllByText('Custom').length).toBe(2); // et-1 + et-2
    expect(screen.getByText('System')).toBeInTheDocument(); // et-3
  });

  test('search filters the cards by name and slug; Clear resets', async () => {
    render(<EntityTypeList />);
    await screen.findByText('Customer');

    const searchInput = screen.getByPlaceholderText(/Search entity types/i);
    fireEvent.change(searchInput, { target: { value: 'vend' } });

    expect(screen.getByText('Vendor')).toBeInTheDocument();
    expect(screen.queryByText('Customer')).not.toBeInTheDocument();
    expect(screen.getByText('Showing 1 of 3 entity types')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Clear/i }));
    expect(searchInput).toHaveValue('');
    expect(screen.getByText('Customer')).toBeInTheDocument();
    expect(screen.getByText('Showing 3 of 3 entity types')).toBeInTheDocument();
  });

  test('searching for an unknown term shows the empty grid state', async () => {
    render(<EntityTypeList />);
    await screen.findByText('Customer');

    fireEvent.change(screen.getByPlaceholderText(/Search entity types/i), {
      target: { value: 'zzz-no-match' },
    });

    expect(screen.getByText('Showing 0 of 3 entity types')).toBeInTheDocument();
    expect(screen.queryByText('Customer')).not.toBeInTheDocument();
  });

  test('Include System Types checkbox refetches with include_system=true', async () => {
    render(<EntityTypeList />);
    await screen.findByText('Customer');

    fireEvent.click(screen.getByLabelText('Include System Types'));

    await waitFor(() => {
      expect(axiosMock.get).toHaveBeenLastCalledWith('/api/entity-types', {
        params: { workspace_id: 'ws-1', include_system: true },
      });
    });
  });

  test('refresh button re-fetches the list', async () => {
    render(<EntityTypeList />);
    await screen.findByText('Customer');
    const callsBefore = axiosMock.get.mock.calls.length;

    fireEvent.click(screen.getByTitle('Refresh entity types'));

    await waitFor(() => {
      expect(axiosMock.get.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });

  test('renders the error state with the API message and retries', async () => {
    axiosMock.get.mockRejectedValue(new Error('boom'));

    render(<EntityTypeList />);

    expect(await screen.findByText('Error Loading Entity Types')).toBeInTheDocument();
    expect(screen.getByText('boom')).toBeInTheDocument();
    expect(mockSonner.error).toHaveBeenCalledWith('boom');

    // Retry succeeds and renders the list
    axiosMock.get.mockResolvedValue({ data: { success: true, data: entityTypes } });
    fireEvent.click(screen.getByRole('button', { name: /Retry/i }));

    expect(await screen.findByText('Customer')).toBeInTheDocument();
    expect(screen.queryByText('Error Loading Entity Types')).not.toBeInTheDocument();
  });

  test('renders the empty state when the API returns no types', async () => {
    axiosMock.get.mockResolvedValue({ data: { success: true, data: [] } });

    render(<EntityTypeList />);

    expect(await screen.findByText('No Entity Types Found')).toBeInTheDocument();
    expect(screen.getByText(/Create your first entity type/i)).toBeInTheDocument();
    expect(screen.getByText('Showing 0 of 0 entity types')).toBeInTheDocument();
  });

  test('Create Entity Type opens the form dialog and refresh happens after success', async () => {
    render(<EntityTypeList />);
    await screen.findByText('Customer');

    fireEvent.click(screen.getByRole('button', { name: /Create Entity Type/i }));

    expect(await screen.findByText('Create New Entity Type')).toBeInTheDocument();
    expect(screen.getByLabelText(/Display Name/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Display Name/i), { target: { value: 'Lead' } });
    fireEvent.change(screen.getByLabelText(/Slug/i), { target: { value: 'lead' } });
    fireEvent.click(screen.getByRole('button', { name: /Create Type/i }));

    await waitFor(() => {
      expect(axiosMock.post).toHaveBeenCalledWith('/api/entity-types', expect.any(Object), {
        headers: { 'X-Workspace-ID': 'ws-1' },
      });
    });
    // onSuccess closes the dialog and refetches the list
    await waitFor(() => {
      expect(axiosMock.get.mock.calls.length).toBeGreaterThan(1);
    });
    expect(screen.queryByText('Create New Entity Type')).not.toBeInTheDocument();
  });

  test('Portability button opens the import/export dialog', async () => {
    render(<EntityTypeList />);
    await screen.findByText('Customer');

    fireEvent.click(screen.getByRole('button', { name: /Portability/i }));

    expect(await screen.findByText('Portability Engine')).toBeInTheDocument();
  });
});
