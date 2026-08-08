/**
 * LeadManagement Component Tests
 *
 * Verifies the real LeadManagement (components/sales/LeadManagement.tsx):
 * - loads leads from GET /api/sales/leads and renders rows with real values
 *   (name, email, company, source badge, AI score + color, qualification
 *   summary, status / spam badges)
 * - loading state disables the Sync CRM button
 * - Sync CRM refetches the lead list
 * - search filters by email or company (case-insensitive)
 * - empty + non-array API responses render the empty state without crashing
 * - a lead with a missing email must not crash the table (real-bug guard)
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import LeadManagement from '../LeadManagement';

const leadsPayload = [
  {
    id: 'l1',
    email: 'ada@example.com',
    first_name: 'Ada',
    last_name: 'Lovelace',
    company: 'Analytical Engines',
    source: 'Website',
    status: 'qualified',
    ai_score: 92,
    ai_qualification_summary: 'High intent, budget confirmed',
    is_spam: false,
    created_at: '2026-08-01T10:00:00Z',
  },
  {
    id: 'l2',
    email: 'spam@example.com',
    first_name: 'Spam',
    last_name: 'Bot',
    company: 'Bot Co',
    source: 'LinkedIn',
    status: 'new',
    ai_score: 12,
    ai_qualification_summary: 'Suspicious domain',
    is_spam: true,
    created_at: '2026-08-02T10:00:00Z',
  },
];

describe('LeadManagement', () => {
  beforeEach(() => {
    server.resetHandlers();
    server.use(
      rest.get('/api/sales/leads', (req, res, ctx) => res(ctx.status(200), ctx.json(leadsPayload)))
    );
  });

  it('renders lead rows with values from the API', async () => {
    const { container } = render(<LeadManagement />);

    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument();
    expect(screen.getByText('ada@example.com')).toBeInTheDocument();
    expect(screen.getByText('Analytical Engines')).toBeInTheDocument();
    expect(screen.getByText('Website')).toBeInTheDocument();
    expect(screen.getByText('92%')).toBeInTheDocument();
    expect(screen.getByText('High intent, budget confirmed')).toBeInTheDocument();
    expect(screen.getByText('qualified')).toBeInTheDocument();

    // score color thresholds: 92 → green, 12 → red
    expect(container.querySelector('.bg-green-500')).toBeInTheDocument();
    expect(container.querySelector('.bg-red-500')).toBeInTheDocument();
  });

  it('renders a spam badge for flagged leads instead of the status', async () => {
    render(<LeadManagement />);

    await screen.findByText('Ada Lovelace');
    expect(screen.getByText('Spam')).toBeInTheDocument();
    // spam lead has no status badge
    expect(screen.queryByText('new')).not.toBeInTheDocument();
  });

  it('disables the Sync CRM button while loading', async () => {
    server.use(
      rest.get('/api/sales/leads', (req, res, ctx) =>
        res(ctx.delay(150), ctx.status(200), ctx.json(leadsPayload))
      )
    );
    render(<LeadManagement />);

    const syncButton = screen.getByRole('button', { name: /Sync CRM/i });
    expect(syncButton).toBeDisabled();

    await screen.findByText('Ada Lovelace');
    expect(screen.getByRole('button', { name: /Sync CRM/i })).not.toBeDisabled();
  });

  it('refetches the lead list when Sync CRM is clicked', async () => {
    let calls = 0;
    server.use(
      rest.get('/api/sales/leads', (req, res, ctx) => {
        calls += 1;
        return res(ctx.status(200), ctx.json(leadsPayload));
      })
    );
    render(<LeadManagement />);
    await screen.findByText('Ada Lovelace');

    fireEvent.click(screen.getByRole('button', { name: /Sync CRM/i }));

    await waitFor(() => expect(calls).toBe(2));
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
  });

  it('filters leads by company name', async () => {
    render(<LeadManagement />);
    await screen.findByText('Ada Lovelace');

    fireEvent.change(screen.getByPlaceholderText('Search leads or companies...'), {
      target: { value: 'analytical' },
    });

    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    expect(screen.queryByText('Spam Bot')).not.toBeInTheDocument();
  });

  it('filters leads by email case-insensitively', async () => {
    render(<LeadManagement />);
    await screen.findByText('Ada Lovelace');

    fireEvent.change(screen.getByPlaceholderText('Search leads or companies...'), {
      target: { value: 'SPAM@EXAMPLE' },
    });

    expect(screen.getByText('Spam Bot')).toBeInTheDocument();
    expect(screen.queryByText('Ada Lovelace')).not.toBeInTheDocument();
  });

  it('shows the empty state when no leads match the search', async () => {
    render(<LeadManagement />);
    await screen.findByText('Ada Lovelace');

    fireEvent.change(screen.getByPlaceholderText('Search leads or companies...'), {
      target: { value: 'zzz-no-match' },
    });

    expect(screen.getByText('No leads found matching your criteria.')).toBeInTheDocument();
  });

  it('shows the empty state when the API returns no leads', async () => {
    server.use(rest.get('/api/sales/leads', (req, res, ctx) => res(ctx.status(200), ctx.json([]))));
    render(<LeadManagement />);

    expect(await screen.findByText('No leads found matching your criteria.')).toBeInTheDocument();
  });

  it('does not crash when the API returns a non-array body', async () => {
    server.use(
      rest.get('/api/sales/leads', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ leads: leadsPayload, success: true }))
      )
    );
    render(<LeadManagement />);

    expect(await screen.findByText('No leads found matching your criteria.')).toBeInTheDocument();
    expect(screen.queryByText('Ada Lovelace')).not.toBeInTheDocument();
  });

  it('does not crash when a lead has no email address', async () => {
    server.use(
      rest.get('/api/sales/leads', (req, res, ctx) =>
        res(
          ctx.status(200),
          ctx.json([
            {
              id: 'l9',
              first_name: 'No',
              last_name: 'Email',
              company: 'Acme',
              source: 'Manual',
              status: 'new',
              ai_score: 55,
              ai_qualification_summary: '',
              is_spam: false,
              created_at: '2026-08-03T10:00:00Z',
            },
            ...leadsPayload,
          ])
        )
      )
    );
    render(<LeadManagement />);

    expect(await screen.findByText('No Email')).toBeInTheDocument();
    expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    // search still works without crashing on the email-less lead
    fireEvent.change(screen.getByPlaceholderText('Search leads or companies...'), {
      target: { value: 'acme' },
    });
    expect(screen.getByText('No Email')).toBeInTheDocument();
    expect(screen.queryByText('Ada Lovelace')).not.toBeInTheDocument();
  });
});
