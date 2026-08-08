/**
 * EntityTypeImportExport Component Tests
 *
 * Covers the REAL EntityTypeImportExport (components/entity/EntityTypeImportExport.tsx):
 * - Renders the "Portability Engine" dialog only when open
 * - Full-registry export: JSON / YAML buttons build a Blob of the entity types,
 *   trigger a download, and toast success (real js-yaml serialization)
 * - Per-type export buttons serialize only that single type
 * - Import tab: parsing a valid JSON definition file POSTs it to
 *   /api/entity-types (real parseEntityTypeDefinition validation) and shows
 *   the success/failure breakdown + calls onImportComplete
 * - Malformed files surface per-file parse errors in the error breakdown
 * - Close Engine invokes onClose
 *
 * next-auth session is mocked; axios is mocked (importer uses axios.post);
 * sonner toast is mocked.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { EntityTypeImportExport } from '../EntityTypeImportExport';

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

const entityTypes = [
  {
    slug: 'customer',
    display_name: 'Customer',
    description: 'A customer record',
    json_schema: { type: 'object', properties: { name: { type: 'string' } } },
  },
  {
    slug: 'vendor',
    display_name: 'Vendor',
    json_schema: { type: 'object', properties: { name: { type: 'string' } } },
  },
];

const VALID_DEF = JSON.stringify({
  slug: 'lead',
  display_name: 'Lead',
  json_schema: { type: 'object', properties: { email: { type: 'string' } } },
});

describe('EntityTypeImportExport', () => {
  const mockOnClose = jest.fn();
  const mockOnImportComplete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseSession.mockReturnValue({ data: { user: { workspace_id: 'ws-9' } }, status: 'authenticated' });
    axiosMock.post.mockResolvedValue({ data: { success: true } });
  });

  const renderDialog = (isOpen = true) =>
    render(
      <EntityTypeImportExport
        isOpen={isOpen}
        onClose={mockOnClose}
        entityTypes={entityTypes}
        onImportComplete={mockOnImportComplete}
      />
    );

  test('renders the Portability Engine when open and nothing when closed', () => {
    renderDialog(false);
    expect(screen.queryByText('Portability Engine')).not.toBeInTheDocument();

    renderDialog(true);
    expect(screen.getByText('Portability Engine')).toBeInTheDocument();
    expect(screen.getByText(/Sync your entity ecosystem/i)).toBeInTheDocument();
    expect(screen.getByText('Export definitions')).toBeInTheDocument();
    expect(screen.getByText('Import definitions')).toBeInTheDocument();
  });

  test('exports the full registry as JSON', async () => {
    renderDialog();

    fireEvent.click(screen.getByRole('button', { name: /JSON format/i }));

    await waitFor(() => {
      expect(global.URL.createObjectURL).toHaveBeenCalled();
    });
    const blob = (global.URL.createObjectURL as jest.Mock).mock.calls[0][0] as Blob;
    const content = JSON.parse(await blob.text());
    expect(content).toEqual(entityTypes);

    expect(mockSonner.success).toHaveBeenCalledWith('JSON Exported successfully');
  });

  test('exports the full registry as YAML via js-yaml', async () => {
    renderDialog();

    fireEvent.click(screen.getByRole('button', { name: /YAML format/i }));

    await waitFor(() => {
      expect(global.URL.createObjectURL).toHaveBeenCalled();
    });
    const blob = (global.URL.createObjectURL as jest.Mock).mock.calls[0][0] as Blob;
    const text = await blob.text();
    expect(text).toContain('display_name: Customer');
    expect(text).toContain('slug: customer');
    expect(text).toContain('slug: vendor');

    expect(mockSonner.success).toHaveBeenCalledWith('YAML Exported successfully');
  });

  test('lists specific types with per-type export buttons', async () => {
    renderDialog();

    expect(screen.getByText('Customer')).toBeInTheDocument();
    expect(screen.getByText('Vendor')).toBeInTheDocument();
    expect(screen.getByText(/Download all 2 custom entity types/i)).toBeInTheDocument();

    // Per-type buttons are hidden (opacity-0) but still in the DOM. Exact
    // name match picks the per-type buttons, not "JSON format"/"YAML format".
    const jsonButtons = screen.getAllByRole('button', { name: 'JSON' });
    expect(jsonButtons.length).toBe(2);

    fireEvent.click(jsonButtons[0]);
    await waitFor(() => {
      expect(global.URL.createObjectURL).toHaveBeenCalled();
    });
    const blob = (global.URL.createObjectURL as jest.Mock).mock.calls[0][0] as Blob;
    const parsed = JSON.parse(await blob.text());
    expect(parsed.slug).toBe('customer');
    expect(parsed.display_name).toBe('Customer');
  });

  test('imports a valid JSON definition file and reports success', async () => {
    renderDialog();
    fireEvent.click(screen.getByRole('button', { name: /Import definitions/i }));

    expect(screen.getByText('Drop definitions here')).toBeInTheDocument();

    const file = new File([VALID_DEF], 'lead.json', { type: 'application/json' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(axiosMock.post).toHaveBeenCalledWith(
        '/api/entity-types',
        JSON.parse(VALID_DEF),
        { headers: { 'X-Workspace-ID': 'ws-9' } }
      );
    });

    expect(await screen.findByText('Import Finished')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument(); // successes count
    expect(screen.getByText('0')).toBeInTheDocument(); // failures count
    expect(mockOnImportComplete).toHaveBeenCalled();
  });

  test('reports parse errors for malformed files without calling the API', async () => {
    renderDialog();
    fireEvent.click(screen.getByRole('button', { name: /Import definitions/i }));

    const file = new File(['{ this is not json'], 'broken.json', { type: 'application/json' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText('Import Finished')).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('broken.json')).toBeInTheDocument();
    expect(screen.getByText(/Parse error in broken.json/i)).toBeInTheDocument();
    expect(axiosMock.post).not.toHaveBeenCalled();
    expect(mockOnImportComplete).not.toHaveBeenCalled();
  });

  test('surfaces server-side import failures in the error breakdown', async () => {
    axiosMock.post.mockRejectedValue({ response: { data: { detail: 'slug conflict' } } });

    renderDialog();
    fireEvent.click(screen.getByRole('button', { name: /Import definitions/i }));

    const file = new File([VALID_DEF], 'lead.json', { type: 'application/json' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText('Import Finished')).toBeInTheDocument();
    expect(screen.getByText('0')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('lead')).toBeInTheDocument(); // slug used as the error label
    expect(screen.getByText('slug conflict')).toBeInTheDocument();
    // onImportComplete is only called when at least one import succeeds
    expect(mockOnImportComplete).not.toHaveBeenCalled();
  });

  test('Clear Results resets back to the upload dropzone', async () => {
    renderDialog();
    fireEvent.click(screen.getByRole('button', { name: /Import definitions/i }));

    const file = new File([VALID_DEF], 'lead.json', { type: 'application/json' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await screen.findByText('Import Finished');
    fireEvent.click(screen.getByRole('button', { name: /Clear Results/i }));

    expect(screen.getByText('Drop definitions here')).toBeInTheDocument();
    expect(screen.queryByText('Import Finished')).not.toBeInTheDocument();
  });

  test('Close Engine invokes onClose', () => {
    renderDialog();
    fireEvent.click(screen.getByRole('button', { name: /Close Engine/i }));
    expect(mockOnClose).toHaveBeenCalled();
  });
});
