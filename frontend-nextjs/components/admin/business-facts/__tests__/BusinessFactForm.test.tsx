/**
 * BusinessFactForm component tests.
 *
 * Covers the REAL BusinessFactForm (components/admin/business-facts/BusinessFactForm.tsx):
 * - Create mode: empty fields, validation toasts (fact/domain/citations required),
 *   successful createFact call with parsed citations, onSubmit + toast on success,
 *   error toast on API failure, Cancel calls onCancel
 * - Edit mode: pre-filled values (incl. verification status select), updateFact
 *   called with fact id + verification_status, success toast + onSubmit
 *
 * businessFactsAPI is mocked at module level (it wraps axios); the toast hook is
 * mocked following components/Settings/__tests__/ThirdPartyIntegrations.test.tsx.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BusinessFactForm } from '../BusinessFactForm';
import { businessFactsAPI } from '@/lib/api-admin';
import type { BusinessFact } from '@/types/jit-verification';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

jest.mock('@/lib/api-admin', () => ({
  businessFactsAPI: {
    createFact: jest.fn(),
    updateFact: jest.fn(),
  },
}));

const createFactMock = businessFactsAPI.createFact as jest.Mock;
const updateFactMock = businessFactsAPI.updateFact as jest.Mock;

const editFact: BusinessFact = {
  id: 'fact-1',
  fact: 'Invoices over $500 require VP approval',
  citations: [
    'https://bucket.s3.amazonaws.com/policy.pdf',
    'https://bucket.s3.amazonaws.com/handbook.pdf',
  ],
  reason: 'Ensures proper oversight of large expenditures',
  domain: 'finance',
  verification_status: 'verified',
  created_at: '2026-01-01T00:00:00Z',
  last_verified: '2026-01-01T00:00:00Z',
};

describe('BusinessFactForm', () => {
  const onSubmit = jest.fn();
  const onCancel = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    createFactMock.mockResolvedValue({ data: { ...editFact } });
    updateFactMock.mockResolvedValue({ data: { ...editFact } });
  });

  const fillCreateForm = () => {
    fireEvent.change(screen.getByLabelText(/Fact \*/), {
      target: { value: 'Invoices over $500 require VP approval' },
    });
    fireEvent.change(screen.getByLabelText(/Domain \*/), {
      target: { value: 'finance' },
    });
    fireEvent.change(screen.getByLabelText(/Citations \*/), {
      target: { value: 'https://bucket.s3.amazonaws.com/policy.pdf\nhttps://bucket.s3.amazonaws.com/handbook.pdf' },
    });
    fireEvent.change(screen.getByLabelText(/Reason/), {
      target: { value: 'Ensures oversight' },
    });
  };

  it('renders the create form with empty fields and correct title', () => {
    render(<BusinessFactForm onSubmit={onSubmit} onCancel={onCancel} />);

    expect(screen.getByText('Create Business Fact')).toBeInTheDocument();
    expect(screen.getByText('Add a new business fact with citation verification')).toBeInTheDocument();
    expect((screen.getByLabelText(/Fact \*/) as HTMLTextAreaElement).value).toBe('');
    expect((screen.getByLabelText(/Domain \*/) as HTMLInputElement).value).toBe('');
    expect(screen.getByRole('button', { name: 'Create Fact' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    // Verification status select is edit-only
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('shows validation toast and does not call the API when fact text is missing', () => {
    const { container } = render(<BusinessFactForm onSubmit={onSubmit} onCancel={onCancel} />);

    fireEvent.change(screen.getByLabelText(/Domain \*/), { target: { value: 'finance' } });
    fireEvent.change(screen.getByLabelText(/Citations \*/), { target: { value: 'https://a.com' } });
    // Note: dispatch submit directly on the form — jsdom constraint validation
    // blocks click-submits on empty `required` fields (same as a real browser).
    fireEvent.submit(document.querySelector('form')!);

    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Validation error', description: 'Fact text is required' })
    );
    expect(createFactMock).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('shows validation toast when domain is missing', () => {
    const { container } = render(<BusinessFactForm onSubmit={onSubmit} onCancel={onCancel} />);

    fireEvent.change(screen.getByLabelText(/Fact \*/), { target: { value: 'Some fact' } });
    fireEvent.change(screen.getByLabelText(/Citations \*/), { target: { value: 'https://a.com' } });
    fireEvent.submit(document.querySelector('form')!);

    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Validation error', description: 'Domain is required' })
    );
    expect(createFactMock).not.toHaveBeenCalled();
  });

  it('shows validation toast when no citations are provided', () => {
    const { container } = render(<BusinessFactForm onSubmit={onSubmit} onCancel={onCancel} />);

    fireEvent.change(screen.getByLabelText(/Fact \*/), { target: { value: 'Some fact' } });
    fireEvent.change(screen.getByLabelText(/Domain \*/), { target: { value: 'finance' } });
    fireEvent.submit(document.querySelector('form')!);

    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Validation error', description: 'At least one citation is required' })
    );
    expect(createFactMock).not.toHaveBeenCalled();
  });

  it('creates a fact: parses newline-separated citations, calls createFact and onSubmit', async () => {
    render(<BusinessFactForm onSubmit={onSubmit} onCancel={onCancel} />);
    fillCreateForm();

    fireEvent.click(screen.getByRole('button', { name: 'Create Fact' }));

    await waitFor(() => {
      expect(createFactMock).toHaveBeenCalledWith({
        fact: 'Invoices over $500 require VP approval',
        citations: [
          'https://bucket.s3.amazonaws.com/policy.pdf',
          'https://bucket.s3.amazonaws.com/handbook.pdf',
        ],
        reason: 'Ensures oversight',
        domain: 'finance',
      });
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Fact created' })
    );
    expect(onSubmit).toHaveBeenCalled();
  });

  it('shows an error toast when creation fails and does not call onSubmit', async () => {
    createFactMock.mockRejectedValue({ userMessage: 'backend exploded' });
    render(<BusinessFactForm onSubmit={onSubmit} onCancel={onCancel} />);
    fillCreateForm();

    fireEvent.click(screen.getByRole('button', { name: 'Create Fact' }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Creation failed', description: 'backend exploded', variant: 'destructive' })
      );
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('pre-fills form values in edit mode including the verification status select', () => {
    render(<BusinessFactForm fact={editFact} onSubmit={onSubmit} onCancel={onCancel} />);

    expect(screen.getByText('Edit Business Fact')).toBeInTheDocument();
    expect((screen.getByLabelText(/Fact \*/) as HTMLTextAreaElement).value).toBe(editFact.fact);
    expect((screen.getByLabelText(/Domain \*/) as HTMLInputElement).value).toBe('finance');
    expect((screen.getByLabelText(/Citations \*/) as HTMLTextAreaElement).value).toContain('policy.pdf');
    expect((screen.getByLabelText(/Reason/) as HTMLTextAreaElement).value).toBe(editFact.reason);
    // Radix Select trigger shows the current value
    expect(screen.getByRole('combobox')).toHaveTextContent('Verified');
  });

  it('updates an existing fact with the selected verification status', async () => {
    render(<BusinessFactForm fact={editFact} onSubmit={onSubmit} onCancel={onCancel} />);

    fireEvent.click(screen.getByRole('combobox'));
    const option = await screen.findByRole('option', { name: 'Unverified' });
    fireEvent.click(option);

    fireEvent.click(screen.getByRole('button', { name: 'Update Fact' }));

    await waitFor(() => {
      expect(updateFactMock).toHaveBeenCalledWith('fact-1', {
        fact: editFact.fact,
        citations: editFact.citations,
        reason: editFact.reason,
        domain: 'finance',
        verification_status: 'unverified',
      });
    });
    expect(mockToast.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Fact updated' })
    );
    expect(onSubmit).toHaveBeenCalled();
  });

  it('shows an error toast when the update fails', async () => {
    updateFactMock.mockRejectedValue({ userMessage: 'update failed' });
    render(<BusinessFactForm fact={editFact} onSubmit={onSubmit} onCancel={onCancel} />);

    fireEvent.click(screen.getByRole('button', { name: 'Update Fact' }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Update failed', description: 'update failed', variant: 'destructive' })
      );
    });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('calls onCancel when Cancel is clicked', () => {
    render(<BusinessFactForm onSubmit={onSubmit} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalled();
  });
});
