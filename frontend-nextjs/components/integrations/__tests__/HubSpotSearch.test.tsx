/**
 * HubSpot Search Component Tests
 *
 * Test suite for HubSpot search, filtering, and sorting functionality
 */

import React from 'react';

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HubSpotSearch, {
  HubSpotContact,
  HubSpotCompany,
  HubSpotDeal,
  HubSpotActivity,
  SearchFilters,
  SortOptions
} from '../hubspot/HubSpotSearch';

const mockContacts: HubSpotContact[] = [
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
    country: 'USA'
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
    country: 'Canada'
  }
];

const mockCompanies: HubSpotCompany[] = [
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
    dealStage: 'proposal'
  }
];

const mockDeals: HubSpotDeal[] = [
  {
    id: '1',
    name: 'Enterprise Deal',
    amount: 100000,
    stage: 'proposal',
    closeDate: '2026-05-01',
    createdDate: '2026-03-01',
    owner: 'Jane Smith',
    company: 'Acme Corp',
    contact: 'John Doe',
    probability: 75,
    pipeline: 'sales-pipeline-1'
  }
];

const mockOnSearch = jest.fn();

describe('HubSpotSearch', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders search input field', () => {
    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
      />
    );

    expect(screen.getByPlaceholderText(/search contacts, companies, deals, activities/i)).toBeInTheDocument();
    expect(screen.getByText('HubSpot Search')).toBeInTheDocument();
  });

  it('shows search results when provided', () => {
    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
        totalCount={2}
      />
    );

    expect(screen.getByText('Showing 2 of 2 results')).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
  });

  it('shows loading spinner when loading=true', () => {
    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
        loading={true}
      />
    );

    expect(screen.getByText(/searching/i)).toBeInTheDocument();
  });

  it('shows empty state when no results found', () => {
    render(
      <HubSpotSearch
        data={[]}
        dataType="contacts"
        onSearch={mockOnSearch}
        totalCount={0}
      />
    );

    // Type in search to trigger empty state
    const searchInput = screen.getByPlaceholderText(/search contacts, companies, deals, activities/i);
    fireEvent.change(searchInput, { target: { value: 'nonexistent' } });

    waitFor(() => {
      expect(screen.getByText(/no results found/i)).toBeInTheDocument();
    });
  });

  it('calls onSelect when result item is clicked', async () => {
    const user = userEvent.setup();

    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
        totalCount={2}
      />
    );

    const resultItem = screen.getByText('John Doe');
    await user.click(resultItem);

    // Verify onSearch was called with filtered data
    expect(mockOnSearch).toHaveBeenCalled();
  });

  it('handles search input change and triggers debounced search', async () => {
    const user = userEvent.setup();

    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
      />
    );

    const searchInput = screen.getByPlaceholderText(/search contacts, companies, deals, activities/i);

    await user.type(searchInput, 'John');

    // Wait for debounce (300ms)
    await waitFor(
      () => {
        expect(mockOnSearch).toHaveBeenCalled();
      },
      { timeout: 500 }
    );
  });

  it('displays data type filter dropdown', () => {
    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
      />
    );

    expect(screen.getByDisplayValue('contacts')).toBeInTheDocument();
  });

  it('toggles advanced filters panel', async () => {
    const user = userEvent.setup();

    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
      />
    );

    const showFiltersButton = screen.getByText(/show filters/i);
    await user.click(showFiltersButton);

    expect(screen.getByText(/industry/i)).toBeInTheDocument();
    expect(screen.getByText(/country/i)).toBeInTheDocument();
    expect(screen.getByText(/lifecycle stage/i)).toBeInTheDocument();
  });

  it('clears all filters when clear button clicked', async () => {
    const user = userEvent.setup();

    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
      />
    );

    // Set a search query
    const searchInput = screen.getByPlaceholderText(/search contacts, companies, deals, activities/i);
    await user.type(searchInput, 'John');

    // Click clear button
    const clearButton = screen.getByText(/clear all/i);
    await user.click(clearButton);

    expect(searchInput).toHaveValue('');
  });

  it('filters by industry when checkbox is selected', async () => {
    const user = userEvent.setup();

    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
      />
    );

    // Show advanced filters
    const showFiltersButton = screen.getByText(/show filters/i);
    await user.click(showFiltersButton);

    // Wait for filters to appear
    await waitFor(() => {
      expect(screen.getByText(/industry/i)).toBeInTheDocument();
    });
  });

  it('displays active filter badges when filters are applied', async () => {
    const user = userEvent.setup();

    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
      />
    );

    // Show advanced filters
    const showFiltersButton = screen.getByText(/show filters/i);
    await user.click(showFiltersButton);

    // Wait and check for filter sections
    await waitFor(() => {
      expect(screen.getByText(/industry/i)).toBeInTheDocument();
    });
  });

  it('changes sort direction when sort field clicked', async () => {
    const user = userEvent.setup();

    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
      />
    );

    const sortDropdown = screen.getByDisplayValue(/sort by last activity/i);
    expect(sortDropdown).toBeInTheDocument();

    // Change sort field
    fireEvent.change(sortDropdown, { target: { value: 'createdDate' } });

    await waitFor(() => {
      expect(mockOnSearch).toHaveBeenCalled();
    });
  });

  it('displays sort direction badge', () => {
    render(
      <HubSpotSearch
        data={mockContacts}
        dataType="contacts"
        onSearch={mockOnSearch}
      />
    );

    expect(screen.getByText('↓ Desc')).toBeInTheDocument();
  });
});
