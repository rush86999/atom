import React from 'react';
import { renderWithProviders, screen } from '../../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
} from '@/components/ui/table';

describe('Table Components', () => {
  describe('Table', () => {
    it('renders table element', () => {
      renderWithProviders(
        <Table>
          <tbody>
            <tr>
              <td>Content</td>
            </tr>
          </tbody>
        </Table>
      );
      expect(screen.getByRole('table')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      renderWithProviders(
        <Table className="custom-table">
          <tbody>
            <tr>
              <td>Content</td>
            </tr>
          </tbody>
        </Table>
      );
      const table = screen.getByRole('table');
      expect(table).toHaveClass('custom-table');
    });

    it('wraps table in responsive container', () => {
      renderWithProviders(
        <Table>
          <tbody>
            <tr>
              <td>Content</td>
            </tr>
          </tbody>
        </Table>
      );
      const container = screen.getByRole('table').parentElement;
      expect(container).toHaveClass('relative');
      expect(container).toHaveClass('w-full');
      expect(container).toHaveClass('overflow-auto');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLTableElement>();
      renderWithProviders(
        <Table ref={ref}>
          <tbody>
            <tr>
              <td>Content</td>
            </tr>
          </tbody>
        </Table>
      );
      expect(ref.current).toBeInstanceOf(HTMLTableElement);
    });

    it('has default text-sm class', () => {
      renderWithProviders(
        <Table>
          <tbody>
            <tr>
              <td>Content</td>
            </tr>
          </tbody>
        </Table>
      );
      const table = screen.getByRole('table');
      expect(table).toHaveClass('text-sm');
    });

    it('merges custom className with default classes', () => {
      renderWithProviders(
        <Table className="border">
          <tbody>
            <tr>
              <td>Content</td>
            </tr>
          </tbody>
        </Table>
      );
      const table = screen.getByRole('table');
      expect(table).toHaveClass('text-sm');
      expect(table).toHaveClass('border');
    });
  });

  describe('TableHeader', () => {
    it('renders thead element', () => {
      renderWithProviders(
        <table>
          <TableHeader>
            <tr>
              <th>Header</th>
            </tr>
          </TableHeader>
        </table>
      );
      expect(screen.getByRole('rowgroup')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      renderWithProviders(
        <table>
          <TableHeader className="custom-header">
            <tr>
              <th>Header</th>
            </tr>
          </TableHeader>
        </table>
      );
      const thead = screen.getByRole('rowgroup');
      expect(thead).toHaveClass('custom-header');
    });

    it('applies border style to rows', () => {
      renderWithProviders(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Header</TableHead>
            </TableRow>
          </TableHeader>
        </Table>
      );
      const thead = screen.getByRole('rowgroup');
      expect(thead).toHaveClass('[&_tr]:border-b');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLTableSectionElement>();
      renderWithProviders(
        <table>
          <TableHeader ref={ref}>
            <tr>
              <th>Header</th>
            </tr>
          </TableHeader>
        </table>
      );
      expect(ref.current).toBeInstanceOf(HTMLTableSectionElement);
    });
  });

  describe('TableBody', () => {
    it('renders tbody element', () => {
      renderWithProviders(
        <table>
          <TableBody>
            <tr>
              <td>Body</td>
            </tr>
          </TableBody>
        </table>
      );
      expect(screen.getByRole('rowgroup')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      renderWithProviders(
        <table>
          <TableBody className="custom-body">
            <tr>
              <td>Body</td>
            </tr>
          </TableBody>
        </table>
      );
      const tbody = screen.getByRole('rowgroup');
      expect(tbody).toHaveClass('custom-body');
    });

    it('removes border from last row', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Row 1</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Row 2</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const tbody = screen.getByRole('rowgroup');
      expect(tbody).toHaveClass('[&_tr:last-child]:border-0');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLTableSectionElement>();
      renderWithProviders(
        <table>
          <TableBody ref={ref}>
            <tr>
              <td>Body</td>
            </tr>
          </TableBody>
        </table>
      );
      expect(ref.current).toBeInstanceOf(HTMLTableSectionElement);
    });
  });

  describe('TableFooter', () => {
    it('renders tfoot element', () => {
      renderWithProviders(
        <table>
          <TableFooter>
            <tr>
              <td>Footer</td>
            </tr>
          </TableFooter>
        </table>
      );
      expect(screen.getByRole('rowgroup')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      renderWithProviders(
        <table>
          <TableFooter className="custom-footer">
            <tr>
              <td>Footer</td>
            </tr>
          </TableFooter>
        </table>
      );
      const tfoot = screen.getByRole('rowgroup');
      expect(tfoot).toHaveClass('custom-footer');
    });

    it('has border-top style', () => {
      renderWithProviders(
        <Table>
          <TableFooter>
            <TableRow>
              <TableCell>Total</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      );
      const tfoot = screen.getByRole('rowgroup');
      expect(tfoot).toHaveClass('border-t');
    });

    it('has muted background style', () => {
      renderWithProviders(
        <Table>
          <TableFooter>
            <TableRow>
              <TableCell>Total</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      );
      const tfoot = screen.getByRole('rowgroup');
      expect(tfoot).toHaveClass('bg-muted/50');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLTableSectionElement>();
      renderWithProviders(
        <table>
          <TableFooter ref={ref}>
            <tr>
              <td>Footer</td>
            </tr>
          </TableFooter>
        </table>
      );
      expect(ref.current).toBeInstanceOf(HTMLTableSectionElement);
    });
  });

  describe('TableRow', () => {
    it('renders tr element', () => {
      renderWithProviders(
        <table>
          <tbody>
            <TableRow>
              <td>Row</td>
            </TableRow>
          </tbody>
        </table>
      );
      expect(screen.getByRole('row')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow className="custom-row">
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const row = screen.getByRole('row');
      expect(row).toHaveClass('custom-row');
    });

    it('has border-bottom style', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const row = screen.getByRole('row');
      expect(row).toHaveClass('border-b');
    });

    it('has hover effect', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const row = screen.getByRole('row');
      expect(row).toHaveClass('hover:bg-muted/50');
    });

    it('supports selected state styling', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow data-state="selected">
              <TableCell>Selected</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const row = screen.getByRole('row');
      expect(row).toHaveClass('data-[state=selected]:bg-muted');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLTableRowElement>();
      renderWithProviders(
        <table>
          <tbody>
            <TableRow ref={ref}>
              <td>Row</td>
            </TableRow>
          </tbody>
        </table>
      );
      expect(ref.current).toBeInstanceOf(HTMLTableRowElement);
    });
  });

  describe('TableHead', () => {
    it('renders th element', () => {
      renderWithProviders(
        <table>
          <thead>
            <tr>
              <TableHead>Header</TableHead>
            </tr>
          </thead>
        </table>
      );
      expect(screen.getByRole('columnheader')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      renderWithProviders(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="custom-head">Header</TableHead>
            </TableRow>
          </TableHeader>
        </Table>
      );
      const th = screen.getByRole('columnheader');
      expect(th).toHaveClass('custom-head');
    });

    it('has correct height and padding', () => {
      renderWithProviders(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Header</TableHead>
            </TableRow>
          </TableHeader>
        </Table>
      );
      const th = screen.getByRole('columnheader');
      expect(th).toHaveClass('h-12');
      expect(th).toHaveClass('px-4');
    });

    it('has text alignment styles', () => {
      renderWithProviders(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Header</TableHead>
            </TableRow>
          </TableHeader>
        </Table>
      );
      const th = screen.getByRole('columnheader');
      expect(th).toHaveClass('text-left');
      expect(th).toHaveClass('align-middle');
    });

    it('has muted text color', () => {
      renderWithProviders(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Header</TableHead>
            </TableRow>
          </TableHeader>
        </Table>
      );
      const th = screen.getByRole('columnheader');
      expect(th).toHaveClass('text-muted-foreground');
    });

    it('has special handling for checkbox columns', () => {
      renderWithProviders(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <input type="checkbox" role="checkbox" />
              </TableHead>
            </TableRow>
          </TableHeader>
        </Table>
      );
      const th = screen.getByRole('columnheader');
      expect(th).toHaveClass('[&:has([role=checkbox])]:pr-0');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLTableCellElement>();
      renderWithProviders(
        <table>
          <thead>
            <tr>
              <TableHead ref={ref}>Header</TableHead>
            </tr>
          </thead>
        </table>
      );
      expect(ref.current).toBeInstanceOf(HTMLTableCellElement);
    });
  });

  describe('TableCell', () => {
    it('renders td element', () => {
      renderWithProviders(
        <table>
          <tbody>
            <tr>
              <TableCell>Cell</TableCell>
            </tr>
          </tbody>
        </table>
      );
      expect(screen.getByRole('cell')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell className="custom-cell">Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const td = screen.getByRole('cell');
      expect(td).toHaveClass('custom-cell');
    });

    it('has correct padding', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const td = screen.getByRole('cell');
      expect(td).toHaveClass('p-4');
    });

    it('has vertical alignment', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const td = screen.getByRole('cell');
      expect(td).toHaveClass('align-middle');
    });

    it('has special handling for checkbox columns', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>
                <input type="checkbox" role="checkbox" />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const td = screen.getByRole('cell');
      expect(td).toHaveClass('[&:has([role=checkbox])]:pr-0');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLTableCellElement>();
      renderWithProviders(
        <table>
          <tbody>
            <tr>
              <TableCell ref={ref}>Cell</TableCell>
            </tr>
          </tbody>
        </table>
      );
      expect(ref.current).toBeInstanceOf(HTMLTableCellElement);
    });
  });

  describe('TableCaption', () => {
    it('renders caption element', () => {
      renderWithProviders(
        <Table>
          <TableCaption>Caption text</TableCaption>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      expect(screen.getByText('Caption text')).toBeInTheDocument();
    });

    it('renders with custom className', () => {
      renderWithProviders(
        <Table>
          <TableCaption className="custom-caption">Caption</TableCaption>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const caption = screen.getByText('Caption');
      expect(caption).toHaveClass('custom-caption');
    });

    it('has muted text color', () => {
      renderWithProviders(
        <Table>
          <TableCaption>Caption</TableCaption>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const caption = screen.getByText('Caption');
      expect(caption).toHaveClass('text-muted-foreground');
    });

    it('has small text size', () => {
      renderWithProviders(
        <Table>
          <TableCaption>Caption</TableCaption>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const caption = screen.getByText('Caption');
      expect(caption).toHaveClass('text-sm');
    });

    it('has top margin', () => {
      renderWithProviders(
        <Table>
          <TableCaption>Caption</TableCaption>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      const caption = screen.getByText('Caption');
      expect(caption).toHaveClass('mt-4');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLTableCaptionElement>();
      renderWithProviders(
        <Table>
          <TableCaption ref={ref}>Caption</TableCaption>
          <TableBody>
            <TableRow>
              <TableCell>Content</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );
      expect(ref.current).toBeInstanceOf(HTMLTableCaptionElement);
    });
  });

  describe('Complete Table Example', () => {
    it('renders complete table with all components', () => {
      const data = [
        { id: 1, name: 'John Doe', email: 'john@example.com' },
        { id: 2, name: 'Jane Smith', email: 'jane@example.com' },
        { id: 3, name: 'Bob Johnson', email: 'bob@example.com' },
      ];

      renderWithProviders(
        <Table>
          <TableCaption>User List</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((user) => (
              <TableRow key={user.id}>
                <TableCell>{user.id}</TableCell>
                <TableCell>{user.name}</TableCell>
                <TableCell>{user.email}</TableCell>
              </TableRow>
            ))}
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell colSpan={3}>Total: {data.length} users</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      );

      expect(screen.getByText('User List')).toBeInTheDocument();
      expect(screen.getByText('ID')).toBeInTheDocument();
      expect(screen.getByText('Name')).toBeInTheDocument();
      expect(screen.getByText('Email')).toBeInTheDocument();
      expect(screen.getByText('John Doe')).toBeInTheDocument();
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
      expect(screen.getByText('Bob Johnson')).toBeInTheDocument();
      expect(screen.getByText('Total: 3 users')).toBeInTheDocument();
    });

    it('renders empty table body', () => {
      renderWithProviders(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell colSpan={1}>No data available</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('No data available')).toBeInTheDocument();
    });

    it('handles click events on rows', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();

      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow onClick={handleClick}>
              <TableCell>Clickable</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const row = screen.getByRole('row');
      await user.click(row);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('handles click events on cells', async () => {
      const user = userEvent.setup();
      const handleClick = jest.fn();

      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell onClick={handleClick}>Clickable</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const cell = screen.getByRole('cell');
      await user.click(cell);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('Accessibility', () => {
    it('has proper table semantics', () => {
      renderWithProviders(
        <Table>
          <TableCaption>Sales Data</TableCaption>
          <TableHeader>
            <TableRow>
              <TableHead>Product</TableHead>
              <TableHead>Revenue</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>Widget</TableCell>
              <TableCell>$100</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByRole('table')).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Product' })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: 'Revenue' })).toBeInTheDocument();
    });

    it('supports ARIA attributes', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow aria-selected="true">
              <TableCell>Selected row</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const row = screen.getByRole('row');
      expect(row).toHaveAttribute('aria-selected', 'true');
    });

    it('supports scope attribute on headers', () => {
      renderWithProviders(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Column Header</TableHead>
            </TableRow>
          </TableHeader>
        </Table>
      );

      const th = screen.getByRole('columnheader');
      expect(th).toHaveAttribute('scope', 'col');
    });
  });

  describe('Edge Cases', () => {
    it('handles very long content in cells', () => {
      const longText = 'A'.repeat(1000);

      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>{longText}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(longText)).toBeInTheDocument();
    });

    it('handles special characters in content', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>{'<Special> & "Characters"'}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('<Special> & "Characters"')).toBeInTheDocument();
    });

    it('handles nested HTML in cells', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>
                <strong>Bold</strong> and <em>italic</em>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Bold')).toBeInTheDocument();
      expect(screen.getByText('italic')).toBeInTheDocument();
    });

    it('handles colspan and rowspan', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell colSpan={2}>Spanning two columns</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Normal cell 1</TableCell>
              <TableCell>Normal cell 2</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Spanning two columns')).toHaveAttribute('colSpan', '2');
    });

    it('handles missing optional components', () => {
      renderWithProviders(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Only body</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByRole('table')).toBeInTheDocument();
      expect(screen.getByText('Only body')).toBeInTheDocument();
    });
  });
});
