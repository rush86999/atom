/**
 * CanvasSheet Component Tests
 *
 * Testing suite for CanvasSheet covering:
 * - Table rendering (title, headers, cells)
 * - Loading / error / empty states
 * - Search filtering and row counts
 * - Sorting (asc/desc, onSort callback, sort icon)
 * - Cell press and selection mode
 * - CSV export (including falsy value fidelity)
 * - Pull-to-refresh and infinite scroll
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { ScrollView, RefreshControl } from 'react-native';
import { Checkbox } from 'react-native-paper';
import { CanvasSheet } from '../CanvasSheet';
import { SheetData } from '../../types/canvas';

// Mock dependencies
jest.mock('expo-haptics', () => ({
  impactAsync: jest.fn(),
  ImpactFeedbackStyle: {
    Light: 'light',
    Medium: 'medium',
    Heavy: 'heavy',
  },
}));

jest.mock('expo-file-system', () => ({
  writeAsStringAsync: jest.fn().mockResolvedValue(undefined),
  documentDirectory: '/tmp/',
  EncodingType: {
    UTF8: 'utf8',
  },
}));

jest.mock('expo-sharing', () => ({
  isAvailableAsync: jest.fn(() => Promise.resolve(true)),
  shareAsync: jest.fn().mockResolvedValue(undefined),
}));

const mockWriteAsStringAsync = require('expo-file-system').writeAsStringAsync;
const mockShareAsync = require('expo-sharing').shareAsync;

const baseSheet: SheetData = {
  title: 'Sales Data',
  columns: [
    { key: 'region', label: 'Region', type: 'text' },
    { key: 'amount', label: 'Amount', type: 'number' },
  ],
  rows: [
    { id: 'r1', data: { region: 'North', amount: 100 } },
    { id: 'r2', data: { region: 'South', amount: 200 } },
    { id: 'r3', data: { region: 'West', amount: 0 } },
  ],
};

describe('CanvasSheet Component', () => {
  describe('Rendering', () => {
    test('renders title, column headers, and row cell values', () => {
      const { getByText } = render(<CanvasSheet data={baseSheet} />);

      expect(getByText('Sales Data')).toBeTruthy();
      expect(getByText('Region')).toBeTruthy();
      expect(getByText('Amount')).toBeTruthy();
      expect(getByText('North')).toBeTruthy();
      expect(getByText('South')).toBeTruthy();
      expect(getByText('West')).toBeTruthy();
      expect(getByText('100')).toBeTruthy();
      expect(getByText('3 rows')).toBeTruthy();
    });

    test('renders falsy cell values (0) without crashing', () => {
      const { getByText } = render(<CanvasSheet data={baseSheet} />);
      expect(getByText('0')).toBeTruthy();
    });

    test('renders null/undefined cell values as empty', () => {
      const sheet: SheetData = {
        title: 'Nulls',
        columns: [{ key: 'a', label: 'A', type: 'text' }],
        rows: [{ id: 'r1', data: { a: null } }],
      };
      const { getByText } = render(<CanvasSheet data={sheet} />);
      expect(getByText('1 rows')).toBeTruthy();
    });

    test('hides title and search when not provided/disabled', () => {
      const sheet: SheetData = { title: '', columns: baseSheet.columns, rows: baseSheet.rows };
      const { queryByText, queryByPlaceholderText } = render(
        <CanvasSheet data={sheet} enableSearch={false} />
      );
      expect(queryByPlaceholderText('Search...')).toBeNull();
    });
  });

  describe('States', () => {
    test('shows loading indicator with no rows', () => {
      const { getByText } = render(
        <CanvasSheet data={{ ...baseSheet, rows: [] }} loading />
      );
      expect(getByText('Loading data...')).toBeTruthy();
    });

    test('shows error message when error and no rows', () => {
      const { getByText } = render(
        <CanvasSheet data={{ ...baseSheet, rows: [] }} error="Backend down" />
      );
      expect(getByText('Backend down')).toBeTruthy();
    });

    test('shows empty state when no rows', () => {
      const { getByText } = render(<CanvasSheet data={{ ...baseSheet, rows: [] }} />);
      expect(getByText('No data available')).toBeTruthy();
    });

    test('shows no-match message when search has no results', () => {
      const { getByPlaceholderText, getByText } = render(<CanvasSheet data={baseSheet} />);
      fireEvent.changeText(getByPlaceholderText('Search...'), 'zzz-nonexistent');
      expect(getByText('No matching results')).toBeTruthy();
    });
  });

  describe('Search', () => {
    test('filters rows by search query', () => {
      const { getByPlaceholderText, getByText, queryByText } = render(<CanvasSheet data={baseSheet} />);

      fireEvent.changeText(getByPlaceholderText('Search...'), 'north');

      expect(getByText('North')).toBeTruthy();
      expect(queryByText('South')).toBeNull();
      expect(queryByText('West')).toBeNull();
      expect(getByText('1 rows')).toBeTruthy();
    });

    test('matches values across all columns', () => {
      const { getByPlaceholderText, getByText, queryByText } = render(<CanvasSheet data={baseSheet} />);

      fireEvent.changeText(getByPlaceholderText('Search...'), '200');

      expect(getByText('200')).toBeTruthy();
      expect(queryByText('North')).toBeNull();
    });
  });

  describe('Sorting', () => {
    test('sorts ascending on first header press and notifies onSort', () => {
      const onSort = jest.fn();
      const { getByText } = render(<CanvasSheet data={baseSheet} onSort={onSort} />);

      fireEvent.press(getByText('Amount'));

      expect(onSort).toHaveBeenCalledWith('amount', 'asc');
      // Sort icon shown after sorting
      expect(getByText(' ▲')).toBeTruthy();
    });

    test('toggles to descending on second press', () => {
      const onSort = jest.fn();
      const { getByText } = render(<CanvasSheet data={baseSheet} onSort={onSort} />);

      fireEvent.press(getByText('Amount'));
      fireEvent.press(getByText('Amount'));

      expect(onSort).toHaveBeenLastCalledWith('amount', 'desc');
      expect(getByText(' ▼')).toBeTruthy();
    });

    test('does not sort when enableSort is false', () => {
      const onSort = jest.fn();
      const { getByText } = render(
        <CanvasSheet data={baseSheet} onSort={onSort} enableSort={false} />
      );

      fireEvent.press(getByText('Amount'));

      expect(onSort).not.toHaveBeenCalled();
    });
  });

  describe('Cell interactions', () => {
    test('calls onCellPress with row index and column key', () => {
      const onCellPress = jest.fn();
      const { getByText } = render(<CanvasSheet data={baseSheet} onCellPress={onCellPress} />);

      fireEvent.press(getByText('North'));

      expect(onCellPress).toHaveBeenCalledWith(0, 'region');
    });
  });

  describe('Selection mode', () => {
    const renderWithCheckboxes = (props: any = {}) => {
      const result = render(<CanvasSheet data={baseSheet} {...props} />);
      return {
        ...result,
        checkboxes: () => result.UNSAFE_getAllByType(Checkbox),
      };
    };

    test('enters selection mode and selects all via header checkbox', () => {
      const { getByTestId, getByText, queryByText, checkboxes } = renderWithCheckboxes();

      // Enter selection mode via toolbar icon
      fireEvent.press(getByTestId('icon-checkbox-multiple-marked-outline'));
      expect(getByTestId('icon-select-all')).toBeTruthy();

      // Header checkbox (first in tree): select all
      fireEvent.press(checkboxes()[0]);

      expect(getByText('3 selected')).toBeTruthy();

      // Header checkbox again clears selection
      fireEvent.press(checkboxes()[0]);
      expect(queryByText('3 selected')).toBeNull();
    });

    test('selects a row by tapping a cell while in selection mode', () => {
      const onCellPress = jest.fn();
      const { getByTestId, getByText, checkboxes } = renderWithCheckboxes({ onCellPress });

      fireEvent.press(getByTestId('icon-checkbox-multiple-marked-outline'));
      fireEvent.press(getByText('North'));

      // No cell press forwarded in selection mode; row selected instead
      expect(onCellPress).not.toHaveBeenCalled();
      expect(getByText('1 selected')).toBeTruthy();
      expect(checkboxes()[1].props.status).toBe('checked');
    });

    test('select all and clear via toolbar actions', () => {
      const { getByTestId, getByText, queryByText } = render(<CanvasSheet data={baseSheet} />);

      fireEvent.press(getByTestId('icon-checkbox-multiple-marked-outline'));
      fireEvent.press(getByTestId('icon-select-all'));
      expect(getByText('3 selected')).toBeTruthy();

      fireEvent.press(getByTestId('icon-select-remove'));
      expect(queryByText('3 selected')).toBeNull();
    });
  });

  describe('Export', () => {
    test('exports filtered rows to CSV and shares the file', async () => {
      const { getByTestId } = render(<CanvasSheet data={baseSheet} />);

      fireEvent.press(getByTestId('icon-download-outline'));

      await waitFor(() => {
        expect(mockWriteAsStringAsync).toHaveBeenCalled();
      });

      const [, csvContent] = mockWriteAsStringAsync.mock.calls[0];
      expect(csvContent).toContain('Region,Amount');
      // Falsy numeric zero must survive export (regression: `|| ''` lost it)
      expect(csvContent).toContain('"West","0"');
      expect(csvContent).toContain('"North","100"');

      await waitFor(() => {
        expect(mockShareAsync).toHaveBeenCalledWith(
          expect.stringContaining('/tmp/sheet-data-'),
          expect.objectContaining({ mimeType: 'text/csv' })
        );
      });
    });

    test('exports only search-filtered rows', async () => {
      const { getByPlaceholderText, getByTestId } = render(<CanvasSheet data={baseSheet} />);

      fireEvent.changeText(getByPlaceholderText('Search...'), 'north');
      fireEvent.press(getByTestId('icon-download-outline'));

      await waitFor(() => {
        expect(mockWriteAsStringAsync).toHaveBeenCalled();
      });

      const [, csvContent] = mockWriteAsStringAsync.mock.calls[0];
      expect(csvContent).toContain('"North","100"');
      expect(csvContent).not.toContain('South');
    });
  });

  describe('Refresh and infinite scroll', () => {
    test('fires onRefresh via RefreshControl', () => {
      const onRefresh = jest.fn();
      const { UNSAFE_getByType } = render(
        <CanvasSheet data={baseSheet} onRefresh={onRefresh} refreshing={false} />
      );

      const refreshControl = UNSAFE_getByType(RefreshControl);
      fireEvent(refreshControl, 'refresh');

      expect(onRefresh).toHaveBeenCalled();
    });

    test('fires onEndReached on momentum scroll end of the vertical list', () => {
      const onEndReached = jest.fn();
      const { UNSAFE_getAllByType } = render(
        <CanvasSheet data={baseSheet} onEndReached={onEndReached} />
      );

      const scrollViews = UNSAFE_getAllByType(ScrollView);
      const verticalScroll = scrollViews[1];
      fireEvent(verticalScroll, 'momentumScrollEnd');

      expect(onEndReached).toHaveBeenCalled();
    });

    test('syncs the horizontal scroll position when the vertical list scrolls to top', () => {
      const scrollSpy = jest.spyOn(ScrollView.prototype, 'scrollTo').mockImplementation(() => {});
      const { UNSAFE_getAllByType } = render(<CanvasSheet data={baseSheet} />);

      const scrollViews = UNSAFE_getAllByType(ScrollView);
      const verticalScroll = scrollViews[1];

      // y === 0 triggers the horizontal scroll sync
      fireEvent(verticalScroll, 'scroll', {
        nativeEvent: { contentOffset: { x: 40, y: 0 } },
      });
      expect(scrollSpy).toHaveBeenCalledWith(
        expect.objectContaining({ x: 40, animated: false })
      );

      scrollSpy.mockRestore();
    });
  });

  describe('Extended interactions', () => {
    test('selects a row via its checkbox and deselects on second press', () => {
      const { getByTestId, getByText, queryByText, UNSAFE_getAllByType } = render(
        <CanvasSheet data={baseSheet} />
      );

      fireEvent.press(getByTestId('icon-checkbox-multiple-marked-outline'));

      const checkboxes = UNSAFE_getAllByType(Checkbox);
      // checkboxes[0] is the header select-all; [1] is the first row's
      fireEvent.press(checkboxes[1]);
      expect(getByText('1 selected')).toBeTruthy();

      fireEvent.press(checkboxes[1]);
      expect(queryByText('1 selected')).toBeNull();
    });

    test('deselects a row when its cell is tapped again in selection mode', () => {
      const { getByTestId, getByText, queryByText } = render(<CanvasSheet data={baseSheet} />);

      fireEvent.press(getByTestId('icon-checkbox-multiple-marked-outline'));
      fireEvent.press(getByText('North'));
      expect(getByText('1 selected')).toBeTruthy();

      // Tapping the same row's cell toggles the selection off
      fireEvent.press(getByText('North'));
      expect(queryByText('1 selected')).toBeNull();
    });

    test('opens the filter button without disrupting the sheet', () => {
      const { getByTestId, getByText } = render(<CanvasSheet data={baseSheet} />);

      fireEvent.press(getByTestId('icon-filter-outline'));

      // The sheet still renders its rows after the filter modal state flips
      expect(getByText('North')).toBeTruthy();
      expect(getByText('3 rows')).toBeTruthy();
    });

    test('exports null cell values as empty strings', async () => {
      const sheet: SheetData = {
        title: 'Nullable',
        columns: [
          { key: 'a', label: 'A', type: 'text' },
          { key: 'b', label: 'B', type: 'number' },
        ],
        rows: [{ id: 'r1', data: { a: 'x', b: null } }],
      };
      const { getByTestId } = render(<CanvasSheet data={sheet} />);

      fireEvent.press(getByTestId('icon-download-outline'));

      await waitFor(() => {
        expect(mockWriteAsStringAsync).toHaveBeenCalled();
      });

      const [, csvContent] = mockWriteAsStringAsync.mock.calls[0];
      expect(csvContent).toContain('"x",""');
    });

    test('export failure surfaces an alert', async () => {
      mockWriteAsStringAsync.mockRejectedValueOnce(new Error('Disk full'));
      const { Alert } = require('react-native');

      const { getByTestId } = render(<CanvasSheet data={baseSheet} />);
      fireEvent.press(getByTestId('icon-download-outline'));

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith(
          'Export Failed',
          'Could not export sheet data'
        );
      });
    });
  });
});
