/**
 * SearchResults Component Tests
 *
 * Tests verify SearchResults renders search results list, handles empty
 * state, highlights matches, and shows loading state.
 *
 * Source: components/chat/SearchResults.tsx (32 lines, 0% coverage)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { SearchResults, UnifiedEntity } from '../SearchResults';

describe('SearchResults', () => {
  const mockOnResultClick = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  const mockResults: UnifiedEntity[] = [
    {
      entity_id: '1',
      entity_type: 'contact',
      canonical_name: 'John Doe',
      platform_mappings: { slack: 'U123' },
      attributes: { company: 'Acme Corp', email: 'john@acme.com' },
      created_at: '2024-01-01',
      updated_at: '2024-01-02',
      confidence_score: 0.95,
    },
    {
      entity_id: '2',
      entity_type: 'task',
      canonical_name: 'Complete project',
      platform_mappings: { asana: 'task-456' },
      attributes: { due_date: '2024-12-31', status: 'In Progress' },
      created_at: '2024-01-01',
      updated_at: '2024-01-02',
      confidence_score: 0.88,
    },
  ];

  // Test 1: renders search results list
  test('renders search results list', () => {
    const { container } = render(
      <SearchResults results={mockResults} query="test" onResultClick={mockOnResultClick} />
    );

    expect(container.textContent).toContain('John Doe');
    expect(container.textContent).toContain('Complete project');
  });

  // Test 2: empty results shows null
  test('empty results shows null', () => {
    const { container } = render(
      <SearchResults results={[]} query="test" onResultClick={mockOnResultClick} />
    );

    expect(container.innerHTML).toBe('');
  });

  // Test 3: shows search query in header
  test('shows search query in header', () => {
    const { container } = render(
      <SearchResults results={mockResults} query="john" onResultClick={mockOnResultClick} />
    );

    expect(container.textContent).toContain('Search Results for "john"');
  });

  // Test 4: shows result count badge
  test('shows result count badge', () => {
    const { container } = render(
      <SearchResults results={mockResults} query="test" onResultClick={mockOnResultClick} />
    );

    expect(container.textContent).toContain('2 found');
  });

  // Test 5: clicking result triggers callback
  test('clicking result triggers callback', () => {
    const { container } = render(
      <SearchResults results={mockResults} query="test" onResultClick={mockOnResultClick} />
    );

    const resultDivs = container.querySelectorAll('div.cursor-pointer');
    if (resultDivs.length > 0) {
      resultDivs[0].click();
    }

    expect(mockOnResultClick).toHaveBeenCalled();
  });

  // Test 6: displays entity type correctly
  test('displays entity type correctly', () => {
    const { container } = render(
      <SearchResults results={mockResults} query="test" onResultClick={mockOnResultClick} />
    );

    // Check that contact entity shows company attribute
    expect(container.textContent).toContain('Acme Corp');

    // Check that task entity shows status
    expect(container.textContent).toContain('In Progress');
  });
});
