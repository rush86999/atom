/**
 * MyTemplatesPage component tests.
 *
 * fetch is mocked per test. Covers loading/empty states, listing cards with
 * badges/stats, search + category filtering, editor open (create/edit), and
 * the delete/duplicate/visibility actions.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MyTemplatesPage, WorkflowTemplate } from '../MyTemplatesPage';

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] as any[] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

const TEMPLATES: WorkflowTemplate[] = [
  {
    template_id: 'tpl-1',
    name: 'Lead Processing',
    description: 'Process incoming leads automatically',
    category: 'automation',
    complexity: 'intermediate',
    tags: ['lead', 'crm'],
    inputs: [],
    steps: [],
    is_public: true,
    usage_count: 42,
    rating: 4.5,
    rating_count: 3,
  },
  {
    template_id: 'tpl-2',
    name: 'Sales Report',
    description: 'Weekly sales reporting digest',
    category: 'reporting',
    complexity: 'beginner',
    tags: ['sales'],
    inputs: [],
    steps: [],
    is_public: false,
  },
];

const mockFetch = (routes: Array<{ match: string; method?: string; res: () => { ok: boolean; status?: number; json?: any } }>) => {
  (global.fetch as jest.Mock) = jest.fn((url: string, init?: RequestInit) => {
    const route = routes.find(
      (r) =>
        String(url).includes(r.match) &&
        (!r.method || (init?.method || 'GET') === r.method)
    );
    const r = route ? route.res() : { ok: false, status: 404, json: {} };
    return Promise.resolve({
      ok: r.ok,
      status: r.status ?? 200,
      json: async () => r.json ?? {},
    });
  });
};

describe('MyTemplatesPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch([
      { match: '/api/user/templates', method: 'GET', res: () => ({ ok: true, json: TEMPLATES }) },
    ]);
  });

  it('shows a loading state before templates arrive', () => {
    (global.fetch as jest.Mock).mockReturnValue(new Promise(() => {}));
    render(<MyTemplatesPage />);
    expect(screen.getByText('Loading templates...')).toBeInTheDocument();
  });

  it('renders the header and a grid of template cards', async () => {
    render(<MyTemplatesPage />);

    expect(
      await screen.findByRole('heading', { name: /My Templates/i })
    ).toBeInTheDocument();
    expect(screen.getByText('Lead Processing')).toBeInTheDocument();
    expect(screen.getByText('Sales Report')).toBeInTheDocument();
    // Category + complexity + visibility badges
    expect(screen.getByText('automation')).toBeInTheDocument();
    expect(screen.getByText('intermediate')).toBeInTheDocument();
    expect(screen.getByText('Public')).toBeInTheDocument();
    expect(screen.getByText('Private')).toBeInTheDocument();
    // Tags and stats
    expect(screen.getByText('lead')).toBeInTheDocument();
    expect(screen.getByText('42 uses')).toBeInTheDocument();
    expect(screen.getByText(/4.5\(3\)/)).toBeInTheDocument();
  });

  it('renders the empty state with a CTA when there are no templates', async () => {
    mockFetch([
      { match: '/api/user/templates', method: 'GET', res: () => ({ ok: true, json: [] }) },
    ]);
    render(<MyTemplatesPage />);

    expect(
      await screen.findByText(/You haven't created any templates yet/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Create Your First Template/i })
    ).toBeInTheDocument();
  });

  it('filters the grid by search query (name and description)', async () => {
    render(<MyTemplatesPage />);
    await screen.findByText('Lead Processing');

    fireEvent.change(screen.getByPlaceholderText('Search templates...'), {
      target: { value: 'sales' },
    });
    expect(screen.queryByText('Lead Processing')).not.toBeInTheDocument();
    expect(screen.getByText('Sales Report')).toBeInTheDocument();

    // Description match
    fireEvent.change(screen.getByPlaceholderText('Search templates...'), {
      target: { value: 'leads automatically' },
    });
    expect(screen.getByText('Lead Processing')).toBeInTheDocument();
    expect(screen.queryByText('Sales Report')).not.toBeInTheDocument();
  });

  it('shows the no-match message when filters exclude every template', async () => {
    render(<MyTemplatesPage />);
    await screen.findByText('Lead Processing');

    fireEvent.change(screen.getByPlaceholderText('Search templates...'), {
      target: { value: 'zzz-no-match' },
    });
    expect(screen.getByText('No templates match your filters')).toBeInTheDocument();
  });

  it('filters the grid by category via the category select', async () => {
    render(<MyTemplatesPage />);
    await screen.findByText('Lead Processing');

    fireEvent.click(screen.getByRole('combobox'));
    const option = await screen.findByRole('option', { name: /Data Processing/i });
    fireEvent.click(option);

    expect(screen.queryByText('Lead Processing')).not.toBeInTheDocument();
    expect(screen.queryByText('Sales Report')).not.toBeInTheDocument();
    expect(screen.getByText('No templates match your filters')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('combobox'));
    const reporting = await screen.findByRole('option', { name: /Reporting/i });
    fireEvent.click(reporting);
    expect(screen.getByText('Sales Report')).toBeInTheDocument();
  });

  it('opens the editor in create mode', async () => {
    render(<MyTemplatesPage />);
    fireEvent.click(
      await screen.findByRole('button', { name: /New Template/i })
    );

    expect(
      screen.getByRole('heading', { name: /Create New Template/i })
    ).toBeInTheDocument();
    expect(screen.getByText('Template Editor')).toBeInTheDocument();
  });

  it('opens the editor prefilled when editing a template', async () => {
    render(<MyTemplatesPage />);
    const editButton = (await screen.findAllByRole('button', { name: /Edit/i }))[0];
    fireEvent.click(editButton);

    expect(
      screen.getByRole('heading', { name: /Edit Template/i })
    ).toBeInTheDocument();
    expect(
      (screen.getByLabelText(/Template Name \*/i) as HTMLInputElement).value
    ).toBe('Lead Processing');
  });

  it('saves a template through the editor and refreshes the list', async () => {
    mockFetch([
      {
        match: '/api/user/templates',
        method: 'POST',
        res: () => ({ ok: true, json: { template_id: 'tpl-new' } }),
      },
    ]);
    render(<MyTemplatesPage />);
    fireEvent.click(await screen.findByRole('button', { name: /New Template/i }));

    fireEvent.change(screen.getByLabelText(/Template Name \*/i), {
      target: { value: 'My New Template' },
    });
    fireEvent.change(screen.getByLabelText(/Description \*/i), {
      target: { value: 'A shiny new template' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Workflow Steps/i }));
    fireEvent.click(screen.getByRole('button', { name: /Add First Step/i }));
    fireEvent.click(screen.getByRole('button', { name: /Save Template/i }));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Success', description: 'Template created successfully' })
      );
    });
    const post = (global.fetch as jest.Mock).mock.calls.find(
      ([url, init]: [string, RequestInit?]) =>
        String(url).includes('/api/user/templates') && init?.method === 'POST'
    );
    expect(post).toBeDefined();
    expect(JSON.parse(post[1].body)).toEqual(
      expect.objectContaining({ name: 'My New Template', template_json: { nodes: [], edges: [] } })
    );
    // Editor closed, back to the list
    expect(screen.getByRole('heading', { name: /My Templates/i })).toBeInTheDocument();
  });

  it('deletes a template after confirmation', async () => {
    mockFetch([
      { match: '/api/user/templates', method: 'GET', res: () => ({ ok: true, json: TEMPLATES }) },
      {
        match: '/api/user/templates/tpl-2',
        method: 'DELETE',
        res: () => ({ ok: true, json: {} }),
      },
    ]);
    render(<MyTemplatesPage />);
    await screen.findByText('Sales Report');

    fireEvent.click(screen.getAllByTitle('Delete')[1]);
    expect(screen.getByText(/Delete Template\?/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Are you sure you want to delete "Sales Report"\?/i)
    ).toBeInTheDocument();

    // Card action buttons (title="Delete") + dialog confirm — pick the last
    // (dialog content is portal-rendered after the page buttons).
    const confirmButtons = screen.getAllByRole('button', { name: /^Delete$/ });
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Success', description: 'Template deleted successfully' })
      );
    });
    const del = (global.fetch as jest.Mock).mock.calls.find(
      ([url, init]: [string, RequestInit?]) =>
        String(url).includes('/api/user/templates/tpl-2') && init?.method === 'DELETE'
    );
    expect(del).toBeDefined();
    // List refetched after the delete
    const getCalls = (global.fetch as jest.Mock).mock.calls.filter(
      ([url]: [string]) => String(url).includes('/api/user/templates?user_id=')
    );
    expect(getCalls.length).toBeGreaterThanOrEqual(2);
  });

  it('toasts an error when deleting fails', async () => {
    mockFetch([
      { match: '/api/user/templates', method: 'GET', res: () => ({ ok: true, json: TEMPLATES }) },
      {
        match: '/api/user/templates/tpl-1',
        method: 'DELETE',
        res: () => ({ ok: false, status: 500, json: {} }),
      },
    ]);
    render(<MyTemplatesPage />);
    await screen.findByText('Lead Processing');

    fireEvent.click(screen.getAllByTitle('Delete')[0]);
    // Card action buttons (title="Delete") + dialog confirm — pick the last
    // (dialog content is portal-rendered after the page buttons).
    const confirmButtons = screen.getAllByRole('button', { name: /^Delete$/ });
    fireEvent.click(confirmButtons[confirmButtons.length - 1]);

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to delete template', variant: 'error' })
      );
    });
  });

  it('duplicates a template', async () => {
    mockFetch([
      { match: '/api/user/templates', method: 'GET', res: () => ({ ok: true, json: TEMPLATES }) },
      {
        match: '/api/user/templates/tpl-2/duplicate',
        method: 'POST',
        res: () => ({ ok: true, json: {} }),
      },
    ]);
    render(<MyTemplatesPage />);
    await screen.findByText('Sales Report');

    fireEvent.click(screen.getAllByTitle('Duplicate')[1]);

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Success', description: 'Template duplicated successfully' })
      );
    });
    const post = (global.fetch as jest.Mock).mock.calls.find(
      ([url, init]: [string, RequestInit?]) =>
        String(url).includes('/duplicate') && init?.method === 'POST'
    );
    expect(JSON.parse(post[1].body)).toEqual({ name: 'Sales Report (Copy)' });
  });

  it('toggles template visibility', async () => {
    mockFetch([
      { match: '/api/user/templates', method: 'GET', res: () => ({ ok: true, json: TEMPLATES }) },
      {
        match: '/api/user/templates/tpl-2/publish',
        method: 'POST',
        res: () => ({ ok: true, json: {} }),
      },
    ]);
    render(<MyTemplatesPage />);
    await screen.findByText('Sales Report');

    fireEvent.click(screen.getAllByTitle('Make public')[0]);

    await waitFor(() => {
      const post = (global.fetch as jest.Mock).mock.calls.find(
        ([url, init]: [string, RequestInit?]) =>
          String(url).includes('/publish') && init?.method === 'POST'
      );
      expect(post).toBeDefined();
      expect(JSON.parse(post[1].body)).toEqual({ visibility: 'public' });
    });
  });

  it('toasts an error when the initial load fails', async () => {
    mockFetch([
      { match: '/api/user/templates', method: 'GET', res: () => ({ ok: false, status: 500, json: {} }) },
    ]);
    render(<MyTemplatesPage />);

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to load templates', variant: 'error' })
      );
    });
    expect(
      screen.getByText(/You haven't created any templates yet/i)
    ).toBeInTheDocument();
  });
});
