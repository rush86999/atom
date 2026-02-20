/**
 * CanvasSheet Component
 *
 * Data sheet component for tabular canvas presentations with mobile-optimized viewing.
 * Features horizontal scroll, sticky headers, sorting, filtering, search, and export.
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  StyleSheet,
  Text,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { useTheme, IconButton, Searchbar, Checkbox } from 'react-native-paper';
import * as Haptics from 'expo-haptics';
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';

import { SheetData } from '../../types/canvas';

interface CanvasSheetProps {
  data: SheetData;
  style?: any;
  onCellPress?: (rowIndex: number, columnKey: string) => void;
  onRowPress?: (row: any) => void;
  onSort?: (columnKey: string, direction: 'asc' | 'desc') => void;
  onFilter?: (filters: Record<string, any>) => void;
  onRefresh?: () => void;
  onEndReached?: () => void;
  loading?: boolean;
  refreshing?: boolean;
  error?: string;
  enableSort?: boolean;
  enableFilter?: boolean;
  enableSearch?: boolean;
  enableExport?: boolean;
  enableSelection?: boolean;
  stickyHeader?: boolean;
  freezeFirstColumn?: boolean;
}

/**
 * CanvasSheet Component
 *
 * Renders tabular data with mobile-optimized scrolling, sorting, filtering, and export.
 */
export const CanvasSheet: React.FC<CanvasSheetProps> = ({
  data,
  style,
  onCellPress,
  onRowPress,
  onSort,
  onFilter,
  onRefresh,
  onEndReached,
  loading = false,
  refreshing = false,
  error = null,
  enableSort = true,
  enableFilter = true,
  enableSearch = true,
  enableExport = true,
  enableSelection = true,
  stickyHeader = true,
  freezeFirstColumn = true,
}) => {
  const theme = useTheme();

  const [searchQuery, setSearchQuery] = useState('');
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [filters, setFilters] = useState<Record<string, any>>({});
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
  const [selectionMode, setSelectionMode] = useState(false);
  const [showFilterModal, setShowFilterModal] = useState(false);

  const horizontalScrollRef = useRef<ScrollView>(null);
  const verticalScrollRef = useRef<ScrollView>(null);

  /**
   * Filter and search rows
   */
  const filteredRows = React.useMemo(() => {
    let rows = [...data.rows];

    // Apply search
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      rows = rows.filter(row =>
        Object.values(row.data).some(
          value => String(value).toLowerCase().includes(query)
        )
      );
    }

    // Apply filters
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        rows = rows.filter(row => row.data[key] === value);
      }
    });

    // Apply sorting
    if (sortColumn) {
      rows.sort((a, b) => {
        const aVal = a.data[sortColumn];
        const bVal = b.data[sortColumn];

        if (aVal === bVal) return 0;

        const comparison = aVal > bVal ? 1 : -1;
        return sortDirection === 'asc' ? comparison : -comparison;
      });
    }

    return rows;
  }, [data.rows, searchQuery, filters, sortColumn, sortDirection]);

  /**
   * Handle sort
   */
  const handleSort = useCallback(
    (columnKey: string) => {
      if (!enableSort) return;

      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

      let newDirection: 'asc' | 'desc' = 'asc';
      if (sortColumn === columnKey && sortDirection === 'asc') {
        newDirection = 'desc';
      }

      setSortColumn(columnKey);
      setSortDirection(newDirection);
      onSort?.(columnKey, newDirection);
    },
    [enableSort, sortColumn, sortDirection, onSort]
  );

  /**
   * Handle cell press
   */
  const handleCellPress = useCallback(
    (rowIndex: number, columnKey: string) => {
      if (selectionMode) {
        handleRowSelection(filteredRows[rowIndex].id);
        return;
      }

      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      onCellPress?.(rowIndex, columnKey);
    },
    [selectionMode, filteredRows, onCellPress]
  );

  /**
   * Handle row press
   */
  const handleRowPressInternal = useCallback(
    (row: any, rowIndex: number) => {
      if (selectionMode) {
        handleRowSelection(row.id);
        return;
      }

      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      onRowPress?.(row);
    },
    [selectionMode, onRowPress]
  );

  /**
   * Handle row selection
   */
  const handleRowSelection = useCallback((rowId: string) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    setSelectedRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(rowId)) {
        newSet.delete(rowId);
      } else {
        newSet.add(rowId);
      }
      return newSet;
    });
  }, []);

  /**
   * Toggle selection mode
   */
  const toggleSelectionMode = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    setSelectionMode(prev => !prev);
    setSelectedRows(new Set());
  }, []);

  /**
   * Select all rows
   */
  const selectAll = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setSelectedRows(new Set(filteredRows.map(row => row.id)));
  }, [filteredRows]);

  /**
   * Clear selection
   */
  const clearSelection = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setSelectedRows(new Set());
  }, []);

  /**
   * Export to CSV
   */
  const exportCSV = useCallback(async () => {
    if (!enableExport || filteredRows.length === 0) return;

    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

      // Generate CSV
      const headers = data.columns.map(col => col.label);
      const rows = filteredRows.map(row =>
        data.columns.map(col => String(row.data[col.key] || ''))
      );

      const csvContent = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(',')),
      ].join('\n');

      // Write file
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const filename = `sheet-data-${timestamp}.csv`;
      const fileUri = FileSystem.documentDirectory + filename;

      await FileSystem.writeAsStringAsync(fileUri, csvContent, {
        encoding: FileSystem.EncodingType.UTF8,
      });

      // Share
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(fileUri, {
          mimeType: 'text/csv',
          dialogTitle: 'Export Sheet Data',
        });
      }
    } catch (error) {
      console.error('Failed to export:', error);
      Alert.alert('Export Failed', 'Could not export sheet data');
    }
  }, [data.columns, filteredRows, enableExport]);

  /**
   * Render header cell
   */
  const renderHeaderCell = (column: { key: string; label: string; type?: string }, index: number) => {
    const isSortable = enableSort && data.sortable !== false;
    const isSorted = sortColumn === column.key;
    const isFrozen = freezeFirstColumn && index === 0;

    return (
      <View
        key={column.key}
        style={[
          styles.headerCell,
          isFrozen && styles.frozenColumn,
          { borderRightColor: theme.colors.outline },
        ]}
      >
        <TouchableOpacity
          onPress={() => handleSort(column.key)}
          disabled={!isSortable}
          style={styles.headerCellContent}
        >
          <Text
            style={[
              styles.headerText,
              { color: theme.colors.onSurface },
              isSortable && styles.sortableHeader,
            ]}
          >
            {column.label}
          </Text>
          {isSorted && (
            <Text style={[styles.sortIcon, { color: theme.colors.primary }]}>
              {sortDirection === 'asc' ? ' ▲' : ' ▼'}
            </Text>
          )}
        </TouchableOpacity>
      </View>
    );
  };

  /**
   * Render data cell
   */
  const renderDataCell = (
    row: any,
    column: { key: string; label: string; type?: string },
    rowIndex: number,
    colIndex: number
  ) => {
    const value = row.data[column.key];
    const isFrozen = freezeFirstColumn && colIndex === 0;
    const isSelected = selectedRows.has(row.id);

    return (
      <TouchableOpacity
        key={`${row.id}-${column.key}`}
        style={[
          styles.dataCell,
          isFrozen && styles.frozenColumn,
          isSelected && { backgroundColor: theme.colors.primaryContainer + '20' },
          { borderRightColor: theme.colors.outline },
        ]}
        onPress={() => handleCellPress(rowIndex, column.key)}
      >
        <Text
          style={[styles.cellText, { color: theme.colors.onSurface }]}
          numberOfLines={2}
        >
          {value !== undefined && value !== null ? String(value) : ''}
        </Text>
      </TouchableOpacity>
    );
  };

  /**
   * Render row
   */
  const renderRow = (row: any, rowIndex: number) => {
    const isSelected = selectedRows.has(row.id);

    return (
      <View key={row.id} style={styles.row}>
        {enableSelection && (
          <View style={[styles.selectionCell, { borderRightColor: theme.colors.outline }]}>
            <Checkbox
              status={isSelected ? 'checked' : 'unchecked'}
              onPress={() => handleRowSelection(row.id)}
            />
          </View>
        )}
        {data.columns.map((column, colIndex) =>
          renderDataCell(row, column, rowIndex, colIndex)
        )}
      </View>
    );
  };

  // Loading state
  if (loading && filteredRows.length === 0) {
    return (
      <View style={[styles.container, style]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.primary} />
          <Text style={[styles.loadingText, { color: theme.colors.onSurface }]}>
            Loading data...
          </Text>
        </View>
      </View>
    );
  }

  // Error state
  if (error && filteredRows.length === 0) {
    return (
      <View style={[styles.container, style]}>
        <View style={styles.errorContainer}>
          <Text style={[styles.errorText, { color: theme.colors.error }]}>{error}</Text>
        </View>
      </View>
    );
  }

  // Empty state
  if (filteredRows.length === 0) {
    return (
      <View style={[styles.container, style]}>
        <View style={styles.emptyContainer}>
          <Text style={[styles.emptyText, { color: theme.colors.onSurface }]}>
            {searchQuery || Object.keys(filters).length > 0
              ? 'No matching results'
              : 'No data available'}
          </Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.container, style]}>
      {/* Title */}
      {data.title && (
        <Text style={[styles.title, { color: theme.colors.onSurface }]}>{data.title}</Text>
      )}

      {/* Search bar */}
      {enableSearch && (
        <Searchbar
          placeholder="Search..."
          onChangeText={setSearchQuery}
          value={searchQuery}
          style={styles.searchBar}
        />
      )}

      {/* Toolbar */}
      <View style={[styles.toolbar, { borderBottomColor: theme.colors.outline }]}>
        {enableSelection && (
          <IconButton
            icon={selectionMode ? 'close' : 'checkbox-multiple-marked-outline'}
            size={20}
            onPress={toggleSelectionMode}
          />
        )}

        {selectionMode && (
          <>
            <IconButton icon="select-all" size={20} onPress={selectAll} />
            <IconButton icon="select-remove" size={20} onPress={clearSelection} />
          </>
        )}

        {enableFilter && (
          <IconButton
            icon="filter-outline"
            size={20}
            onPress={() => setShowFilterModal(true)}
          />
        )}

        {enableExport && (
          <IconButton icon="download-outline" size={20} onPress={exportCSV} />
        )}

        <View style={styles.spacer} />
        <Text style={[styles.rowCount, { color: theme.colors.onSurfaceVariant }]}>
          {filteredRows.length} rows
        </Text>
      </View>

      {/* Header */}
      <ScrollView
        ref={horizontalScrollRef}
        horizontal
        showsHorizontalScrollIndicator={true}
        bounces={false}
        stickyHeaderIndices={stickyHeader ? [0] : []}
      >
        <View style={styles.table}>
          {/* Header row */}
          <View
            style={[
              styles.headerRow,
              { backgroundColor: theme.colors.surfaceVariant },
            ]}
          >
            {enableSelection && (
              <View
                style={[
                  styles.selectionCell,
                  styles.headerCell,
                  { borderRightColor: theme.colors.outline },
                ]}
              >
                <Checkbox
                  status={
                    selectedRows.size === filteredRows.length && filteredRows.length > 0
                      ? 'checked'
                      : 'unchecked'
                  }
                  onPress={
                    selectedRows.size === filteredRows.length
                      ? clearSelection
                      : selectAll
                  }
                />
              </View>
            )}
            {data.columns.map((column, index) => renderHeaderCell(column, index))}
          </View>

          {/* Data rows */}
          <ScrollView
            ref={verticalScrollRef}
            scrollEventThrottle={16}
            onScroll={({ nativeEvent }) => {
              // Sync horizontal scroll
              if (nativeEvent.contentOffset.y === 0) {
                horizontalScrollRef.current?.scrollTo({
                  x: nativeEvent.contentOffset.x,
                  animated: false,
                });
              }
            }}
            refreshControl={
              onRefresh ? (
                <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
              ) : undefined
            }
            onMomentumScrollEnd={() => {
              // Infinite scroll
              if (onEndReached) {
                onEndReached();
              }
            }}
          >
            {filteredRows.map((row, index) => renderRow(row, index))}
          </ScrollView>
        </View>
      </ScrollView>

      {/* Selection mode banner */}
      {selectionMode && selectedRows.size > 0 && (
        <View style={[styles.selectionBanner, { backgroundColor: theme.colors.primary }]}>
          <Text style={[styles.selectionBannerText, { color: theme.colors.onPrimary }]}>
            {selectedRows.size} selected
          </Text>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    padding: 16,
    paddingBottom: 8,
  },
  searchBar: {
    marginHorizontal: 16,
    marginBottom: 12,
    elevation: 0,
  },
  toolbar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 8,
    borderBottomWidth: 1,
  },
  spacer: {
    flex: 1,
  },
  rowCount: {
    fontSize: 12,
    paddingRight: 16,
  },
  table: {
    minWidth: '100%',
  },
  headerRow: {
    flexDirection: 'row',
    minHeight: 48,
  },
  headerCell: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    justifyContent: 'center',
    borderRightWidth: 1,
    minWidth: 120,
  },
  headerCellContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerText: {
    fontSize: 13,
    fontWeight: '600',
  },
  sortableHeader: {
    color: '#2196F3',
  },
  sortIcon: {
    fontSize: 10,
    marginLeft: 4,
  },
  frozenColumn: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    zIndex: 10,
    backgroundColor: '#fff',
    borderRightWidth: 2,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 2, height: 0 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  row: {
    flexDirection: 'row',
    minHeight: 48,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  selectionCell: {
    width: 56,
    paddingHorizontal: 8,
    justifyContent: 'center',
    borderRightWidth: 1,
  },
  dataCell: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    justifyContent: 'center',
    borderRightWidth: 1,
    minWidth: 120,
    minHeight: 48,
  },
  cellText: {
    fontSize: 13,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 14,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  errorText: {
    fontSize: 14,
    textAlign: 'center',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  emptyText: {
    fontSize: 16,
    textAlign: 'center',
  },
  selectionBanner: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingVertical: 12,
    paddingHorizontal: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  selectionBannerText: {
    fontSize: 14,
    fontWeight: '600',
  },
});

export default CanvasSheet;
