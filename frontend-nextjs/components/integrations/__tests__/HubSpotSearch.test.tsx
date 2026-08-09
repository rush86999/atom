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
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
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

const mockDeals = [
  {
    id: 'd1',
    name: 'Acme Renewal',
    amount: 50000,
    stage: 'proposal',
    closeDate: '2026-05-01',
    createdDate: '2026-02-01',
    owner: 'Jane Smith',
    company: 'Acme Corp',
    contact: 'John Doe',
    probability: 80,
    pipeline: 'standard',
  },
  {
    id: 'd2',
    name: 'Startup Onboarding',
    amount: 12000,
    stage: 'closed_won',
    closeDate: '2026-04-01',
    createdDate: '2026-03-01',
    owner: 'Bob Johnson',
    company: 'Tech Startup',
    contact: 'Jane Smith',
    probability: 100,
    pipeline: 'standard',
  },
];

const mockActivities = [
  {
    id: 'act1',
    type: 'meeting',
    subject: 'Quarterly review',
    body: 'Reviewed the pipeline',
    timestamp: '2026-04-22T10:00:00Z',
    contact: 'John Doe',
    company: 'Acme Corp',
    owner: 'Jane Smith',
    engagementType: 'meeting',
  },
  {
    id: 'act2',
    type: 'email',
    subject: 'Follow up on proposal',
    body: 'Sending revised terms',
    timestamp: '2026-04-21T09:00:00Z',
    contact: 'Jane Smith',
    company: 'Tech Startup',
    owner: 'Bob Johnson',
    engagementType: 'email',
  },
];

const lastOnSearchCall = () =>
  mockOnSearch.mock.calls[mockOnSearch.mock.calls.length - 1] as [any[], any, any];

// The advanced-filters checkboxes render owner/industry labels that repeat
// the preview row text, so preview assertions must be scoped to the results
// preview container.
const resultsPreview = (container: HTMLElement) =>
  container.querySelector<HTMLElement>('[class*="max-h-[200px]"]')!;

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

  // Test 13: renders company results (name + revenue path)
  test('renders company results', () => {
    renderSearch({ data: mockCompanies, dataType: 'companies', totalCount: 1 });

    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('Showing 1 of 1 results')).toBeInTheDocument();
  });

  // Test 14: changing the dataType dropdown updates filters + badge
  test('changes dataType via dropdown', async () => {
    renderSearch({ data: mockCompanies, dataType: 'contacts' });

    const dataTypeSelect = screen.getByDisplayValue('Contacts');
    fireEvent.change(dataTypeSelect, { target: { value: 'companies' } });

    await waitFor(
      () => {
        const [results, filters] = lastOnSearchCall();
        expect(filters.dataType).toBe('companies');
        expect(results).toHaveLength(1);
        expect(results[0].name).toBe('Acme Corp');
      },
      { timeout: 1500 }
    );
    expect(screen.getByText('COMPANIES')).toBeInTheDocument();
  });

  // Test 15: clicking the same sort field twice toggles to ascending
  test('toggles sort direction to ascending', async () => {
    renderSearch();

    const sortDropdown = screen.getByDisplayValue(/sort by last activity/i);
    fireEvent.change(sortDropdown, { target: { value: 'createdDate' } });
    fireEvent.change(sortDropdown, { target: { value: 'createdDate' } });

    await waitFor(
      () => {
        expect(screen.getByText('↑ Asc')).toBeInTheDocument();
        expect(lastOnSearchCall()[2].direction).toBe('asc');
      },
      { timeout: 2000 }
    );
  });

  // Test 16: sorts contacts by lead score (descending)
  test('sorts by lead score', async () => {
    renderSearch({ totalCount: 2 });

    const sortDropdown = screen.getByDisplayValue(/sort by last activity/i);
    fireEvent.change(sortDropdown, { target: { value: 'leadScore' } });

    await waitFor(
      () => {
        const [results] = lastOnSearchCall();
        expect(results.map((r: any) => r.leadScore)).toEqual([85, 45]);
      },
      { timeout: 1500 }
    );

    const names = screen.getAllByText(/john doe|jane smith/i);
    expect(names[0]).toHaveTextContent('John Doe'); // higher score first
  });

  // Test 17: sorts deals by amount (ascending when toggled)
  test('sorts deals by amount', async () => {
    renderSearch({ data: mockDeals, dataType: 'deals', totalCount: 2 });

    const sortDropdown = screen.getByDisplayValue(/sort by last activity/i);
    fireEvent.change(sortDropdown, { target: { value: 'amount' } });
    fireEvent.change(sortDropdown, { target: { value: 'amount' } }); // asc

    await waitFor(
      () => {
        const [results] = lastOnSearchCall();
        expect(results.map((r: any) => r.amount)).toEqual([12000, 50000]);
      },
      { timeout: 1500 }
    );
  });

  // Test 18: sorts companies by annual revenue
  test('sorts companies by annual revenue', async () => {
    const biggerCompany = {
      ...mockCompanies[0],
      id: '2',
      name: 'Mega Corp',
      annualRevenue: 90000000,
    };
    renderSearch({
      data: [biggerCompany, ...mockCompanies],
      dataType: 'companies',
      totalCount: 2,
    });
    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));

    // Mega Corp (90M) exceeds the default 10M revenue cap — raise the max
    // range first so both companies survive the filter.
    const revenueMaxInput = screen.getAllByPlaceholderText('Max')[0];
    fireEvent.change(revenueMaxInput, { target: { value: '100000000' } });

    const sortDropdown = screen.getByDisplayValue(/sort by last activity/i);
    fireEvent.change(sortDropdown, { target: { value: 'annualRevenue' } });

    await waitFor(
      () => {
        const [results] = lastOnSearchCall();
        expect(results.map((r: any) => r.name)).toEqual(['Mega Corp', 'Acme Corp']);
      },
      { timeout: 2000 }
    );
  });

  // Test 19: sorts by name (contacts become "first last")
  test('sorts by name', async () => {
    renderSearch({ totalCount: 2 });

    const sortDropdown = screen.getByDisplayValue(/sort by last activity/i);
    fireEvent.change(sortDropdown, { target: { value: 'name' } });
    fireEvent.change(sortDropdown, { target: { value: 'name' } }); // asc

    await waitFor(
      () => {
        const [results] = lastOnSearchCall();
        expect(results.map((r: any) => `${r.firstName} ${r.lastName}`)).toEqual([
          'Jane Smith',
          'John Doe',
        ]);
      },
      { timeout: 1500 }
    );
  });

  // Test 20: filters results by owner checkbox
  test('filters by owner', async () => {
    const { container } = renderSearch({ totalCount: 2 });
    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Bob Johnson' }));

    const preview = resultsPreview(container);
    await waitFor(
      () => {
        expect(within(preview).queryByText('John Doe')).not.toBeInTheDocument();
        expect(within(preview).getByText('Jane Smith')).toBeInTheDocument();
        const [results] = lastOnSearchCall();
        expect(results).toHaveLength(1);
        expect(results[0].owner).toBe('Bob Johnson');
      },
      { timeout: 2000 }
    );
  });

  // Test 21: filters companies by size checkbox
  test('filters by company size', async () => {
    const smbCompany = {
      ...mockCompanies[0],
      id: '2',
      name: 'Acme SMB',
      size: 'SMB',
    };
    renderSearch({
      data: [smbCompany, ...mockCompanies],
      dataType: 'companies',
      totalCount: 2,
    });
    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Enterprise' }));

    await waitFor(
      () => {
        expect(screen.queryByText('Acme SMB')).not.toBeInTheDocument();
        expect(screen.getByText('Acme Corp')).toBeInTheDocument();
      },
      { timeout: 1500 }
    );
  });

  // Test 22: filters activities by engagement type
  test('filters by activity type', async () => {
    renderSearch({ data: mockActivities, dataType: 'activities', totalCount: 2 });
    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));

    fireEvent.click(await screen.findByRole('checkbox', { name: 'email' }));

    await waitFor(
      () => {
        expect(screen.queryByText('Quarterly review')).not.toBeInTheDocument();
        expect(screen.getByText('Follow up on proposal')).toBeInTheDocument();
      },
      { timeout: 1500 }
    );
  });

  // Test 23: filters companies by revenue range
  test('filters by annual revenue range', async () => {
    renderSearch({ data: mockCompanies, dataType: 'companies', totalCount: 1 });
    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));

    const [minInput, maxInput] = screen.getAllByPlaceholderText('Min');
    fireEvent.change(minInput, { target: { value: '10000000' } });

    await waitFor(
      () => {
        expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument();
        expect(screen.getByText('Showing 0 of 1 results')).toBeInTheDocument();
      },
      { timeout: 1500 }
    );
    expect(maxInput).toBeInTheDocument();
  });

  // Test 24: filters deals by amount range
  test('filters by deal amount range', async () => {
    renderSearch({ data: mockDeals, dataType: 'deals', totalCount: 2 });
    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));

    // Two Min/Max pairs render (revenue + deal amount); deal amount is 2nd.
    const dealMinInput = screen.getAllByPlaceholderText('Min')[1];
    const dealMaxInput = screen.getAllByPlaceholderText('Max')[1];
    fireEvent.change(dealMinInput, { target: { value: '30000' } });

    await waitFor(
      () => {
        expect(screen.queryByText('Startup Onboarding')).not.toBeInTheDocument();
        expect(screen.getByText('Acme Renewal')).toBeInTheDocument();
      },
      { timeout: 1500 }
    );
    fireEvent.change(dealMaxInput, { target: { value: '40000' } });
    await waitFor(
      () => {
        expect(screen.queryByText('Acme Renewal')).not.toBeInTheDocument();
      },
      { timeout: 1500 }
    );
  });

  // Test 25: lead score "N+" semantics — a 0-score contact is filtered out
  test('filters by lead score threshold', async () => {
    const zeroScoreContact = {
      id: '3',
      firstName: 'Zero',
      lastName: 'Score',
      email: 'zero@example.com',
      company: 'None',
      phone: '',
      lifecycleStage: 'lead',
      leadStatus: 'new',
      leadScore: 0,
      lastActivityDate: '2026-04-01',
      createdDate: '2026-01-01',
      owner: 'Jane Smith',
      industry: 'Technology',
      country: 'USA',
    };
    const { container } = renderSearch({
      data: [...mockContacts, zeroScoreContact],
      totalCount: 3,
    });
    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));

    fireEvent.click(await screen.findByRole('checkbox', { name: '1+' }));

    const preview = resultsPreview(container);
    await waitFor(
      () => {
        expect(within(preview).queryByText('Zero Score')).not.toBeInTheDocument();
        expect(within(preview).getByText('John Doe')).toBeInTheDocument();
        expect(within(preview).getByText('Jane Smith')).toBeInTheDocument();
      },
      { timeout: 2000 }
    );
  });

  // Test 26: removes an active filter badge via its X icon
  test('removes active filter badge via X', async () => {
    const { container } = renderSearch({ totalCount: 2 });
    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Technology' }));

    const badge = await screen.findByText('Industry: Technology');
    fireEvent.click(badge.closest('div')!.querySelector('svg')!);

    const preview = resultsPreview(container);
    await waitFor(
      () => {
        expect(screen.queryByText('Industry: Technology')).not.toBeInTheDocument();
        expect(within(preview).getByText('John Doe')).toBeInTheDocument();
        expect(within(preview).getByText('Jane Smith')).toBeInTheDocument();
      },
      { timeout: 2000 }
    );
  });

  // Test 27: search matches company and activity subject fields
  test('searches by company and subject', async () => {
    renderSearch({ totalCount: 2 });
    const searchInput = screen.getByPlaceholderText(
      /search contacts, companies, deals, activities/i
    );
    await userEvent.type(searchInput, 'tech startup');
    await waitFor(() => {
      expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    });
  });

  test('searches activity subject/body', async () => {
    renderSearch({ data: mockActivities, dataType: 'activities', totalCount: 2 });
    const searchInput = screen.getByPlaceholderText(
      /search contacts, companies, deals, activities/i
    );
    await userEvent.type(searchInput, 'follow up');
    await waitFor(() => {
      expect(screen.getByText('Follow up on proposal')).toBeInTheDocument();
      expect(screen.queryByText('Quarterly review')).not.toBeInTheDocument();
    });
  });

  // Test 28: empty data without a query shows 0 results, not "No results"
  test('empty data without query shows 0 results only', () => {
    renderSearch({ data: [], totalCount: 0 });

    expect(screen.getByText('Showing 0 of 0 results')).toBeInTheDocument();
    expect(screen.queryByText(/no results found/i)).not.toBeInTheDocument();
  });

  // Test 29: results preview caps at 10 items
  test('caps the results preview at 10 items', () => {
    const manyContacts = Array.from({ length: 12 }, (_, i) => ({
      ...mockContacts[0],
      id: String(i),
      firstName: `Contact ${i}`,
      lastName: 'X',
    }));
    renderSearch({ data: manyContacts, totalCount: 12 });

    expect(screen.getAllByText(/contact \d+ x/i)).toHaveLength(10);
    // The summary counts ALL matches; only the preview is capped at 10.
    expect(screen.getByText('Showing 12 of 12 results')).toBeInTheDocument();
  });

  // Test 30: mixed-type data — every advanced filter checkbox toggles on/off
  // (check then uncheck) and active badges can be removed via their X icons.
  // Also covers the "name" sort fallback for items without name/firstName
  // (activities → "").
  test('toggles every advanced filter and removes active badges', async () => {
    const mixed = [
      ...mockContacts,
      ...mockCompanies,
      ...mockDeals,
      ...mockActivities,
    ];
    const { container } = renderSearch({ data: mixed, dataType: 'all', totalCount: 7 });
    fireEvent.click(screen.getByRole('button', { name: /show filters/i }));

    // Industry: check → badge appears → uncheck via checkbox → badge gone.
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Healthcare' }));
    expect(await screen.findByText('Industry: Healthcare')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Healthcare' }));
    await waitFor(() => {
      expect(screen.queryByText('Industry: Healthcare')).not.toBeInTheDocument();
    });

    // Country: check → badge → remove via X icon; then check/uncheck again
    // via the checkbox itself.
    fireEvent.click(screen.getByRole('checkbox', { name: 'USA' }));
    const countryBadge = await screen.findByText('Country: USA');
    fireEvent.click(countryBadge.closest('div')!.querySelector('svg')!);
    await waitFor(() => {
      expect(screen.queryByText('Country: USA')).not.toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('checkbox', { name: 'USA' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'USA' }));
    await waitFor(() => {
      expect(screen.queryByText('Country: USA')).not.toBeInTheDocument();
    });

    // Lifecycle stage: check → badge → remove via X icon; then checkbox.
    fireEvent.click(screen.getByRole('checkbox', { name: 'customer' }));
    const stageBadge = await screen.findByText('Stage: customer');
    fireEvent.click(stageBadge.closest('div')!.querySelector('svg')!);
    await waitFor(() => {
      expect(screen.queryByText('Stage: customer')).not.toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('checkbox', { name: 'customer' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'customer' }));

    // Deal stage: check → badge → remove via X icon; then checkbox.
    fireEvent.click(screen.getByRole('checkbox', { name: 'proposal' }));
    const dealStageBadge = await screen.findByText('Deal Stage: proposal');
    fireEvent.click(dealStageBadge.closest('div')!.querySelector('svg')!);
    await waitFor(() => {
      expect(screen.queryByText('Deal Stage: proposal')).not.toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('checkbox', { name: 'proposal' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'proposal' }));

    // Owner: check filters to Bob Johnson only, then uncheck restores all.
    fireEvent.click(screen.getByRole('checkbox', { name: 'Bob Johnson' }));
    const preview = resultsPreview(container);
    await waitFor(() => {
      expect(within(preview).queryByText('John Doe')).not.toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Bob Johnson' }));
    await waitFor(() => {
      expect(within(preview).getByText('John Doe')).toBeInTheDocument();
    });

    // Company size + activity type + lead score: check then uncheck.
    fireEvent.click(screen.getByRole('checkbox', { name: 'Enterprise' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Enterprise' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'email' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'email' }));
    fireEvent.click(screen.getByRole('checkbox', { name: '5+' }));
    fireEvent.click(screen.getByRole('checkbox', { name: '5+' }));

    // Sorting by "name" with activities present (no name/firstName) must not
    // crash and must still emit results.
    fireEvent.change(screen.getByDisplayValue(/sort by last activity/i), {
      target: { value: 'name' },
    });

    await waitFor(
      () => {
        const [results] = lastOnSearchCall();
        expect(results.length).toBe(7);
        expect(results.some((r: any) => r.subject === 'Quarterly review')).toBe(true);
      },
      { timeout: 2000 }
    );
  });
});
