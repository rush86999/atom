/**
 * SmartSearch tests (components/SmartSearch.tsx)
 *
 * Covers the heading, query typing, search via button and Enter key,
 * rendering results, and the hidden results block before searching.
 * fetch is stubbed directly (no MSW needed for a single relative endpoint).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SmartSearch from '@/components/SmartSearch';

const results = [
  { skill: 'web-search', title: 'Search the web', url: '/skills/web-search' },
  { skill: 'code-review', title: 'Review a PR', url: '/skills/code-review' },
];

describe('SmartSearch', () => {
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => results,
    });
    global.fetch = fetchMock as any;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders the heading and hides results before searching', () => {
    render(<SmartSearch />);

    expect(screen.getByRole('heading', { name: 'Smart Search' })).toBeInTheDocument();
    expect(
      screen.getByText('Search across all agent skills.')
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter your search query')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Results' })).not.toBeInTheDocument();
  });

  it('searches via the button with the typed query and renders results', async () => {
    render(<SmartSearch />);

    fireEvent.change(screen.getByPlaceholderText('Enter your search query'), {
      target: { value: 'search agents' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Results' })).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/smart-search?query=search agents'
    );
    expect(screen.getByText('web-search')).toBeInTheDocument();
    expect(screen.getByText('Search the web')).toBeInTheDocument();
    expect(screen.getByText('code-review')).toBeInTheDocument();
    expect(screen.getByText('Review a PR')).toBeInTheDocument();

    const links = screen.getAllByRole('link');
    expect(links.map((a) => a.getAttribute('href'))).toEqual(
      expect.arrayContaining(['/skills/web-search', '/skills/code-review'])
    );
  });

  it('searches when Enter is pressed in the input', async () => {
    render(<SmartSearch />);

    fireEvent.change(screen.getByPlaceholderText('Enter your search query'), {
      target: { value: 'enter query' },
    });
    fireEvent.keyDown(screen.getByPlaceholderText('Enter your search query'), {
      key: 'Enter',
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/smart-search?query=enter query'
      );
    });
    expect(await screen.findByText('web-search')).toBeInTheDocument();
  });

  it('does not search on other keys', () => {
    render(<SmartSearch />);

    fireEvent.keyDown(screen.getByPlaceholderText('Enter your search query'), {
      key: 'Escape',
    });

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
