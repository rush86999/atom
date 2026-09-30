import React from 'react';
import { renderWithProviders, screen, fireEvent } from '../../../tests/test-utils';
import WorkbookResultCard from '../WorkbookResultCard';

const result = {
    schema: 'workbook-result-1',
    file: 'recipe log.xlsx',
    source_note: 'saved copy · 2026-09-07',
    coverage: '46 sheets indexed · 46 sheets scanned',
    items: [
        { item: 'Sourdough loaf', status: 'found', value: '78%', basis: 'HYDRATION',
          ref: 'Breads!R14', identity_cells: ['A14'],
          other_bases: [{ basis: 'FLOUR', display: '450g' }] },
        { item: 'rye', status: 'ambiguous',
          candidates: [
              { ref: 'Breads!R3', value: '70%', basis: 'HYDRATION', identity_cells: ['A3'] },
              { ref: 'Breads!R9', value: '68%', basis: 'HYDRATION', identity_cells: ['A9'] }],
          more_candidates: 2 },
        { item: 'milk bread', status: 'absent' },
    ],
};

describe('WorkbookResultCard', () => {
    it('renders header, footer and one row per item', () => {
        renderWithProviders(
            <WorkbookResultCard result={result as any} rawText="raw markdown" />);
        expect(screen.getByTestId('workbook-result-card')).toBeInTheDocument();
        expect(screen.getByTestId('workbook-result-file').textContent)
            .toContain('recipe log.xlsx');
        expect(screen.getByTestId('workbook-result-coverage').textContent)
            .toContain('46 sheets indexed');
        expect(screen.getAllByTestId('workbook-result-row')).toHaveLength(3);
        expect(screen.getByText('Sourdough loaf')).toBeInTheDocument();
        expect(screen.getByText('78%')).toBeInTheDocument();
        expect(screen.getByText(/4 candidate rows/)).toBeInTheDocument();
    });

    it('reveals provenance evidence per row on toggle', () => {
        renderWithProviders(<WorkbookResultCard result={result as any} />);
        expect(screen.queryByTestId('workbook-result-evidence-0')).toBeNull();
        fireEvent.click(screen.getByTestId('workbook-result-toggle-0'));
        expect(screen.getByTestId('workbook-result-evidence-0').textContent)
            .toContain('Breads!R14');
        fireEvent.click(screen.getByTestId('workbook-result-toggle-1'));
        expect(screen.getByTestId('workbook-result-evidence-1').textContent)
            .toContain('Breads!R3');
        expect(screen.getByTestId('workbook-result-evidence-1').textContent)
            .toContain('+2 more');
    });

    it('keeps the authoritative markdown behind the detailed-text toggle', () => {
        renderWithProviders(
            <WorkbookResultCard result={result as any} rawText={'- **raw** list'} />);
        expect(screen.queryByTestId('workbook-result-raw')).toBeNull();
        fireEvent.click(screen.getByTestId('workbook-result-raw-toggle'));
        expect(screen.getByTestId('workbook-result-raw').textContent)
            .toContain('raw');
    });
});
