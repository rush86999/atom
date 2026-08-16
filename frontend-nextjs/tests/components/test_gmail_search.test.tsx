/**
 * GmailSearch Component Tests
 *
 * Covers the search wiring: typing filters the provided data (messages and
 * contacts field sets) and invokes onSearch with the filtered results; the
 * loading state disables the input.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import GmailSearch from '@/components/GmailSearch';

const messages = [
  { from: 'alice@example.com', subject: 'Quarterly Report', preview: 'Please review the numbers' },
  { from: 'bob@example.com', subject: 'Lunch?', preview: 'Are you free on Friday' },
];

const contacts = [
  { name: 'Alice Smith', email: 'alice@example.com', company: 'Acme' },
  { name: 'Bob Jones', email: 'bob@example.com', company: 'Globex' },
];

describe('GmailSearch', () => {
  test('renders the search input and item counts', () => {
    render(
      <GmailSearch
        data={messages}
        dataType="messages"
        onSearch={jest.fn()}
        loading={false}
        totalCount={messages.length}
      />,
    );

    expect(screen.getByTestId('gmail-search-input')).toBeInTheDocument();
    expect(screen.getByText('Showing 2 of 2 items')).toBeInTheDocument();
  });

  test('shows Loading... and disables the input while loading', () => {
    render(
      <GmailSearch
        data={[]}
        dataType="messages"
        onSearch={jest.fn()}
        loading={true}
        totalCount={0}
      />,
    );

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(screen.getByTestId('gmail-search-input')).toBeDisabled();
  });

  test('filters messages and invokes onSearch with matching results', () => {
    const onSearch = jest.fn();
    render(
      <GmailSearch
        data={messages}
        dataType="messages"
        onSearch={onSearch}
        loading={false}
        totalCount={messages.length}
      />,
    );

    fireEvent.change(screen.getByTestId('gmail-search-input'), {
      target: { value: 'quarterly' },
    });

    expect(onSearch).toHaveBeenCalledWith(
      [messages[0]],
      { query: 'quarterly', dataType: 'messages' },
      {},
    );
  });

  test('filters contacts by name and email fields', () => {
    const onSearch = jest.fn();
    render(
      <GmailSearch
        data={contacts}
        dataType="contacts"
        onSearch={onSearch}
        loading={false}
        totalCount={contacts.length}
      />,
    );

    fireEvent.change(screen.getByTestId('gmail-search-input'), {
      target: { value: 'globex' },
    });
    expect(onSearch).toHaveBeenLastCalledWith(
      [contacts[1]],
      { query: 'globex', dataType: 'contacts' },
      {},
    );

    fireEvent.change(screen.getByTestId('gmail-search-input'), {
      target: { value: 'bob@example.com' },
    });
    expect(onSearch).toHaveBeenLastCalledWith(
      [contacts[1]],
      { query: 'bob@example.com', dataType: 'contacts' },
      {},
    );

    fireEvent.change(screen.getByTestId('gmail-search-input'), {
      target: { value: 'nomatch' },
    });
    expect(onSearch).toHaveBeenLastCalledWith(
      [],
      { query: 'nomatch', dataType: 'contacts' },
      {},
    );
  });

  test('clearing the query passes the full data set back', () => {
    const onSearch = jest.fn();
    render(
      <GmailSearch
        data={messages}
        dataType="messages"
        onSearch={onSearch}
        loading={false}
        totalCount={messages.length}
      />,
    );

    fireEvent.change(screen.getByTestId('gmail-search-input'), {
      target: { value: 'lunch' },
    });
    fireEvent.change(screen.getByTestId('gmail-search-input'), {
      target: { value: '' },
    });

    expect(onSearch).toHaveBeenLastCalledWith(
      messages,
      { query: '', dataType: 'messages' },
      {},
    );
  });
});
