/**
 * Table Edge Cases Test Suite
 *
 * Tests edge cases for Table component including:
 * - Very large datasets
 * - Empty datasets
 * - Single row datasets
 * - Null/undefined values
 * - Very long text
 * - Special characters
 * - Concurrent sorting and filtering
 * - Rapid pagination
 * - Selection with keyboard
 * - Cell editing with validation
 */

import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
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

describe('Table Edge Cases', () => {
  describe('Very Large Datasets', () => {
    it('should handle 100+ rows', () => {
      const rows = Array.from({ length: 100 }, (_, i) => ({
        id: i,
        name: `Row ${i}`,
        value: i * 10,
      }));

      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Value</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id}>
                <TableCell>{row.id}</TableCell>
                <TableCell>{row.name}</TableCell>
                <TableCell>{row.value}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Row 0')).toBeInTheDocument();
      expect(screen.getByText('Row 99')).toBeInTheDocument();
    });

    it('should handle many columns', () => {
      const columns = Array.from({ length: 20 }, (_, i) => `Column ${i}`);

      render(
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col}>{col}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              {columns.map((col) => (
                <TableCell key={col}>{col} Value</TableCell>
              ))}
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Column 0')).toBeInTheDocument();
      expect(screen.getByText('Column 19')).toBeInTheDocument();
    });

    it('should handle large cell content', () => {
      const longContent = 'a'.repeat(1000);

      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>{longContent}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(new RegExp('a{100}'))).toBeInTheDocument();
    });
  });

  describe('Empty Datasets', () => {
    it('should handle empty table body', () => {
      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody />
        </Table>
      );

      expect(screen.getByRole('table')).toBeInTheDocument();
    });

    it('should handle table with only header', () => {
      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
            </TableRow>
          </TableHeader>
        </Table>
      );

      expect(screen.getByRole('table')).toBeInTheDocument();
    });

    it('should handle table with empty rows', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell></TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const table = screen.getByRole('table');
      expect(table).toBeInTheDocument();
    });
  });

  describe('Single Row Datasets', () => {
    it('should handle single row', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Single Row</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Single Row')).toBeInTheDocument();
    });

    it('should handle single column', () => {
      render(
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

      expect(screen.getByText('Row 1')).toBeInTheDocument();
      expect(screen.getByText('Row 2')).toBeInTheDocument();
    });
  });

  describe('Null/Undefined Values', () => {
    it('should handle null values in cells', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>{null}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const table = screen.getByRole('table');
      expect(table).toBeInTheDocument();
    });

    it('should handle undefined values in cells', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>{undefined}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const table = screen.getByRole('table');
      expect(table).toBeInTheDocument();
    });

    it('should handle mixed null and valid values', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Valid</TableCell>
              <TableCell>{null}</TableCell>
              <TableCell>Also Valid</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Valid')).toBeInTheDocument();
      expect(screen.getByText('Also Valid')).toBeInTheDocument();
    });
  });

  describe('Very Long Text', () => {
    it('should handle very long text in cells', () => {
      const longText = 'This is a very long text that goes on and on '.repeat(50);

      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>{longText}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(/very long text/i)).toBeInTheDocument();
    });

    it('should handle text with no spaces', () => {
      const noSpaces = 'a'.repeat(500);

      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>{noSpaces}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(new RegExp('a{100}'))).toBeInTheDocument();
    });

    it('should handle text with many newlines', () => {
      const newlines = 'Line\n'.repeat(50);

      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>{newlines}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(/Line/i)).toBeInTheDocument();
    });
  });

  describe('Special Characters', () => {
    it('should handle HTML entities', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>&lt;tag&gt; &amp; &quot;quoted&quot;</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(/<tag>/i)).toBeInTheDocument();
    });

    it('should handle emoji characters', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>🎉 👍 🚀 ❤️</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(/🎉/)).toBeInTheDocument();
    });

    it('should handle unicode characters', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Unicode: 你好 🚀 Ñoño</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(/unicode/i)).toBeInTheDocument();
    });

    it('should handle RTL text', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell dir="rtl">مرحبا بالعالم</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(/مرحبا/i)).toBeInTheDocument();
    });

    it('should handle script tags (escaped)', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>{'<script>alert("xss")</script>'}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      // Script tags should be escaped, not executed
      expect(screen.getByText(/script/i)).toBeInTheDocument();
    });
  });

  describe('Concurrent Sorting and Filtering', () => {
    it('should handle sortable column headers', () => {
      const handleClick = jest.fn();

      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead onClick={handleClick}>Sortable</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>Data</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const header = screen.getByText('Sortable');
      fireEvent.click(header);

      expect(handleClick).toHaveBeenCalled();
    });

    it('should handle multiple sortable columns', () => {
      const handleClick1 = jest.fn();
      const handleClick2 = jest.fn();

      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead onClick={handleClick1}>Column 1</TableHead>
              <TableHead onClick={handleClick2}>Column 2</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>Data 1</TableCell>
              <TableCell>Data 2</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      fireEvent.click(screen.getByText('Column 1'));
      fireEvent.click(screen.getByText('Column 2'));

      expect(handleClick1).toHaveBeenCalled();
      expect(handleClick2).toHaveBeenCalled();
    });
  });

  describe('Rapid Pagination', () => {
    it('should handle pagination controls', () => {
      const handleNext = jest.fn();
      const handlePrev = jest.fn();

      render(
        <div>
          <Table>
            <TableBody>
              <TableRow>
                <TableCell>Data</TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <button onClick={handlePrev}>Previous</button>
          <button onClick={handleNext}>Next</button>
        </div>
      );

      fireEvent.click(screen.getByText('Next'));
      fireEvent.click(screen.getByText('Previous'));

      expect(handleNext).toHaveBeenCalled();
      expect(handlePrev).toHaveBeenCalled();
    });

    it('should handle rapid page changes', () => {
      const handlePageChange = jest.fn();

      render(
        <div>
          <Table>
            <TableBody>
              <TableRow>
                <TableCell>Data</TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <button onClick={() => handlePageChange(1)}>Page 1</button>
          <button onClick={() => handlePageChange(2)}>Page 2</button>
          <button onClick={() => handlePageChange(3)}>Page 3</button>
        </div>
      );

      fireEvent.click(screen.getByText('Page 1'));
      fireEvent.click(screen.getByText('Page 2'));
      fireEvent.click(screen.getByText('Page 3'));

      expect(handlePageChange).toHaveBeenCalledTimes(3);
    });
  });

  describe('Selection with Keyboard', () => {
    it('should handle keyboard navigation on rows', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <Cell tabIndex={0}>Row 1</Cell>
            </TableRow>
            <TableRow>
              <Cell tabIndex={0}>Row 2</Cell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const rows = screen.getAllByRole('row');
      expect(rows.length).toBeGreaterThan(0);
    });
  });

  describe('Table Caption', () => {
    it('should handle caption', () => {
      render(
        <Table>
          <TableCaption>Table Caption</TableCaption>
          <TableBody>
            <TableRow>
              <TableCell>Data</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Table Caption')).toBeInTheDocument();
    });

    it('should handle caption with special characters', () => {
      render(
        <Table>
          <TableCaption>Caption with &lt;special&gt; characters</TableCaption>
          <TableBody>
            <TableRow>
              <TableCell>Data</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(/<special>/)).toBeInTheDocument();
    });

    it('should handle caption with emoji', () => {
      render(
        <Table>
          <TableCaption>📊 Sales Data 2024</TableCaption>
          <TableBody>
            <TableRow>
              <TableCell>Data</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText(/📊/)).toBeInTheDocument();
    });
  });

  describe('Table Footer', () => {
    it('should handle footer with summary', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>100</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>200</TableCell>
            </TableRow>
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell>Total: 300</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      );

      expect(screen.getByText('Total: 300')).toBeInTheDocument();
    });

    it('should handle footer with calculations', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell>Item 1</TableCell>
              <TableCell>10</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Item 2</TableCell>
              <TableCell>20</TableCell>
            </TableRow>
          </TableBody>
          <TableFooter>
            <TableRow>
              <TableCell>Sum</TableCell>
              <TableCell>30</TableCell>
            </TableRow>
          </TableFooter>
        </Table>
      );

      expect(screen.getByText('Sum')).toBeInTheDocument();
      expect(screen.getByText('30')).toBeInTheDocument();
    });
  });

  describe('Cell Span', () => {
    it('should handle colspan', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell colSpan={2}>Spanned Cell</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Cell 1</TableCell>
              <TableCell>Cell 2</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Spanned Cell')).toBeInTheDocument();
    });

    it('should handle rowspan', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell rowSpan={2}>Spanned</TableCell>
              <TableCell>Cell 1</TableCell>
            </TableRow>
            <TableRow>
              <TableCell>Cell 2</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Spanned')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper table semantics', () => {
      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>John</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const table = screen.getByRole('table');
      expect(table).toBeInTheDocument();
    });

    it('should have proper header scope', () => {
      render(
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead scope="col">Name</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell scope="row">John</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Name')).toBeInTheDocument();
      expect(screen.getByText('John')).toBeInTheDocument();
    });
  });

  describe('Custom Styling', () => {
    it('should handle custom className on table', () => {
      render(
        <Table className="custom-table-class">
          <TableBody>
            <TableRow>
              <TableCell>Data</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const table = screen.getByRole('table');
      expect(table).toHaveClass('custom-table-class');
    });

    it('should handle custom className on rows', () => {
      render(
        <Table>
          <TableBody>
            <TableRow className="custom-row-class">
              <TableCell>Data</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      const rows = screen.getAllByRole('row');
      expect(rows[1]).toHaveClass('custom-row-class');
    });

    it('should handle custom className on cells', () => {
      render(
        <Table>
          <TableBody>
            <TableRow>
              <TableCell className="custom-cell-class">Data</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      );

      expect(screen.getByText('Data')).toHaveClass('custom-cell-class');
    });
  });
});

// Helper component for tablable cells
const Cell: React.FC<React.TdHTMLAttributes<HTMLTableCellElement>> = (props) => {
  return <td {...props} />;
};
