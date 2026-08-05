/**
 * HubSpotSearch Component Tests
 *
 * Tests verify the real HubSpotSearch component
 * (components/integrations/hubspot/HubSpotSearch.tsx) — a pure props-driven
 * search / filter / sort UI. It makes no network calls, so no MSW handlers
 * are needed; data + dataType + onSearch are passed in as props and results
 * are filtered/sorted/previewed internally (onSearch is debounced 300ms).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import HubSpotSearch from '@/components/integrations/hubspot/HubSpotSearch';

// The ui/spinner module references React without importing it, which throws
// "React is not defined" in the test runtime whenever the loading state
// renders the real Spinner. Mock it to a plain div so the component's own
// "Searching..." label can still be asserted.
jest.mock('@/components/ui/spinner', () => ({
  Spinner: ({ className }: { className?: string }) => (
    <div data-testid="spinner" className={className} />
  ),
}));

const mockContacts = [
  {
    id: '1',
    firstName: 'John',
    lastName: 'Doe',
    email: 'john.doe@example.com',
    company: 'Acme Corp',
    phone: '+1234567890',
    lifecycleStage: 'customer',
    leadStatus: 'qualified',
    leadScore: 85,
    lastActivityDate: '2026-04-20',
    createdDate: '2026-01-15',
    owner: 'Jane Smith',
    industry: 'Technology',
    country: 'USA',
  },
  {
    id: '2',
    firstName: 'Jane',
    lastName: 'Smith',
    email: 'jane.smith@example.com',
    company: 'Tech Startup',
    phone: '+0987654321',
    lifecycleStage: 'lead',
    leadStatus: 'new',
    leadScore: 45,
    lastActivityDate: '2026-04-18',
    createdDate: '2026-02-01',
    owner: 'Bob Johnson',
    industry: 'Healthcare',
    country: 'Canada',
  },
];

const mockCompanies = [
  {
    id: '1',
    name: 'Acme Corp',
    domain: 'acme.com',
    industry: 'Technology',
    size: 'Enterprise',
    country: 'USA',
    city: 'San Francisco',
    annualRevenue: 5000000,
    owner: 'Jane Smith',
    lastActivityDate: '2026-04-20',
    createdDate: '2026-01-15',
    dealStage: 'proposal',
  },
];

const mockOnSearch = jest.fn();

const renderSearch = (overrides: Partial<React.ComponentProps<typeof HubSpotSearch>> = {}) => {
  const defaultProps = {
    data: mockContacts,
    dataType: 'contacts' as const,
    onSearch: mockOnSearch,
  };
  return render(<HubSpotSearch {...defaultProps} {...overrides} />);
};

describe('HubSpotSearch', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders the search input and heading
  test('renders search input field', () => {
    renderSearch();

    expect(screen.getByText('HubSpot Search')).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/search contacts, companies, deals, activities/i)
    ).toBeInTheDocument();
  });

  // Test 2: shows search results when provided
  test('shows search results when provided', () => {
    renderSearch({ totalCount: 2 });

    expect(screen.getByText('Showing 2 of 2 results')).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
  });

  // Test 3: shows loading spinner when loading=true
  test('shows loading spinner when loading=true', () => {
    renderSearch({ loading: true });

    expect(screen.getByTestId('spinner')).toBeInTheDocument();
    expect(screen.getByText('Searching...')).toBeInTheDocument();
  });

  // Test 4: shows empty state when no results found
  test('shows empty state when no results found', async () => {
    renderSearch({ data: [], totalCount: 0 });

    const searchInput = screen.getByPlaceholderText(
      /search contacts, companies, deals, activities/i
    );
    fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

    await waitFor(() => {
      expect(screen.getByText(/no results found/i)).toBeInTheDocument();
    });
  });

  // Test 5: calls onSearch with filtered results (debounced 300ms)
  test('calls onSearch with filtered results', async () => {
    renderSearch();

    await waitFor(
      () => {
        expect(mockOnSearch).toHaveBeenCalled();
      },
      { timeout: 1500 }
    );

    // onSearch receives (results, filters, sort)
    const [results, filters] = mockOnSearch.mock.calls[0] as [any[], any, any];
    expect(results).toHaveLength(2);
    expect(filters.dataType).toBe('contacts');
  });

  // Test 6: filters the results preview by search query
  test('filters results by search query', async () => {
    renderSearch({ totalCount: 2 });

    const searchInput = screen.getByPlaceholderText(
      /search contacts, companies, deals, activities/i
    );
    await userEvent.type(searchInput, 'Jane');

    await waitFor(() => {
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    });
    expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
  });

  // Test 7: displays the data type filter dropdown
  test('displays data type filter dropdown', () => {
    renderSearch();

    // Two native <select> elements: data type + sort field
    expect(screen.getAllByRole('combobox')).toHaveLength(2);
    // The data type select shows the selected option's display text "Contacts"
    expect(screen.getByDisplayValue('Contacts')).toBeInTheDocument();
    // The results badge shows the active data type in uppercase
    expect(screen.getByText('CONTACTS')).toBeInTheDocument();
  });

  // Test 8: toggles advanced filters panel
  test('toggles advanced filters panel', async () => {
    renderSearch();

    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));

    await waitFor(() => {
      expect(screen.getByText('Industry')).toBeInTheDocument();
      expect(screen.getByText('Country')).toBeInTheDocument();
      expect(screen.getByText('Lifecycle Stage')).toBeInTheDocument();
    });
  });

  // Test 9: clears all filters when clear button clicked
  test('clears all filters when clear button clicked', async () => {
    renderSearch();

    const searchInput = screen.getByPlaceholderText(
      /search contacts, companies, deals, activities/i
    );
    await userEvent.type(searchInput, 'John');

    fireEvent.click(screen.getByRole('button', { name: /clear all/i }));

    expect(searchInput).toHaveValue('');
  });

  // Test 10: applies an industry filter via checkbox
  test('filters by industry when checkbox is selected', async () => {
    renderSearch({ totalCount: 2 });

    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));

    await waitFor(() => {
      expect(screen.getByText('Industry')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('checkbox', { name: 'Technology' }));

    await waitFor(() => {
      expect(screen.getByText('Industry: Technology')).toBeInTheDocument();
    });
  });

  // Test 11: changing the sort field triggers a re-search
  test('changes sort field triggers re-search', async () => {
    renderSearch({ totalCount: 2 });

    const sortDropdown = screen.getByDisplayValue(/sort by last activity/i);
    fireEvent.change(sortDropdown, { target: { value: 'createdDate' } });

    await waitFor(
      () => {
        expect(mockOnSearch).toHaveBeenCalled();
      },
      { timeout: 1500 }
    );
  });

  // Test 12: displays the sort direction badge
  test('displays sort direction badge', () => {
    renderSearch();

    expect(screen.getByText('↓ Desc')).toBeInTheDocument();
  });
});
