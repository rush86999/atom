/**
 * WorkflowTables Component Tests
 *
 * Tests verify the real WorkflowTables component
 * (components/Automations/WorkflowTables.tsx, a DEFAULT export):
 * - Sidebar table list (names, row counts, connected-flow badges)
 * - Empty state prompt before a table is selected
 * - Selecting a table renders columns, rows and connected flows
 * - onSelectTable callback on table selection
 * - Cell editing (text via click→input→Enter), boolean checkbox, select badge
 * - Add row / add column / delete row
 * - Create table flow (empty state + Add Row)
 * - Search filtering of tables
 * - Dropdown menu (Export/Import CSV, Connect to Flow)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import WorkflowTables, { AutomationTable } from '../WorkflowTables';

describe('WorkflowTables', () => {
  const mockOnSelectTable = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders the sidebar with tables, row counts and flow badges', () => {
    render(<WorkflowTables />);

    expect(screen.getByText('Tables')).toBeInTheDocument();
    expect(screen.getByText('Sales Leads')).toBeInTheDocument();
    expect(screen.getByText('3 rows')).toBeInTheDocument();
    expect(screen.getByText('Support Tickets')).toBeInTheDocument();
    expect(screen.getByText('2 rows')).toBeInTheDocument();
    // Connected flows count badges: 2 flows on leads, 1 on support
    expect(screen.getAllByText('2')).toHaveLength(1);
    expect(screen.getAllByText('1')).toHaveLength(1);
  });

  it('shows the empty state prompt before a table is selected', () => {
    render(<WorkflowTables />);

    expect(screen.getByText('Select a table')).toBeInTheDocument();
    expect(
      screen.getByText('Choose a table from the sidebar or create a new one')
    ).toBeInTheDocument();
  });

  it('renders table columns, rows and connected flows after selection', async () => {
    const user = userEvent.setup();
    render(<WorkflowTables onSelectTable={mockOnSelectTable} />);

    await user.click(screen.getByText('Sales Leads'));

    // Header
    expect(screen.getByRole('heading', { name: /sales leads/i })).toBeInTheDocument();
    expect(screen.getByText('Track and manage incoming leads')).toBeInTheDocument();
    // Columns
    expect(screen.getByText('Name')).toBeInTheDocument();
    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Company')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Lead Score')).toBeInTheDocument();
    // Rows
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.getByText('Bob Wilson')).toBeInTheDocument();
    expect(screen.getByText('Acme Inc')).toBeInTheDocument();
    expect(screen.getByText('85')).toBeInTheDocument();
    // Email cells are mailto links
    expect(screen.getByRole('link', { name: 'john@acme.com' })).toHaveAttribute(
      'href',
      'mailto:john@acme.com'
    );
    // Connected flows footer
    expect(screen.getByText('Connected flows:')).toBeInTheDocument();
    expect(screen.getByText('lead-enrichment')).toBeInTheDocument();
    expect(screen.getByText('follow-up-sequence')).toBeInTheDocument();
    // onSelectTable fired with the selected table
    expect(mockOnSelectTable).toHaveBeenCalledTimes(1);
    const table = mockOnSelectTable.mock.calls[0][0] as AutomationTable;
    expect(table.id).toBe('leads');
  });

  it('does not fire onSelectTable on initial render', () => {
    render(<WorkflowTables onSelectTable={mockOnSelectTable} />);
    expect(mockOnSelectTable).not.toHaveBeenCalled();
  });

  it('adds a row to the selected table', async () => {
    const user = userEvent.setup();
    render(<WorkflowTables />);

    await user.click(screen.getByText('Sales Leads'));
    await user.click(screen.getByRole('button', { name: 'Row' }));

    expect(screen.getByText('4 rows')).toBeInTheDocument();
    // New empty row renders a dash per column (number cell stays blank)
    expect(screen.getAllByText('-')).toHaveLength(4);
  });

  it('adds a column to the selected table', async () => {
    const user = userEvent.setup();
    render(<WorkflowTables />);

    await user.click(screen.getByText('Sales Leads'));
    await user.click(screen.getByRole('button', { name: /column/i }));

    expect(screen.getByText('Column 6')).toBeInTheDocument();
  });

  it('edits a text cell via click, type and Enter', async () => {
    const user = userEvent.setup();
    render(<WorkflowTables />);

    await user.click(screen.getByText('Sales Leads'));
    await user.click(screen.getByText('John Doe'));

    const input = screen.getByDisplayValue('John Doe');
    await user.clear(input);
    await user.type(input, 'John Smith');
    await user.keyboard('{Enter}');

    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
  });

  it('edits a select cell through the inline editor', async () => {
    const user = userEvent.setup();
    render(<WorkflowTables />);

    await user.click(screen.getByText('Sales Leads'));
    // "New" status badge on row 1 opens the editor
    await user.click(screen.getByText('New'));

    const input = screen.getByDisplayValue('New');
    await user.clear(input);
    await user.type(input, 'Converted');
    await user.keyboard('{Enter}');

    expect(screen.getByText('Converted')).toBeInTheDocument();
  });

  it('toggles a boolean cell via checkbox', async () => {
    const user = userEvent.setup();
    render(<WorkflowTables />);

    await user.click(screen.getByText('Support Tickets'));

    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes).toHaveLength(2);
    // Row 1 unresolved, row 2 resolved
    expect((checkboxes[0] as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[1] as HTMLInputElement).checked).toBe(true);

    await user.click(checkboxes[0]);
    expect((screen.getAllByRole('checkbox')[0] as HTMLInputElement).checked).toBe(true);
  });

  it('deletes a row', async () => {
    const user = userEvent.setup();
    const { container } = render(<WorkflowTables />);

    await user.click(screen.getByText('Sales Leads'));

    const deleteButton = container.querySelector('button .lucide-trash-2')?.closest('button');
    expect(deleteButton).not.toBeNull();
    await user.click(deleteButton as HTMLElement);

    expect(screen.queryByText('John Doe')).not.toBeInTheDocument();
    // Leads drops to 2 rows, support still has 2 rows
    expect(screen.getAllByText('2 rows')).toHaveLength(2);
  });

  it('creates a new table with the create flow', async () => {
    const user = userEvent.setup();
    const { container } = render(<WorkflowTables onSelectTable={mockOnSelectTable} />);

    const createButton = container.querySelector('button .lucide-plus')?.closest('button');
    await user.click(createButton as HTMLElement);

    const nameInput = screen.getByPlaceholderText('Table name...');
    await user.type(nameInput, 'Campaign Tracker');
    await user.click(screen.getByRole('button', { name: /create/i }));

    // Sidebar entry + table header both show the new name
    expect(screen.getAllByText('Campaign Tracker')).toHaveLength(2);
    expect(screen.getByText('0 rows')).toBeInTheDocument();
    // New table is auto-selected → empty data state
    expect(screen.getByText('No data yet')).toBeInTheDocument();
    // Creating a table selects it locally but does not fire the external callback
    expect(mockOnSelectTable).not.toHaveBeenCalled();
  });

  it('adds the first row to a newly created empty table', async () => {
    const user = userEvent.setup();
    const { container } = render(<WorkflowTables />);

    const createButton = container.querySelector('button .lucide-plus')?.closest('button');
    await user.click(createButton as HTMLElement);
    await user.type(screen.getByPlaceholderText('Table name...'), 'Campaign Tracker');
    await user.click(screen.getByRole('button', { name: /create/i }));

    await user.click(screen.getByRole('button', { name: /add row/i }));
    expect(screen.getByText('1 rows')).toBeInTheDocument();
    expect(screen.queryByText('No data yet')).not.toBeInTheDocument();
  });

  it('filters tables by search query', async () => {
    const user = userEvent.setup();
    render(<WorkflowTables />);

    await user.type(screen.getByPlaceholderText('Search tables...'), 'support');

    expect(screen.getByText('Support Tickets')).toBeInTheDocument();
    expect(screen.queryByText('Sales Leads')).not.toBeInTheDocument();
  });

  it('opens the actions dropdown with export/import/connect items', async () => {
    const user = userEvent.setup();
    const { container } = render(<WorkflowTables />);

    await user.click(screen.getByText('Sales Leads'));

    const menuButton = container.querySelector('button .lucide-ellipsis')?.closest('button');
    await user.click(menuButton as HTMLElement);

    expect(await screen.findByText('Export CSV')).toBeInTheDocument();
    expect(screen.getByText('Import CSV')).toBeInTheDocument();
    expect(screen.getByText('Connect to Flow')).toBeInTheDocument();
  });
});
