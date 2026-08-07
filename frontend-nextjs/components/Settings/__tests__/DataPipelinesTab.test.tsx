/**
 * DataPipelinesTab component tests.
 *
 * Covers: loading gate while preferences fetch, three pipeline cards with
 * saved schedule values, Save & Apply with success toast, and save failure
 * toast (BUG-097: the save path must surface non-ok responses).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { DataPipelinesTab } from '../DataPipelinesTab';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const prefs: Record<string, any> = {
  'schedule.sales': '*/30 * * * *',
  'schedule.projects': '*/15 * * * *',
  'schedule.finance': '0 * * * *',
};

const getMockFetch = (postOk = true) =>
  jest.fn().mockImplementation((url: string, init?: RequestInit) => {
    const u = String(url);
    if (init?.method === 'POST') {
      return Promise.resolve({ ok: postOk, status: postOk ? 200 : 500, json: async () => ({}) });
    }
    const key = Object.keys(prefs).find((k) => u.includes(`preferences/${k}`));
    return Promise.resolve({
      ok: true,
      json: async () => ({ value: key ? prefs[key] : null }),
    });
  });

describe('DataPipelinesTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = getMockFetch();
  });

  it('shows the loader until preferences are loaded', () => {
    global.fetch = jest.fn(() => new Promise(() => {}));
    const { container } = render(<DataPipelinesTab />);
    expect(container.querySelector('.animate-spin')).toBeInTheDocument();
    expect(screen.queryByText('Sales Pipeline')).not.toBeInTheDocument();
  });

  it('renders the three pipeline cards with saved schedules', async () => {
    render(<DataPipelinesTab />);
    expect(await screen.findByText('Memory Pipeline Schedules')).toBeInTheDocument();
    expect(screen.getByText('Sales Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Projects Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Finance Pipeline')).toBeInTheDocument();
    expect(screen.getByText('HubSpot / Salesforce')).toBeInTheDocument();
    expect(screen.getByText('Jira / Asana')).toBeInTheDocument();
    expect(screen.getByText('Stripe / Xero')).toBeInTheDocument();
  });

  it('saves all three schedules and toasts success', async () => {
    render(<DataPipelinesTab />);
    fireEvent.click(await screen.findByRole('button', { name: /Save & Apply Changes/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Schedules Updated' })
      );
    });
    const posts = (global.fetch as jest.Mock).mock.calls.filter(([, init]) => init?.method === 'POST');
    expect(posts).toHaveLength(3);
    const bodies = posts.map(([, init]) => JSON.parse(init.body));
    expect(bodies.map((b: any) => b.key).sort()).toEqual([
      'schedule.finance',
      'schedule.projects',
      'schedule.sales',
    ]);
    expect(bodies.find((b: any) => b.key === 'schedule.sales').value).toBe('*/30 * * * *');
  });

  it('toasts an error when a preference save fails (BUG-097)', async () => {
    global.fetch = getMockFetch(false);
    render(<DataPipelinesTab />);
    fireEvent.click(await screen.findByRole('button', { name: /Save & Apply Changes/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to update schedules.' })
      );
    });
    expect(mockToast.toast).not.toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Schedules Updated' })
    );
  });
});
